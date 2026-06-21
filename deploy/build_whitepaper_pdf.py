"""
Build a clean, professional PDF of the Lattice Network whitepaper.

Reads /app/deploy/WHITEPAPER.md, parses the markdown structure (headings,
paragraphs, lists, tables, code), and renders it via ReportLab.
Output: /app/frontend/public/whitepaper.pdf
"""
from __future__ import annotations
import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY

SRC_DOCS = [
    ("/app/deploy/WHITEPAPER.md", "/app/frontend/public/whitepaper.pdf",
     "Lattice Network · Whitepaper Tecnico",
     "Infrastruttura sovrana di comunicazione aziendale<br/>post-quantistica · auto-ospitata · senza dipendenze terze"),
    ("/app/deploy/SECURITY-AUDIT.md", "/app/frontend/public/security-audit.pdf",
     "Lattice Network · Security Audit Interno",
     "Audit del layer blockchain · 9 vulnerabilità identificate e chiuse<br/>con 8 test automatici di regressione"),
]

# --- Brand palette (matches the React UI) ---------------------------------
GOLD = HexColor("#D4AF37")
INK = HexColor("#0B0E13")
PAPER = HexColor("#F8F6EF")     # warm cream
INK_2 = HexColor("#2A2F36")
INK_3 = HexColor("#5A6068")
RULE = HexColor("#C9B97C")


def _frame(canvas, doc):
    """Header + footer on every page."""
    w, h = A4
    # subtle hairline
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, h - 1.6 * cm, w - 2 * cm, h - 1.6 * cm)
    canvas.line(2 * cm, 1.5 * cm, w - 2 * cm, 1.5 * cm)
    # header label
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_3)
    canvas.drawString(2 * cm, h - 1.2 * cm, "LATTICE NETWORK · WHITEPAPER TECNICO · v1.0")
    canvas.drawRightString(w - 2 * cm, h - 1.2 * cm, "Giugno 2026")
    # footer page number
    canvas.drawCentredString(w / 2, 1.1 * cm, f"— {doc.page} —")
    canvas.drawString(2 * cm, 1.1 * cm, "lattice.id")
    canvas.drawRightString(w - 2 * cm, 1.1 * cm, "Confidential / Commercial Material")


def build_styles():
    base = getSampleStyleSheet()
    base["BodyText"].fontName = "Helvetica"
    base["BodyText"].fontSize = 9.8
    base["BodyText"].leading = 14
    base["BodyText"].alignment = TA_JUSTIFY
    base["BodyText"].textColor = INK_2
    base["BodyText"].spaceAfter = 6

    styles = {
        "Body": base["BodyText"],
        "H1": ParagraphStyle(
            "H1", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=24, leading=30, textColor=INK, spaceBefore=18,
            spaceAfter=10,
        ),
        "H2": ParagraphStyle(
            "H2", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=14, leading=20, textColor=INK, spaceBefore=16,
            spaceAfter=6,
        ),
        "H3": ParagraphStyle(
            "H3", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=11.5, leading=16, textColor=INK_2, spaceBefore=10,
            spaceAfter=4,
        ),
        "Subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=10, leading=14, textColor=INK_3, alignment=TA_LEFT,
            spaceBefore=4, spaceAfter=24,
        ),
        "Eyebrow": ParagraphStyle(
            "Eyebrow", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8, leading=11, textColor=GOLD, spaceBefore=0,
            spaceAfter=2,
        ),
        "Code": ParagraphStyle(
            "Code", parent=base["Normal"], fontName="Courier",
            fontSize=8.6, leading=11, textColor=INK_2, leftIndent=12,
            spaceBefore=2, spaceAfter=2,
        ),
        "Bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"], leftIndent=14, bulletIndent=2,
            spaceAfter=2,
        ),
        "Cover": ParagraphStyle(
            "Cover", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=36, leading=42, textColor=INK, spaceAfter=10,
        ),
        "CoverSub": ParagraphStyle(
            "CoverSub", parent=base["Normal"], fontName="Helvetica",
            fontSize=13, leading=18, textColor=INK_3, spaceAfter=4,
        ),
    }
    return styles


