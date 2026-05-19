import asyncio
import json
from pathlib import Path

DOWNLOADS_DIR = Path(__file__).parent.parent / "downloads"
OUTPUTS_DIR   = Path(__file__).parent.parent / "outputs"

DOWNLOADS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)


def _fmt_size(size: int) -> str:
    if size >= 1_073_741_824:
        return f"{size/1_073_741_824:.1f} GB"
    if size >= 1_048_576:
        return f"{size/1_048_576:.1f} MB"
    if size >= 1024:
        return f"{size/1024:.1f} KB"
    return f"{size} B"


async def _run(*args: str) -> tuple[int, str, str]:
    # Uses create_subprocess_exec (not shell=True) — no injection risk
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")


async def download_video(url: str, output_dir: Path = DOWNLOADS_DIR, audio_only: bool = False) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / "%(title)s.%(ext)s")
    args = ["yt-dlp", "--no-playlist", "-o", template]
    if audio_only:
        args += ["-x", "--audio-format", "mp3"]
    args.append(url)  # url is a separate argv element, not shell-interpolated

    code, out, err = await _run(*args)
    if code != 0:
        raise RuntimeError(err or "yt-dlp failed")

    files = sorted(output_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("yt-dlp finished but no file found")

    path = files[0]
    return {"path": str(path), "name": path.name, "size": _fmt_size(path.stat().st_size)}


async def get_video_info(url: str) -> dict:
    code, out, err = await _run("yt-dlp", "--no-playlist", "--dump-json", "--no-download", url)
    if code != 0:
        raise RuntimeError(err or "yt-dlp info failed")
    return json.loads(out)
