"""Build web/superchat.html: one self-contained page (engine + data + UI) for the hosted demo link."""
import json, subprocess, sys
from pathlib import Path
W = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(W / "export_tables.py")], check=True)
tables = (W / "tables.json").read_text(encoding="utf-8")
html = (W / "template.html").read_text(encoding="utf-8")
html = html.replace("/*TABLES*/", "window.SUPERCHAT_TABLES = " + tables.replace("</", "<\\/") + ";")
html = html.replace("/*ENGINE*/", (W / "engine.js").read_text(encoding="utf-8"))
(W / "superchat.html").write_text(html, encoding="utf-8")
print("built", len(html), "bytes")
