#!/usr/bin/env python3
"""Regenerate docs/mobile_handoff.pdf from docs/mobile_handoff.md.

Pure-Python pipeline (no system deps): markdown -> HTML -> PDF via xhtml2pdf.

    ./venv/bin/pip install markdown xhtml2pdf
    ./venv/bin/python scripts/gen_mobile_handoff_pdf.py
"""

import os
import re
import sys

import markdown
from xhtml2pdf import pisa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "mobile_handoff.md")
OUT = os.path.join(ROOT, "docs", "mobile_handoff.pdf")

CSS = """
@page { size: letter; margin: 0.8in 0.75in;
        @frame footer { -pdf-frame-content: footer; bottom: 0.4in; height: 0.3in; } }
body { font-family: Helvetica, Arial, sans-serif; font-size: 9.5pt; line-height: 1.4; color: #1c2230; }
h1 { font-size: 20pt; margin: 0 0 6pt; color: #0f766e; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; padding-top: 6pt; border-top: 1px solid #dde1e8; color: #1c2230; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; }
h4 { font-size: 10pt; margin: 10pt 0 3pt; }
p { margin: 0 0 6pt; }
ul, ol { margin: 0 0 6pt 14pt; }
li { margin: 0 0 2pt; }
code { font-family: Courier, monospace; font-size: 8.5pt; background: #eef1f5; }
pre { font-family: Courier, monospace; font-size: 8pt; background: #eef1f5; padding: 6pt;
      margin: 4pt 0 8pt; border: 1px solid #dde1e8; white-space: pre-wrap; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 10pt; font-size: 8.5pt; }
th, td { border: 1px solid #c9ced8; padding: 3pt 5pt; vertical-align: top; }
th { background: #e2f3f0; text-align: left; }
hr { border: 0; border-top: 1px solid #dde1e8; margin: 10pt 0; }
blockquote { margin: 4pt 0 8pt 8pt; padding-left: 8pt; border-left: 3px solid #0f766e; color: #4b5468; }
#footer { font-size: 7.5pt; color: #7b8498; text-align: center; }
"""


def build() -> int:
    text = open(SRC, encoding="utf-8").read()
    # GitHub-style task lists -> plain checkboxes xhtml2pdf can draw
    text = re.sub(r"^(\s*)- \[ \] ", r"\1- ☐ ", text, flags=re.M)
    text = re.sub(r"^(\s*)- \[x\] ", r"\1- ☑ ", text, flags=re.M | re.I)
    html_body = markdown.markdown(
        text, extensions=["tables", "fenced_code", "sane_lists", "toc"],
        output_format="xhtml")
    html = (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f"{html_body}<div id='footer'>Voice Orchestrator — Mobile Developer Handoff · "
            f"generated from docs/mobile_handoff.md</div></body></html>")
    with open(OUT, "wb") as fh:
        result = pisa.CreatePDF(html, dest=fh, encoding="utf-8")
    if result.err:
        print(f"xhtml2pdf reported {result.err} error(s)", file=sys.stderr)
        return 1
    print(f"wrote {OUT} ({os.path.getsize(OUT):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(build())
