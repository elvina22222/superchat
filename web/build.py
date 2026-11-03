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
head, rest = html.split("<style>", 1)
head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
css, body = rest.split("</style>", 1)
standalone = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              '<meta name="description" content="SuperChat: one chat for flights, shopping and cinema.">\n'
              + head + "<style>\nbody { margin: 0; }\n" + css + "</style>\n</head>\n<body>\n" + body + "\n</body>\n</html>\n")
(W / "index.html").write_text(standalone, encoding="utf-8")
print("built", len(html), "bytes (+ index.html for any static host)")
