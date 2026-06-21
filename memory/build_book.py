#!/usr/bin/env python3
"""Build LATTICE — libro completo DOCX + PDF, con immagini integrate."""
import re
import subprocess
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.style import WD_STYLE_TYPE

SRC = Path("/app/memory/book_src")
IMG = Path("/app/memory/book_img")
OUT_DOCX = Path("/app/memory/LATTICE_LIBRO_COMPLETO.docx")
OUT_PDF = Path("/app/memory/LATTICE_LIBRO_COMPLETO.pdf")

# Mapping marker → image filename
FIG_MAP = {
    "1.1": "fig_1_1_qday_timeline.png",
    "4.1": "fig_4_1_sovranita.png",
    "7.1": "fig_7_1_architettura.png",
    "7.2": "fig_7_2_rust_stack.png",
    "8.1": "fig_8_1_confronto_algo.png",
    "9.1": "fig_9_1_qbft.png",
    "9.2": "fig_9_2_loopix.png",
    "10.1": "fig_10_1_pec_vs_certify.png",
    "13.1": "fig_13_1_roi.png",
}

# Palette
NAVY = RGBColor(0x0A, 0x0F, 0x1E)
GOLD = RGBColor(0xD4, 0xAF, 0x37)
GREY = RGBColor(0x55, 0x55, 0x55)
DARK = RGBColor(0x1A, 0x1A, 0x1A)

doc = Document()

for section in doc.sections:
    section.page_height = Cm(22.86); section.page_width = Cm(15.24)
    section.top_margin = Cm(2.2); section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(1.8); section.right_margin = Cm(1.8)

styles = doc.styles
body = styles['Normal']
body.font.name = 'Garamond'; body.font.size = Pt(11)
body.paragraph_format.first_line_indent = Cm(0.5)
body.paragraph_format.space_after = Pt(2)
body.paragraph_format.line_spacing = 1.25

def make_style(name, size, bold, color, alignment=WD_ALIGN_PARAGRAPH.LEFT, italic=False):
    if name in [s.name for s in styles]:
        return styles[name]
    s = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    s.font.name = 'Garamond' if not bold else 'Helvetica'
    s.font.size = Pt(size); s.font.bold = bold; s.font.italic = italic
    s.font.color.rgb = color
    s.paragraph_format.alignment = alignment
    s.paragraph_format.space_before = Pt(18); s.paragraph_format.space_after = Pt(12)
    s.paragraph_format.first_line_indent = Cm(0)
    return s

ChapterTitle = make_style('ChapterTitle', 22, True, NAVY)
SectionH = make_style('SectionH', 14, True, NAVY)
SubsectionH = make_style('SubsectionH', 12, True, GOLD)
Quote = make_style('Quote', 11, False, GREY, italic=True)

def add_page_break():
    p = doc.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)

def format_inline(run_target, text):
    parts = re.split(r'(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)', text)
    for p in parts:
        if not p: continue
        if p.startswith('**') and p.endswith('**'):
            r = run_target.add_run(p[2:-2]); r.bold = True
        elif p.startswith('*') and p.endswith('*'):
            r = run_target.add_run(p[1:-1]); r.italic = True
        elif p.startswith('`') and p.endswith('`'):
            r = run_target.add_run(p[1:-1]); r.font.name = 'Courier New'; r.font.size = Pt(9)
        else:
            run_target.add_run(p)

def add_para_inline(text, style=None, alignment=None):
    p = doc.add_paragraph(style=style)
    if alignment is not None: p.alignment = alignment
    format_inline(p, text)
    return p

def insert_figure(fig_id):
    """Insert image fig_id (e.g. '7.1') centered with caption."""
    fname = FIG_MAP.get(fig_id)
    if not fname: return
    path = IMG / fname
    if not path.exists():
        return
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run()
    r.add_picture(str(path), width=Cm(11))

