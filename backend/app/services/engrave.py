"""Engrave MusicXML into pages anyone can read without notation software.

MusicXML is an interchange format, not a document — reading one means owning an
app that opens it, which is a barrier between a musician and their part. Verovio
engraves it to SVG, and wrapping those pages in a self-contained HTML file makes
the result openable in any browser and printable to PDF from there.

Verovio ships as a pure wheel with no system dependencies, so this costs nothing
at install time. PDF output additionally needs cairosvg and pypdf, which pull in
a system cairo library; that path is optional and degrades to HTML.
"""

from html import escape
from pathlib import Path

import verovio

# A4 at the scale verovio expects, in its own units.
PAGE_WIDTH = 2100
PAGE_HEIGHT = 2970

RENDER_OPTIONS = {
    "pageWidth": PAGE_WIDTH,
    "pageHeight": PAGE_HEIGHT,
    "scale": 38,
    "adjustPageHeight": False,
    "breaks": "auto",
    "header": "auto",
    "footer": "auto",
    "spacingStaff": 10,
}


def render_pages(musicxml_path: Path) -> list[str]:
    """Every page of a score, as standalone SVG markup."""
    toolkit = verovio.toolkit()
    toolkit.setOptions(dict(RENDER_OPTIONS))
    if not toolkit.loadFile(musicxml_path.as_posix()):
        return []
    return [toolkit.renderToSVG(page) for page in range(1, toolkit.getPageCount() + 1)]


def engrave_to_html(musicxml_path: Path, out_path: Path, title: str, subtitle: str = "") -> int:
    """Write the engraved score as one self-contained HTML page.

    Returns the number of pages written, or 0 if the score could not be read.
    """
    pages = render_pages(musicxml_path)
    if not pages:
        return 0

    body = "".join(f'<div class="page">{svg}</div>' for svg in pages)
    header = f"<h1>{escape(title)}</h1>"
    if subtitle:
        header += f"<p class='sub'>{escape(subtitle)}</p>"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<style>{_CSS}</style></head>
<body><header class="sheet-head">{header}
<p class="hint">Print this page to save it as a PDF.</p></header>
{body}
</body></html>""",
        encoding="utf-8",
    )
    return len(pages)


def engrave_to_pdf(musicxml_path: Path, out_path: Path) -> int:
    """Write the engraved score as a PDF, if the optional deps are installed."""
    try:
        import io

        import cairosvg
        import pypdf
    except ImportError:
        return 0

    pages = render_pages(musicxml_path)
    if not pages:
        return 0

    writer = pypdf.PdfWriter()
    for svg in pages:
        buffer = io.BytesIO()
        cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=buffer)
        buffer.seek(0)
        writer.append(pypdf.PdfReader(buffer))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        writer.write(f)
    return len(pages)


# Engraving is black ink on paper, so the score keeps a white background even in
# dark mode; only the surrounding page follows the reader's theme.
_CSS = """
* { box-sizing:border-box; }
body { margin:0; padding:24px; background:#f4f4f5;
       font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; color:#16181c; }
.sheet-head { max-width:1000px; margin:0 auto 20px; }
h1 { font-size:24px; margin:0 0 4px; letter-spacing:-.01em; }
.sub { margin:0; color:#666; font-size:14px; }
.hint { margin:10px 0 0; color:#888; font-size:13px; }
.page { max-width:1000px; margin:0 auto 20px; background:#fff; border:1px solid #ddd;
        border-radius:4px; padding:12px; overflow-x:auto; }
.page svg { display:block; width:100%; height:auto; }
@media (prefers-color-scheme: dark) {
  body { background:#16181c; color:#e8e8e8; }
  .sub, .hint { color:#9aa0a6; }
  .page { background:#fff; border-color:#333; }
}
@media print {
  body { background:#fff; padding:0; }
  .sheet-head { display:none; }
  .page { max-width:none; margin:0; border:none; border-radius:0; padding:0;
          break-after:page; page-break-after:always; }
  .page:last-child { break-after:auto; page-break-after:auto; }
}
"""