# Inline markdown → reportlab markup (very small subset: **bold**, *italic*, `code`)
def _inline(s: str) -> str:
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`([^`]+?)`", r'<font face="Courier" color="#2A2F36">\1</font>', s)
    s = re.sub(r"(?<!\*)\*([^\*]+?)\*(?!\*)", r"<i>\1</i>", s)
    return s


def parse_markdown(md: str):
    """Yield (kind, payload) tuples for the structured renderer."""
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("# "):
            yield ("h1", ln[2:].strip())
        elif ln.startswith("## "):
            yield ("h2", ln[3:].strip())
        elif ln.startswith("### "):
            yield ("h3", ln[4:].strip())
        elif ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i+1]):
            # table
            rows = [ln]
            i += 1  # skip separator
            while i + 1 < len(lines) and lines[i + 1].startswith("|"):
                i += 1
                rows.append(lines[i])
            yield ("table", rows)
        elif ln.startswith("- ") or ln.startswith("* "):
            items = [ln[2:].strip()]
            while i + 1 < len(lines) and (lines[i+1].startswith("- ") or lines[i+1].startswith("* ")):
                i += 1
                items.append(lines[i][2:].strip())
            yield ("ul", items)
        elif re.match(r"^\d+\.\s", ln):
            items = [re.sub(r"^\d+\.\s+", "", ln)]
            while i + 1 < len(lines) and re.match(r"^\d+\.\s", lines[i+1]):
                i += 1
                items.append(re.sub(r"^\d+\.\s+", "", lines[i]))
            yield ("ol", items)
        elif ln.startswith("---"):
            yield ("hr", None)
        elif ln.strip() == "":
            yield ("blank", None)
        else:
            # paragraph: join continued lines
            buf = [ln]
            while i + 1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(("#", "-", "*", "|", "    ")) and not re.match(r"^\d+\.\s", lines[i+1]):
                i += 1
                buf.append(lines[i].rstrip())
            yield ("p", " ".join(buf).strip())
        i += 1


def render_table(rows, styles):
    parsed = []
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        parsed.append(cells)
    # First row is header
    header = parsed[0]
    body = parsed[1:]
    data = [[Paragraph(f"<b>{_inline(c)}</b>", styles["Body"]) for c in header]]
    for r in body:
        data.append([Paragraph(_inline(c) if c else "—", styles["Body"]) for c in r])
    tbl = Table(data, hAlign="LEFT", colWidths=None, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#EAE0BC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, RULE),
        ("LINEABOVE", (0, 0), (-1, 0), 0.4, RULE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def build_one(src_path: str, out_path: str, cover_title: str, cover_sub: str):
    with open(src_path, "r", encoding="utf-8") as fh:
        md = fh.read()
    md = re.sub(r"^# [^\n]+\n+\*\*[^\n]+\*\*\n+---\n+", "", md, count=1)
    styles = build_styles()
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
        title=cover_title, author="Lattice Network",
        subject="Sovereign B2B Post-Quantum Communication Infrastructure",
    )
    story = []
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("LATTICE NETWORK", styles["Eyebrow"]))
    story.append(Paragraph(cover_title.split("·")[-1].strip(), styles["Cover"]))
    story.append(Paragraph(cover_sub, styles["CoverSub"]))
    story.append(Spacer(1, 3.5 * cm))
    cover_meta = Table([
        [Paragraph("<b>Versione</b>", styles["Body"]), Paragraph("1.0", styles["Body"])],
        [Paragraph("<b>Data</b>", styles["Body"]), Paragraph("Giugno 2026", styles["Body"])],
        [Paragraph("<b>Algoritmo firma</b>", styles["Body"]), Paragraph("ML-DSA-65 · NIST FIPS 204", styles["Body"])],
        [Paragraph("<b>Consenso</b>", styles["Body"]), Paragraph("QBFT · 2f+1", styles["Body"])],
        [Paragraph("<b>Licenza core</b>", styles["Body"]), Paragraph("BSL 1.1 → Apache 2.0", styles["Body"])],
    ], colWidths=[5 * cm, 11 * cm])
    cover_meta.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(cover_meta)
    story.append(PageBreak())
    h2s = [ln[3:].strip() for ln in md.split("\n") if ln.startswith("## ")]
    if h2s:
        story.append(Paragraph("INDICE", styles["Eyebrow"]))
        story.append(Paragraph("Sommario", styles["H1"]))
        story.append(Spacer(1, 0.3 * cm))
        for i, h in enumerate(h2s, 1):
            story.append(Paragraph(f"{i}. {_inline(h)}", styles["Body"]))
        story.append(PageBreak())
    for kind, payload in parse_markdown(md):
        if kind == "h1":
            story.append(Paragraph(_inline(payload), styles["H1"]))
        elif kind == "h2":
            story.append(Spacer(1, 4))
            story.append(Paragraph(_inline(payload), styles["H2"]))
        elif kind == "h3":
            story.append(Paragraph(_inline(payload), styles["H3"]))
        elif kind == "p":
            story.append(Paragraph(_inline(payload), styles["Body"]))
        elif kind == "ul":
            for it in payload:
                story.append(Paragraph(f"• {_inline(it)}", styles["Bullet"]))
        elif kind == "ol":
            for idx, it in enumerate(payload, 1):
                story.append(Paragraph(f"{idx}. {_inline(it)}", styles["Bullet"]))
        elif kind == "table":
            story.append(Spacer(1, 4))
            story.append(KeepTogether(render_table(payload, styles)))
            story.append(Spacer(1, 8))
        elif kind == "hr":
            story.append(Spacer(1, 6))
    doc.build(story, onFirstPage=_frame, onLaterPages=_frame)
    print(f"PDF written to {out_path} · size={os.path.getsize(out_path)} bytes")


def build():
    for src, out, title, sub in SRC_DOCS:
        build_one(src, out, title, sub)


if __name__ == "__main__":
    build()
