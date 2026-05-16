"""SKILL: pdf — Produce storyboard briefs and shot lists."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


def build_storyboard(segments: list[dict], shot_list: list[str], output_path: str, title: str = "Storyboard"):
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    body_style = styles["Normal"]

    elements = [Paragraph(title, title_style), Spacer(1, 12)]

    for i, seg in enumerate(segments):
        seg_id = seg.get("id", f"seg_{i}")
        text = seg.get("text", "")
        dur = seg.get("duration_hint", 0)
        shot = shot_list[i] if i < len(shot_list) else "—"

        elements.append(Paragraph(f"Segment: {seg_id} ({dur}s)", heading_style))
        elements.append(Paragraph(f"<b>Shot:</b> {shot}", body_style))
        elements.append(Paragraph(f"<b>Narration:</b> {text}", body_style))
        elements.append(Spacer(1, 8))

    doc.build(elements)
