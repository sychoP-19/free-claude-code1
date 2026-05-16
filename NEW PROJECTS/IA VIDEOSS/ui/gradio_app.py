"""UI Layer — Gradio interface for the AI Avatar Video Agent.

Runs on localhost:7860. Provides: prompt input, config controls,
preview player, A/B comparison, segment feedback.
"""

from __future__ import annotations

import gradio as gr
from pathlib import Path


def launch_ui(orchestrator, port: int = 7860):
    with gr.Blocks(
        title="AI Avatar Video Agent",
        theme=gr.themes.Soft(),
        css="""
        #preview-video { max-height: 500px; }
        .segment-card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; margin: 4px; }
        """,
    ) as app:

        gr.Markdown("# AI Avatar Video Agent")
        gr.Markdown("Create avatar presenter videos from a single prompt. Fully local pipeline.")

        with gr.Row():
            with gr.Column(scale=2):
                prompt_input = gr.Textbox(label="Video Topic / Prompt", placeholder="e.g. Create a 60s explainer about quantum computing", lines=3)
                with gr.Row():
                    tone_dd = gr.Dropdown(["professional", "casual", "educational", "humorous", "dramatic"], value="professional", label="Tone")
                    lang_dd = gr.Dropdown(["en", "es", "fr", "de", "ar", "zh", "ja", "ko"], value="en", label="Language")
                    dur_slider = gr.Slider(15, 300, value=60, step=15, label="Duration (seconds)")

                with gr.Accordion("Advanced Settings", open=False):
                    with gr.Row():
                        tts_dd = gr.Dropdown(["xtts-v2", "piper", "bark"], value="xtts-v2", label="TTS Engine")
                        avatar_dd = gr.Dropdown(["sadtalker", "musetalk", "heygen", "did"], value="sadtalker", label="Avatar Engine")
                        output_dd = gr.Dropdown(["mp4", "webm", "gif"], value="mp4", label="Output Format")

                    with gr.Row():
                        bg_remove_cb = gr.Checkbox(value=True, label="Remove Background")
                        captions_cb = gr.Checkbox(value=True, label="Auto-Captions")
                        upscale_cb = gr.Checkbox(value=False, label="Upscale to 1080p")
                        music_cb = gr.Checkbox(value=False, label="BG Music")

                    voice_sample = gr.File(label="Voice Sample (for cloning)", file_types=[".wav", ".mp3"])
                    source_files = gr.File(label="Source Documents (PDF, DOCX, XLSX)", file_count="multiple", file_types=[".pdf", ".docx", ".xlsx", ".csv"])

                generate_btn = gr.Button("Generate Video", variant="primary", size="lg")
                status_text = gr.Textbox(label="Status", interactive=False)

            with gr.Column(scale=3):
                video_output = gr.Video(label="Preview", elem_id="preview-video")
                with gr.Row():
                    approve_btn = gr.Button("Approve", variant="primary")
                    rerun_btn = gr.Button("Re-run Selected Segments")
                segment_checkboxes = gr.CheckboxGroup(
                    choices=["script", "visual", "avatar", "enhanced"],
                    label="Segments to Re-run",
                    value=[],
                )
                feedback_text = gr.Textbox(label="Feedback Notes", placeholder="e.g. Make the tone more casual in section 2")
                download_files = gr.File(label="Download Output Files", file_count="multiple")

        # --- State management ---
        current_state = gr.State({})

        def on_generate(prompt, tone, lang, dur, tts, avatar, out_fmt, bg_rem, caps, upscale, music, voice, sources):
            if not prompt.strip():
                return None, "Please enter a prompt.", None, {}

            import tempfile
            overrides = {
                "tone": tone,
                "language": lang,
                "duration_seconds": int(dur),
                "tts_engine": tts,
                "avatar_engine": avatar,
                "output_format": out_fmt,
            }

            if sources:
                overrides["source_files"] = [f.name for f in sources]
            if voice:
                overrides["voice_sample"] = voice.name

            # Update config dynamically
            orchestrator.config["enhancement"]["background"]["remove"] = bg_rem
            orchestrator.config["enhancement"]["captions"]["enabled"] = caps
            orchestrator.config["enhancement"]["quality"]["upscale"] = upscale
            orchestrator.config["enhancement"]["music"]["enabled"] = music

            result = orchestrator.run(prompt, **overrides)

            state = {"result": result, "overrides": overrides}
            if result.success:
                paths = result.segments.get("output", {}).get("files", [])
                return result.output_path, f"Done — {result.output_path}", paths, state
            else:
                return None, f"Failed: {result.error}", None, state

        generate_btn.click(
            fn=on_generate,
            inputs=[prompt_input, tone_dd, lang_dd, dur_slider, tts_dd, avatar_dd, output_dd, bg_remove_cb, captions_cb, upscale_cb, music_cb, voice_sample, source_files],
            outputs=[video_output, status_text, download_files, current_state],
        )

        def on_approve(state):
            return "Approved — video is final.", state

        def on_rerun(segments, feedback, state):
            if not segments:
                return "Select at least one segment to re-run.", state
            result = state.get("result")
            if not result or not result.success:
                return "No video to re-run segments on.", state

            from review.loop import ReviewLoop
            review = ReviewLoop(orchestrator.config)
            fb = {"action": "rerun", "rerun_segments": segments, "notes": feedback}
            review_result = review.process_feedback(fb)
            return f"Re-running segments: {', '.join(segments)}. Notes: {feedback or 'none'}", state

        approve_btn.click(fn=on_approve, inputs=[current_state], outputs=[status_text, current_state])
        rerun_btn.click(fn=on_rerun, inputs=[segment_checkboxes, feedback_text, current_state], outputs=[status_text, current_state])

    app.launch(server_name="0.0.0.0", server_port=port, share=False)
