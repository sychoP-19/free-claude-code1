"""AI Avatar Video Agent — Main entry point.

Seven-layer architecture:
  L1 Orchestrator → L2 Skills → L3 Invoked Skills
  → L4 Avatar Engine → L5 Enhancement → L6 Review → L7 Output

CLI: python main.py "Create a 60s explainer about AI safety"
"""

import argparse
import sys
from pathlib import Path

from orchestrator import Orchestrator
from config import load_config


def main():
    parser = argparse.ArgumentParser(description="AI Avatar Video Agent")
    parser.add_argument("prompt", nargs="?", help="Video topic or description")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--tts-engine", choices=["xtts-v2", "piper", "bark"], help="Override TTS engine")
    parser.add_argument("--avatar-engine", choices=["sadtalker", "musetalk", "heygen", "did"], help="Override avatar engine")
    parser.add_argument("--output-format", choices=["mp4", "webm", "gif"], default=None, help="Override output format")
    parser.add_argument("--serve", action="store_true", help="Launch Gradio UI on localhost")
    parser.add_argument("--port", type=int, default=7860, help="UI server port")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.tts_engine:
        cfg["tts"]["engine"] = args.tts_engine
    if args.avatar_engine:
        cfg["avatar"]["engine"] = args.avatar_engine
    if args.output_format:
        cfg["output"]["format"] = args.output_format

    orch = Orchestrator(cfg)

    if args.serve or not args.prompt:
        from ui.gradio_app import launch_ui
        launch_ui(orch, port=args.port)
    else:
        result = orch.run(args.prompt)
        if result.success:
            print(f"\nDone: {result.output_path}")
        else:
            print(f"\nFailed: {result.error}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
