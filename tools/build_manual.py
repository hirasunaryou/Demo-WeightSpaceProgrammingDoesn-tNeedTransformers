"""Produce a truly portable HTML guide (no CSS/image dependencies).

Only documentation CI needs a browser. The ordinary app uses the Python
standard library and the real, copied MIT-licensed source fact rows.
"""
import base64
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"
INPUT=DOCS/"MANUAL.source.html"
STYLES=DOCS/"manual.css"
OUTPUT=DOCS/"MANUAL.html"
MARKER="<!--EMBED_STYLES-->"
REGEX=re.compile(r'(?P<start>src=")(?P<path>(?:images/|\.\./assets/)[a-zA-Z0-9_-]+\.png)"')


def render():
    text=INPUT.read_text(encoding="utf-8")
    if text.count(MARKER)!=1:
        raise RuntimeError("Missing exactly one standalone CSS marker")
    css=STYLES.read_text(encoding="utf-8")
    text=text.replace(MARKER,"<style>\n"+css+"\n</style>")
    seen=set()
    def inline(match):
        rel=match.group("path")
        file=(DOCS/rel).resolve()
        if (ROOT not in file.parents or not file.is_file()):
            raise RuntimeError("Missing verified image: "+rel)
        seen.add(rel)
        return match.group("start")+"data:image/png;base64,"+base64.b64encode(file.read_bytes()).decode("ascii")+'"'
    text=REGEX.sub(inline,text)
    required={"images/overview.png","images/ablation.png",
              "../assets/original_architecture.png","../assets/original_teaser.png"}
    if not required.issubset(seen):
        raise RuntimeError("Missing original illustrations or REAL captured UI screenshots: "+str(required-seen))
    if 'src="images/' in text or 'src="../assets/' in text or 'href="manual.css"' in text:
        raise RuntimeError("Standalone manual contains unembedded assets")
    return "<!-- GENERATED: edit MANUAL.source.html and manual.css, not this file. -->\n"+text


def main():
    result=render()
    if "--check" in sys.argv:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8")!=result:
            raise SystemExit("Portable HTML is stale. Re-run python tools/build_manual.py")
        print("Standalone manual verified:",len(result),"characters")
    else:
        OUTPUT.write_text(result,encoding="utf-8")
        print("Generated portable HTML:",OUTPUT, len(result),"characters")


if __name__=="__main__":
    main()
