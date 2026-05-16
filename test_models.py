#!/usr/bin/env python3
"""Connectivity, latency, and power-tier tester for all proxy models.

Usage:
    uv run python test_models.py              # test all, show best picks
    uv run python test_models.py qwen         # filter by name
    uv run python test_models.py --top 20     # show top 20 fastest
    uv run python test_models.py --best       # show only powerful+fast picks
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass

import httpx

BASE_URL = "http://127.0.0.1:8082"
AUTH = "freecc"
PROMPT = "Reply with exactly one word: ok"
MAX_TOKENS = 5
CONCURRENCY = 8
TIMEOUT = 20.0

# ANSI
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
C = "\033[96m"
B = "\033[1m"
D = "\033[2m"
X = "\033[0m"

# Power scoring — higher = more capable model (based on known model families & param counts)
# Patterns matched against lowercased model name
POWER_TIERS: list[tuple[str, int]] = [
    # Tier 5 — Flagship (reasoning / largest)
    ("deepseek-r1-0528", 10),
    ("deepseek-r1", 9),
    ("deepseek-v4-pro", 9),
    ("llama-3.1-405b", 10),
    ("llama-3.3-405b", 10),
    ("qwen3-235b", 10),
    ("qwen2.5-72b", 9),
    ("nemotron-4-340b", 10),
    ("nemotron-70b", 9),
    # Tier 4 — Very capable (70b+)
    ("llama-3.3-70b", 8),
    ("llama-3.1-70b", 8),
    ("llama-3-70b", 8),
    ("72b", 8),
    ("70b", 8),
    ("mixtral-8x22b", 8),
    ("8x22b", 8),
    ("glm4.7", 8),
    ("glm-4.7", 8),
    ("command-r-plus", 8),
    ("jamba-1.5-large", 8),
    ("yi-large", 7),
    # Tier 3 — Solid (30-50b range or known strong small models)
    ("deepseek-v4-flash", 7),
    ("deepseek-coder-6.7b", 6),
    ("47b", 7),
    ("40b", 7),
    ("32b", 7),
    ("nemotron-mini", 6),
    ("mistral-large", 7),
    ("mistral-nemo", 6),
    ("mixtral-8x7b", 6),
    ("8x7b", 6),
    # Tier 2 — Good (13-27b)
    ("27b", 6),
    ("22b", 5),
    ("13b", 5),
    ("qwen3-", 5),
    ("qwen2-", 5),
    ("gemma-3", 5),
    # Tier 1 — Fast/small but functional
    ("7b", 4),
    ("8b", 4),
]


def power_score(name: str) -> int:
    low = name.lower()
    for pattern, score in POWER_TIERS:
        if pattern in low:
            return score
    return 1  # unknown / unranked


@dataclass
class Result:
    model_id: str
    name: str
    status: str  # ok | error | timeout
    ttft_ms: float | None = None
    error: str | None = None

    @property
    def power(self) -> int:
        return power_score(self.name)

    @property
    def score(self) -> float:
        """Combined power/speed score — higher is better."""
        if self.ttft_ms is None or self.ttft_ms <= 0:
            return 0.0
        return (self.power ** 2) / (self.ttft_ms / 1000)


async def fetch_models(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(f"{BASE_URL}/v1/models", headers={"x-api-key": AUTH}, timeout=10)
    r.raise_for_status()
    return [
        m["id"]
        for m in r.json()["data"]
        if "no thinking" not in m.get("display_name", "").lower()
        and not m["id"].startswith("claude-")
    ]


async def test_model(
    client: httpx.AsyncClient, model_id: str, sem: asyncio.Semaphore
) -> Result:
    name = model_id.split("/", 1)[1] if "/" in model_id else model_id

    async with sem:
        t0 = time.perf_counter()
        try:
            async with client.stream(
                "POST",
                f"{BASE_URL}/v1/messages",
                json={
                    "model": model_id,
                    "max_tokens": MAX_TOKENS,
                    "messages": [{"role": "user", "content": PROMPT}],
                    "stream": True,
                },
                headers={"x-api-key": AUTH, "anthropic-version": "2023-06-01"},
                timeout=TIMEOUT,
            ) as resp:
                if resp.status_code != 200:
                    return Result(model_id, name, "error", error=f"HTTP {resp.status_code}")

                ttft_ms: float | None = None
                error_text: str | None = None
                async for line in resp.aiter_lines():
                    if line.startswith("data:") and ttft_ms is None:
                        chunk = line[5:].strip()
                        if not chunk or chunk == "[DONE]":
                            continue
                        # Proxy wraps provider errors as SSE text content
                        try:
                            obj = json.loads(chunk)
                            # Check for error in delta text content
                            delta = (
                                obj.get("delta", {})
                                .get("text", "")
                            )
                            if "Provider API request failed" in delta or "Authorization failed" in delta or "error" in obj.get("type", ""):
                                error_text = delta[:80] or obj.get("type", "provider_error")
                                break
                        except Exception:
                            pass
                        ttft_ms = (time.perf_counter() - t0) * 1000
                        break

            if error_text:
                return Result(model_id, name, "error", error=error_text)
            return Result(model_id, name, "ok", ttft_ms=ttft_ms)

        except httpx.TimeoutException:
            return Result(model_id, name, "timeout", error=f">{TIMEOUT:.0f}s")
        except Exception as e:
            return Result(model_id, name, "error", error=str(e)[:60])


def _fmt_ttft(r: Result) -> str:
    if r.ttft_ms is None:
        return f"{D}          -{X}"
    c = G if r.ttft_ms < 2000 else Y if r.ttft_ms < 6000 else R
    return f"{c}{r.ttft_ms:>8.0f} ms{X}"


def _fmt_power(p: int) -> str:
    stars = min(p, 10)
    filled = round(stars / 2)
    bar = "*" * filled + "." * (5 - filled)
    c = G if filled >= 4 else Y if filled >= 3 else D
    return f"{c}[{bar}]{X}"


def _fmt_status(r: Result) -> str:
    if r.status == "ok":
        return f"{G}ok     {X}"
    if r.status == "timeout":
        return f"{Y}timeout{X}"
    return f"{R}error  {X}"


def _print_recommendations(ok: list[Result]) -> None:
    # Power >= 7 and ttft < 8s — models worth using
    picks = [r for r in ok if r.power >= 7 and (r.ttft_ms or 9e9) < 8000]
    picks.sort(key=lambda r: -r.score)

    if not picks:
        picks = sorted(ok, key=lambda r: -r.score)[:10]

    print(f"\n{B}{'='*70}{X}")
    print(f"{B}  BEST PICKS FOR YOU  (powerful + fast + available){X}")
    print(f"{B}{'='*70}{X}")
    print(f"  {'#':>3}  {'power':<7}  {'ttft':>11}    model")
    print(f"  {'-'*3}  {'-'*7}  {'-'*11}    {'-'*45}")
    for i, r in enumerate(picks, 1):
        print(f"  {i:>3}.  {_fmt_power(r.power)}  {_fmt_ttft(r)}    {r.name}")

    if picks:
        best = picks[0]
        print(f"\n  {C}{B}Recommended:{X} {best.name}")
        print(f"  Use it: set MODEL=anthropic/{best.model_id.split('/', 1)[1] if '/' in best.model_id else best.model_id}")


async def main() -> None:
    args = sys.argv[1:]
    name_filter = next((a for a in args if not a.startswith("--")), "")
    top_n = int(args[args.index("--top") + 1]) if "--top" in args else None
    best_only = "--best" in args

    async with httpx.AsyncClient() as client:
        print(f"{B}Fetching model list from proxy...{X}")
        try:
            models = await fetch_models(client)
        except Exception as e:
            print(f"{R}Failed to reach proxy: {e}{X}")
            print("Is the proxy running?  cd free-claude-code && uv run uvicorn server:app --port 8082")
            sys.exit(1)

    if name_filter:
        models = [m for m in models if name_filter.lower() in m.lower()]

    total = len(models)
    if total == 0:
        print(f"{Y}No models found matching '{name_filter}'{X}")
        sys.exit(0)

    print(f"Testing {B}{total}{X} models  (concurrency={CONCURRENCY}, timeout={TIMEOUT:.0f}s)\n")

    if not best_only:
        print(f"  {'#':>5}  {'status':<9}  {'ttft':>11}  {'pwr':<7}  model")
        print(f"  {'-'*5}  {'-'*9}  {'-'*11}  {'-'*7}  {'-'*45}")

    sem = asyncio.Semaphore(CONCURRENCY)
    results: list[Result] = []
    done = 0

    async with httpx.AsyncClient() as client:
        tasks = [test_model(client, m, sem) for m in models]
        for coro in asyncio.as_completed(tasks):
            r = await coro
            done += 1
            results.append(r)
            if not best_only:
                err_hint = f"  {D}{r.error}{X}" if r.error else ""
                print(
                    f"  {done:>3}/{total}  {_fmt_status(r)}  {_fmt_ttft(r)}  "
                    f"{_fmt_power(r.power)}  {r.name}{err_hint}"
                )
            else:
                print(f"  testing {done}/{total}...", end="\r")

    ok = [r for r in results if r.status == "ok"]
    failed = [r for r in results if r.status != "ok"]

    print(f"\n{'-'*70}")
    print(f"{B}Summary:{X}  {G}{len(ok)} ok{X}  /  {R}{len(failed)} failed{X}  /  {total} total")

    if ok:
        if top_n:
            show = sorted(ok, key=lambda r: r.ttft_ms or 9e9)[:top_n]
            print(f"\n{B}Fastest (top {top_n}):{X}")
            for i, r in enumerate(show, 1):
                print(f"  {i:>3}.  {_fmt_ttft(r)}  {_fmt_power(r.power)}  {r.name}")

        _print_recommendations(ok)


if __name__ == "__main__":
    asyncio.run(main())