def render_markdown(md_text):
    lines = md_text.split('\n')
    i = 0
    in_table = False; table_rows = []
    while i < len(lines):
        line = lines[i]; stripped = line.strip()
        # Strip code blocks completely (sensibility)
        if stripped.startswith('```'):
            # skip until next ```
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            i += 1
            continue
        # Figure markers
        m = re.match(r'\[FIGURA\s+([\d.]+)\s*[—\-]', stripped)
        if m:
            insert_figure(m.group(1))
            i += 1
            continue
        # Tables (GFM)
        if '|' in line and stripped.startswith('|'):
            if not in_table: in_table = True; table_rows = []
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if cells and all(set(c) <= set('-: ') for c in cells if c):
                i += 1; continue
            table_rows.append(cells)
            i += 1; continue
        elif in_table:
            if table_rows:
                tbl = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
                tbl.style = 'Light Grid Accent 1'
                for r_idx, row in enumerate(table_rows):
                    for c_idx, cell_txt in enumerate(row):
                        if c_idx < len(tbl.rows[r_idx].cells):
                            cell = tbl.rows[r_idx].cells[c_idx]
                            cell.text = ''
                            p = cell.paragraphs[0]
                            p.paragraph_format.first_line_indent = Cm(0)
                            format_inline(p, cell_txt)
                            for run in p.runs:
                                if r_idx == 0: run.bold = True
                                run.font.size = Pt(9)
            in_table = False; table_rows = []
            doc.add_paragraph()
        # Headings
        if stripped.startswith('# '):
            add_page_break()
            p = doc.add_paragraph(style=ChapterTitle); p.add_run(stripped[2:].strip())
        elif stripped.startswith('## '):
            p = doc.add_paragraph(style=SectionH); p.add_run(stripped[3:].strip())
        elif stripped.startswith('### '):
            p = doc.add_paragraph(style=SubsectionH); p.add_run(stripped[4:].strip())
        elif stripped.startswith('> '):
            add_para_inline(stripped[2:], style=Quote)
        elif stripped.startswith('- ') or stripped.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            p.paragraph_format.first_line_indent = Cm(0)
            format_inline(p, stripped[2:])
        elif re.match(r'^\d+\.\s', stripped):
            p = doc.add_paragraph(style='List Number')
            p.paragraph_format.first_line_indent = Cm(0)
            format_inline(p, re.sub(r'^\d+\.\s', '', stripped))
        elif stripped == '':
            pass
        elif stripped.startswith('---'):
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run('— · —'); r.font.color.rgb = GOLD
        else:
            add_para_inline(stripped)
        i += 1

# === COVER PAGE ===
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.first_line_indent = Cm(0)
r = p.add_run()
cover = IMG / "00_cover.png"
if cover.exists():
    r.add_picture(str(cover), width=Cm(13))
else:
    p.paragraph_format.space_before = Cm(5)
    r = p.add_run('LATTICE')
    r.font.size = Pt(48); r.font.bold = True; r.font.color.rgb = NAVY

add_page_break()

# === COPYRIGHT ===
p = doc.add_paragraph()
p.paragraph_format.first_line_indent = Cm(0)
p.paragraph_format.space_before = Cm(8)
r = p.add_run('© 2026 — Lattice Network. Tutti i diritti riservati.\n\n')
r.font.size = Pt(9); r.font.color.rgb = GREY
p = doc.add_paragraph()
p.paragraph_format.first_line_indent = Cm(0)
r = p.add_run(
    "Quest'opera è pubblicata in self-publishing su Amazon KDP. "
    "È vietata la riproduzione, anche parziale, con qualsiasi mezzo, "
    "senza autorizzazione scritta dell'editore.\n\n"
    "I marchi citati (ML-DSA, ML-KEM, NIST, FIPS, Signal, WhatsApp, "
    "Microsoft, Google, AWS, Bitcoin, OpenTimestamps, ecc.) appartengono "
    "ai rispettivi proprietari e sono usati a scopo esclusivamente "
    "descrittivo e formativo.\n\n"
    "Le citazioni di casi reali nei capitoli 5, 10, 11 e 13 sono basate "
    "su situazioni effettive ma anonimizzate. Nomi, date e dettagli "
    "identificativi sono stati modificati per ragioni di riservatezza "
    "commerciale e di sicurezza informatica.\n\n"
    "ISBN: assegnato in fase di pubblicazione KDP.\n"
    "Prima edizione: 2026 · Lingua: italiano · Formato: paperback 15.24 × 22.86 cm."
)
r.font.size = Pt(9); r.font.color.rgb = GREY
add_page_break()

