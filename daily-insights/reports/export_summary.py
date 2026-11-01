"""Exports a sync summary report (the Markdown tables) to Word, Excel and PDF next to it.

  python3 reports/export_summary.py reports/sync-summary-2026-11-01.md
"""
import html
import re
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Inches
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


def parse(md):
    """-> title, subtitle, [(heading, header, rows)], notes"""
    lines = md.splitlines()
    title = next(l[2:] for l in lines if l.startswith("# "))
    subtitle = next(l for l in lines[1:] if l.strip() and not l.startswith("#"))
    sections, notes, heading, table = [], [], None, []
    for line in lines:
        if line.startswith("## "):
            heading, table = line[3:], []
            if heading != "Notes":
                sections.append([heading, None, []])
        elif line.startswith("|") and heading != "Notes":
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if sections[-1][1] is None:
                sections[-1][1] = cells
            else:
                sections[-1][2].append(cells)
        elif heading == "Notes" and line.startswith("- "):
            notes.append(line[2:])
        elif heading == "Notes" and line.startswith("  ") and notes:
            notes[-1] += " " + line.strip()
    return title, subtitle, sections, notes


def plain(text):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def is_bold(text):
    return text.startswith("**")


def number(text):
    t = re.sub(r"\s*\(.*\)$", "", plain(text)).replace(",", "")  # '46 (ad sets)' -> 46
    return int(t) if t.isdigit() else plain(text)


def to_excel(path, title, subtitle, sections, notes):
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    head_fill = PatternFill("solid", fgColor="344054")
    total_fill = PatternFill("solid", fgColor="F2F4F7")
    thin = Side(style="thin", color="D0D5DD")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    ws.append([title]); ws["A1"].font = Font(size=16, bold=True)
    ws.append([plain(subtitle)]); ws["A2"].font = Font(italic=True, color="475467")
    for heading, header, rows in sections:
        ws.append([])
        ws.append([heading]); ws.cell(ws.max_row, 1).font = Font(size=13, bold=True)
        ws.append(header)
        for c in ws[ws.max_row]:
            c.font, c.fill, c.border = Font(bold=True, color="FFFFFF"), head_fill, border
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for row in rows:
            ws.append([number(c) for c in row])
            total = plain(row[0]) == "Total"
            for c in ws[ws.max_row][:len(row)]:
                c.border = border
                if isinstance(c.value, int):
                    c.number_format = "#,##0"
                    c.alignment = Alignment(horizontal="right")
                if total or is_bold(row[c.column - 1]):
                    c.font = Font(bold=True)
                if total:
                    c.fill = total_fill
    ws.append([])
    ws.append(["Notes"]); ws.cell(ws.max_row, 1).font = Font(size=13, bold=True)
    for n in notes:
        ws.append([plain(n)])
    ws.column_dimensions["A"].width = 14
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 24
    wb.save(path)


def shade(cell, colour):
    pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), colour)
    pr.append(shd)


def to_word(path, title, subtitle, sections, notes):
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(0.6))
    style = doc.styles["Normal"]; style.font.name = "Calibri"; style.font.size = Pt(10)
    doc.add_heading(title, level=1)
    p = doc.add_paragraph(plain(subtitle)); p.runs[0].italic = True
    for heading, header, rows in sections:
        doc.add_heading(heading, level=2)
        t = doc.add_table(rows=1, cols=len(header))
        t.style = "Table Grid"
        for i, h in enumerate(header):
            cell = t.rows[0].cells[i]
            cell.text = ""
            run = cell.paragraphs[0].add_run(h); run.bold = True; run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            shade(cell, "344054")
        for row in rows:
            cells = t.add_row().cells
            total = plain(row[0]) == "Total"
            for i, value in enumerate(row):
                para = cells[i].paragraphs[0]
                run = para.add_run(plain(value)); run.bold = is_bold(value) or total
                if isinstance(number(value), int) or plain(value) == "–":
                    para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                if total:
                    shade(cells[i], "F2F4F7")
    doc.add_heading("Notes", level=2)
    for n in notes:
        para = doc.add_paragraph(style="List Bullet")
        for part in re.split(r"(\*\*.+?\*\*)", n):
            run = para.add_run(plain(part)); run.bold = part.startswith("**")
    doc.save(path)


def to_pdf(path, title, subtitle, sections, notes):
    bold = lambda s: re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(s))
    parts = [f"<h1>{html.escape(title)}</h1><p class=sub>{bold(subtitle)}</p>"]
    for heading, header, rows in sections:
        parts.append(f"<h2>{html.escape(heading)}</h2><table><tr>" +
                     "".join(f"<th>{html.escape(h)}</th>" for h in header) + "</tr>")
        for row in rows:
            cls = " class=total" if plain(row[0]) == "Total" else ""
            parts.append(f"<tr{cls}>" + "".join(f"<td class=num>{bold(c)}</td>" if isinstance(number(c), int) or plain(c) == "–"
                                         else f"<td>{bold(c)}</td>" for c in row) + "</tr>")
        parts.append("</table>")
    parts.append("<h2>Notes</h2><ul>" + "".join(f"<li>{bold(n)}</li>" for n in notes) + "</ul>")
    page = path.with_suffix(".print.html")
    page.write_text("""<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: A4 landscape; margin: 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; color: #101828; font-size: 11px; }
h1 { font-size: 20px; margin: 0 0 4px; } h2 { font-size: 14px; margin: 18px 0 6px; }
.sub { color: #475467; font-style: italic; margin: 0 0 6px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #D0D5DD; padding: 5px 8px; }
th { background: #344054; color: #fff; text-align: center; }
td.num { text-align: right; }
h2 { break-after: avoid; } table { break-inside: avoid; }
tr.total td { background: #F2F4F7; font-weight: 700; }
li { margin: 3px 0; }
</style></head><body>""" + "".join(parts) + "</body></html>", encoding="utf-8")
    script = """
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + process.argv[1]); await p.pdf({ path: process.argv[2], preferCSSPageSize: true, printBackground: true });
  await b.close();
})();"""
    subprocess.run(["node", "-e", script, str(page.resolve()), str(path.resolve())], check=True)
    page.unlink()


def main(md_path):
    md = Path(md_path)
    data = parse(md.read_text(encoding="utf-8"))
    to_excel(md.with_suffix(".xlsx"), *data)
    to_word(md.with_suffix(".docx"), *data)
    to_pdf(md.with_suffix(".pdf"), *data)
    for ext in (".xlsx", ".docx", ".pdf"):
        print(md.with_suffix(ext))


if __name__ == "__main__":
    main(sys.argv[1])
