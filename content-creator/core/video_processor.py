import asyncio
import subprocess
import time
from pathlib import Path

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


def _run_sync(*args: str) -> tuple[int, str]:
    result = subprocess.run(list(args), capture_output=True, text=True)
    return result.returncode, result.stderr


async def _ffmpeg(*args: str) -> tuple[int, str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_sync, "ffmpeg", "-y", *args)


def _out(name: str) -> Path:
    return OUTPUTS_DIR / name


async def images_to_video(
    image_folder: Path,
    fps: int = 30,
    transition: str = "fade",
    output_name: str | None = None,
) -> dict:
    output_name = output_name or f"video_{int(time.time())}.mp4"
    output = _out(output_name)
    pattern = str(image_folder / "*.jpg")

    extra = []
    if transition == "zoom":
        extra = ["-vf", "zoompan=z='zoom+0.001':d=25,scale=1920:1080"]
    elif transition == "fade":
        extra = ["-vf", "fade=in:0:15"]

    args = [
        "-framerate", str(fps),
        "-pattern_type", "glob", "-i", pattern,
        *extra,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output),
    ]
    code, err = await _ffmpeg(*args)
    if code != 0:
        raise RuntimeError(f"ffmpeg failed: {err[-500:]}")
    return _file_info(output)


async def clip_video(input_path: Path, start: float = 0, end: float | None = None, output_name: str | None = None) -> dict:
    output_name = output_name or f"clip_{int(time.time())}.mp4"
    output = _out(output_name)
    args = ["-i", str(input_path), "-ss", str(start)]
    if end is not None:
        args += ["-to", str(end)]
    args += ["-c", "copy", str(output)]
    code, err = await _ffmpeg(*args)
    if code != 0:
        raise RuntimeError(f"clip failed: {err[-500:]}")
    return _file_info(output)


async def concat_videos(parts: list[Path], output_name: str | None = None) -> dict:
    output_name = output_name or f"concat_{int(time.time())}.mp4"
    output = _out(output_name)
    list_file = OUTPUTS_DIR / f"_list_{int(time.time())}.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in parts))
    code, err = await _ffmpeg("-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output))
    list_file.unlink(missing_ok=True)
    if code != 0:
        raise RuntimeError(f"concat failed: {err[-500:]}")
    return _file_info(output)


def list_outputs(ext_filter: str | None = None) -> list[dict]:
    files = []
    for f in sorted(OUTPUTS_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.name.startswith("_"):
            continue
        if ext_filter and not f.name.endswith(ext_filter):
            continue
        stat = f.stat()
        files.append({"name": f.name, "size": _fmt_size(stat.st_size),
                       "format": f.suffix.lstrip("."), "created": _fmt_time(stat.st_mtime), "duration": "—"})
    return files


def _file_info(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path), "name": path.name, "size": _fmt_size(stat.st_size),
            "format": path.suffix.lstrip("."), "created": _fmt_time(stat.st_mtime)}


def _fmt_size(size: int) -> str:
    if size >= 1_073_741_824: return f"{size/1_073_741_824:.1f} GB"
    if size >= 1_048_576:     return f"{size/1_048_576:.1f} MB"
    if size >= 1024:           return f"{size/1024:.1f} KB"
    return f"{size} B"


def _fmt_time(ts: float) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