# === INDICE ===
p = doc.add_paragraph(style=ChapterTitle)
p.add_run('INDICE'); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
toc = [
    ('PREFAZIONE', None),
    ('EXECUTIVE SUMMARY · Per CEO, CISO, Legal', None),
    ('', None),
    ('PARTE I — IL PROBLEMA REALE', None),
    ('  Capitolo 1 — Le comunicazioni aziendali sono fuori controllo', None),
    ("  Capitolo 2 — Perché l'Italia è esposta più di chiunque altro", None),
    ('  Capitolo 3 — Anatomia di un attacco "Harvest Now, Decrypt Later"', None),
    ('', None),
    ('PARTE II — LA SOVRANITÀ', None),
    ('  Capitolo 4 — Cosa significa davvero "sovrano" nel software', None),
    ('  Capitolo 5 — Cloud pubblico, SaaS estero e il mito del "private link"', None),
    ('  Capitolo 6 — Self-hosting e on-premise come scelta strategica', None),
    ('', None),
    ('PARTE III — LATTICE NETWORK', None),
    ("  Capitolo 7 — L'architettura di Lattice Network", None),
    ('  Capitolo 7B — Block Explorer pubblico e Gateway Delegation', None),
    ('  Capitolo 8 — ML-DSA-65 e ML-KEM-768: i nuovi standard NIST', None),
    ('  Capitolo 9 — QBFT, Loopix, Zero-Knowledge', None),
    ('  Capitolo 10 — Certify: la PEC sovrana', None),
    ('  Capitolo 11 — Pulse: la chat sovrana stile Signal', None),
    ('', None),
    ('PARTE IV — COMPLIANCE E CASI', None),
    ('  Capitolo 12 — NIS2, DORA, GDPR: la mappa di conformità', None),
    ("  Capitolo 13 — Casi d'uso reali", None),
    ("  Capitolo 14 — Roadmap dell'autosovranità", None),
    ('', None),
    ('APPENDICI', None),
    ('  A. Glossario tecnico', None),
    ('  B. Come verificare indipendentemente una ricevuta Certify', None),
    ('  C. Specifica del formato della ricevuta PEC court-grade', None),
    ('  D. Bibliografia', None),
    ('  E. Il Manifesto Lattice (12 principi)', None),
]
for entry, _ in toc:
    if entry.startswith('PARTE') or entry == 'PREFAZIONE' or entry == 'APPENDICI':
        p = doc.add_paragraph(); p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_before = Pt(6)
        r = p.add_run(entry); r.bold = True; r.font.color.rgb = NAVY; r.font.size = Pt(11)
    elif entry == '':
        doc.add_paragraph()
    else:
        p = doc.add_paragraph(); p.paragraph_format.first_line_indent = Cm(0)
        r = p.add_run(entry); r.font.size = Pt(10)

# === RENDER ===
files_in_order = [
    'ch00_prefazione.md', 'ch00b_executive_summary.md', 'ch01_qday.md', 'ch02_italia_esposta.md',
    'ch03_anatomia_attacco.md', 'ch04_sovrano_software.md', 'ch05_cloud_mito.md',
    'ch06_self_hosting.md', 'ch07_architettura.md', 'ch07b_explorer_gateway.md', 'ch08_ml_dsa.md',
    'ch09_qbft_loopix_zk.md', 'ch10_certify.md', 'ch11_pulse.md',
    'ch12_compliance.md', 'ch13_casi_uso.md', 'ch14_roadmap.md',
    'ch99_appendici.md',
]
for fname in files_in_order:
    md = (SRC / fname).read_text(encoding='utf-8')
    render_markdown(md)

# === MANIFESTO PAGE (ultima) ===
add_page_break()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.first_line_indent = Cm(0)
r = p.add_run()
manif = IMG / "fig_E_manifesto.png"
if manif.exists():
    r.add_picture(str(manif), width=Cm(13))

# === COLOPHON ===
add_page_break()
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.first_line_indent = Cm(0)
p.paragraph_format.space_before = Cm(8)
r = p.add_run('LATTICE NETWORK')
r.font.size = Pt(14); r.font.bold = True; r.font.color.rgb = NAVY
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.first_line_indent = Cm(0)
r = p.add_run('Corporate Communication Control Layer · post-quantum · self-hosted')
r.font.size = Pt(10); r.font.italic = True; r.font.color.rgb = GOLD
p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.first_line_indent = Cm(0)
p.paragraph_format.space_before = Cm(1)
r = p.add_run('Per richiedere un pilot, contattare:\nlattice@network.it\n\nCodice promo "BOOK-2026": 30 giorni di pilot gratis.')
r.font.size = Pt(10); r.font.color.rgb = DARK

doc.save(OUT_DOCX)
print(f"OK · {OUT_DOCX.stat().st_size//1024} KB · {OUT_DOCX}")

# === CONVERT TO PDF ===
print("Conversione in PDF via LibreOffice…")
result = subprocess.run([
    'libreoffice', '--headless', '--convert-to', 'pdf',
    '--outdir', str(OUT_DOCX.parent), str(OUT_DOCX)
], capture_output=True, text=True, timeout=180)
print(result.stdout[-500:] if result.stdout else "")
if result.returncode == 0 and OUT_PDF.exists():
    print(f"OK · PDF {OUT_PDF.stat().st_size//1024} KB · {OUT_PDF}")
else:
    print(f"PDF conversion error: {result.stderr[-300:]}")
