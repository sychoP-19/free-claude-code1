#!/usr/bin/env python3
"""Quality-first model ranker.

Runs 5 benchmark tasks (math, logic, reasoning, coding, knowledge) — same problem
types used by world-class leaderboards (GSM8K, MMLU, HumanEval, BBH).
Ranks by correct answers first, speed (TTFT) second.

Usage:
    uv run python top_models.py
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field

import httpx

BASE_URL = "http://127.0.0.1:8082"
AUTH = "freecc"
TIMEOUT = 25.0

CANDIDATES = [
    "anthropic/nvidia_nim/deepseek-ai/deepseek-r1-0528",
    "anthropic/nvidia_nim/nvidia/nemotron-4-340b-instruct",
    "anthropic/nvidia_nim/deepseek-ai/deepseek-v4-pro",
    "anthropic/nvidia_nim/mistralai/mistral-large-3-675b-instruct-2512",
    "anthropic/nvidia_nim/meta/llama-3.1-405b-instruct",
    "anthropic/nvidia_nim/meta/llama-3.3-70b-instruct",
    "anthropic/nvidia_nim/nvidia/llama-3.1-nemotron-70b-instruct",
    "anthropic/nvidia_nim/mistralai/mixtral-8x22b-instruct-v0.1",
    "anthropic/nvidia_nim/z-ai/glm4.7",
    "anthropic/nvidia_nim/qwen/qwen2.5-coder-32b-instruct",
    "anthropic/open_router/deepseek/deepseek-r1",
    "anthropic/open_router/meta-llama/llama-3.3-70b-instruct",
    "anthropic/open_router/qwen/qwen-2.5-72b-instruct",
]


def _num(text: str) -> str:
    m = re.search(r"\b(\d+(?:\.\d+)?)\b", text.strip())
    return m.group(1) if m else ""


# 5 benchmark tasks with deterministic correct answers.
# Problem types match GSM8K (math), BBH (logic/reasoning), HumanEval (coding), MMLU (knowledge).
BENCHMARKS: list[dict] = [
    {
        "name": "math",
        "prompt": (
            "A store sells apples for $0.40 each and oranges for $0.65 each. "
            "Sarah buys 5 apples and 3 oranges. How much does she pay in total? "
            "Reply with only the dollar amount like: $3.95"
        ),
        "check": lambda r: "3.95" in r,
    },
    {
        "name": "logic",
        "prompt": (
            "A bat and a ball together cost $1.10. "
            "The bat costs exactly $1.00 more than the ball. "
            "How many cents does the ball cost? "
            "Reply with only the number."
        ),
        "check": lambda r: _num(r) == "5",
    },
    {
        "name": "coding",
        "prompt": (
            "What does this Python expression evaluate to: "
            "sum(x for x in range(1, 11) if x % 2 == 0) "
            "Reply with only the integer."
        ),
        "check": lambda r: _num(r) == "30",
    },
    {
        "name": "reasoning",
        "prompt": (
            "Three boxes are labelled Apples, Oranges, Mixed — but every label is wrong. "
            "You draw one fruit from the box labelled Mixed and it is an apple. "
            "What is actually in the box labelled Oranges? "
            "Reply with one word: apples, oranges, or mixed."
        ),
        "check": lambda r: "both" in r.lower() or "mixed" in r.lower(),
    },
    {
        "name": "knowledge",
        "prompt": (
            "What is the only even prime number? "
            "Reply with only the number."
        ),
        "check": lambda r: _num(r) == "2",
    },
]

MAX_TOKENS = 80

G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
B = "\033[1m"
D = "\033[2m"
X = "\033[0m"


@dataclass
class BenchResult:
    name: str
    correct: bool
    answer: str


@dataclass
class ModelResult:
    model_id: str
    label: str
    provider: str
    status: str
    ttft_ms: float | None = None
    bench: list[BenchResult] = field(default_factory=list)
    error: str = ""

    @property
    def score(self) -> int:
        return sum(1 for b in self.bench if b.correct)

    @property
    def pct(self) -> float:
        return self.score / len(self.bench) * 100 if self.bench else 0.0


async def _ask(client: httpx.AsyncClient, model_id: str, prompt: str) -> tuple[str, float]:
    t0 = time.perf_counter()
    ttft = 0.0
    parts: list[str] = []
    async with client.stream(
        "POST",
        f"{BASE_URL}/v1/messages",
        json={
            "model": model_id,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        },
        headers={"x-api-key": AUTH, "anthropic-version": "2023-06-01"},
        timeout=TIMEOUT,
    ) as resp:
        if resp.status_code != 200:
            raise RuntimeError(f"HTTP {resp.status_code}")
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if not chunk or chunk == "[DONE]":
                continue
            try:
                obj = json.loads(chunk)
                text = obj.get("delta", {}).get("text", "")
                if text:
                    if not ttft:
                        ttft = (time.perf_counter() - t0) * 1000
                    if "Provider API request failed" in text or "Authorization failed" in text:
                        raise RuntimeError(text[:80])
                    parts.append(text)
            except (json.JSONDecodeError, KeyError):
                pass
    return "".join(parts).strip(), ttft


async def run_model(client: httpx.AsyncClient, model_id: str, sem: asyncio.Semaphore) -> ModelResult:
    parts = model_id.split("/", 2)
    provider = parts[1] if len(parts) >= 2 else "?"
    label = parts[2] if len(parts) >= 3 else model_id
    short = label.split("/")[-1]

    async with sem:
        first_ttft: float | None = None
        bench: list[BenchResult] = []
        for task in BENCHMARKS:
            try:
                answer, ttft = await _ask(client, model_id, task["prompt"])
                if first_ttft is None:
                    first_ttft = ttft
                bench.append(BenchResult(task["name"], task["check"](answer), answer[:50]))
            except httpx.TimeoutException:
                return ModelResult(model_id, short, provider, "timeout", error=f">{TIMEOUT:.0f}s")
            except Exception as e:
                return ModelResult(model_id, short, provider, "error", error=str(e)[:60])
        return ModelResult(model_id, short, provider, "ok", ttft_ms=first_ttft, bench=bench)


def _bar(score: int, total: int) -> str:
    pct = score / total * 100 if total else 0
    bar = "#" * score + "." * (total - score)
    c = G if pct >= 80 else Y if pct >= 60 else R
    return f"{c}[{bar}] {score}/{total}{X}"


def _spd(ms: float | None) -> str:
    if ms is None:
        return f"{D}    ?{X}"
    if ms < 500:
        return f"{G}{ms:>5.0f}ms{X}"
    if ms < 2500:
        return f"{G}{ms/1000:>4.1f}s {X}"
    if ms < 6000:
        return f"{Y}{ms/1000:>4.1f}s {X}"
    return f"{R}{ms/1000:>4.1f}s {X}"


async def main() -> None:
    print(f"\n{B}Quality-first model benchmark{X}")
    print(f"{D}Rank 1: correct answers  |  Rank 2: speed (TTFT){X}")
    print(f"{D}Tasks : math / logic / coding / reasoning / knowledge{X}\n")

    try:
        async with httpx.AsyncClient() as c:
            await c.get(f"{BASE_URL}/v1/models", headers={"x-api-key": AUTH}, timeout=5)
    except Exception as e:
        print(f"{R}Proxy not reachable: {e}{X}\nRun: start-proxy")
        return

    print(f"Testing {B}{len(CANDIDATES)}{X} models x {B}{len(BENCHMARKS)}{X} tasks...")
    print(f"{D}(each model answers all 5 questions — takes ~30s){X}\n")

    sem = asyncio.Semaphore(3)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[run_model(client, m, sem) for m in CANDIDATES])

    ok = sorted(
        [r for r in results if r.status == "ok"],
        key=lambda r: (-r.score, r.ttft_ms or 9e9),
    )
    failed = [r for r in results if r.status != "ok"]

    task_names = "  ".join(f"{t['name']:>8}" for t in BENCHMARKS)
    print(f"  {'#':>3}  {'quality':>9}  {'speed':>7}  {task_names}   model")
    print(f"  {'-'*3}  {'-'*9}  {'-'*7}  {'  '.join(['-'*8]*5)}   {'-'*40}")

    for i, r in enumerate(ok, 1):
        cols = "  ".join(
            f"  {G}  ok  {X}" if b.correct else f"  {R} MISS {X}"
            for b in r.bench
        )
        print(f"  {i:>3}.  {_bar(r.score, len(r.bench))}  {_spd(r.ttft_ms)}  {cols}   {D}{r.provider}/{X}{r.label}")

    if failed:
        print(f"\n  {D}--- failed ---{X}")
        for r in failed:
            sym = f"{Y}timeout{X}" if r.status == "timeout" else f"{R}error  {X}"
            print(f"  {sym}  {r.label}  {D}{r.error}{X}")

    print(f"\n{'-'*70}")
    print(f"{B}Tested:{X} {len(results)}  |  {G}live: {len(ok)}{X}  |  {R}failed: {len(failed)}{X}")

    if ok:
        best = ok[0]
        print(f"\n{C}{B}Best overall:{X} {best.label}")
        print(f"  Quality {best.score}/{len(best.bench)} ({best.pct:.0f}%)  |  Speed {best.ttft_ms:.0f}ms")
        suffix = best.model_id.split("/", 1)[1] if "/" in best.model_id else best.model_id
        print(f"  /model -> {suffix}")

        print(f"\n{D}--- {best.label} answers ---{X}")
        for b in best.bench:
            tag = f"{G}correct{X}" if b.correct else f"{R}wrong  {X}"
            print(f"  {tag}  {b.name:<10} -> \"{b.answer}\"")
    print()


if __name__ == "__main__":
    asyncio.run(main())
