"""Build docs/index.md, the GitHub Pages version of docs/CASE_STUDY.md, from the same text.

    python case_study/build_pages.py                      # writes docs/index.md with the TABLEAU_PUBLIC_URL placeholder
    TABLEAU_PUBLIC_URL=https://public.tableau.com/views/<workbook>/<dashboard> python case_study/build_pages.py

docs/CASE_STUDY.md is the full case study and reads correctly on GitHub as it is (README.md is the short summary).
What changes against it: links (relative links point at the repo on GitHub), the Mermaid diagram (drawn by mermaid.js
in the browser) and the dashboard block (a live Tableau Public embed, with the PNG shown until a real URL is set).
The words are not edited. This script does not turn Pages on or change any repo setting.
"""
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = "https://github.com/mikemoose1/olist-ecommerce-analytics"
PLACEHOLDER = "TABLEAU_PUBLIC_URL"

SOURCE = ROOT / "docs" / "CASE_STUDY.md"
DASHBOARD_BLOCK = re.compile(
    r"\[!\[Dashboard of late deliveries[^\n]*\]\(img/dashboard\.png\)\]\(img/dashboard\.png\)\n\n\*The dashboard in one view\.[^\n]*\*\n"
)

EMBED = """<div id="live-dashboard">
<a id="dashboard-fallback" href="img/dashboard.png"><img src="img/dashboard.png" alt="Dashboard of late deliveries, reviews, sellers, regions and months" style="width:100%"></a>
<tableau-viz id="tableauViz" src="__URL__" width="100%" height="768" hide-tabs toolbar="bottom" style="display:none"></tableau-viz>
<script>
  var viz = document.getElementById("tableauViz");
  if ((viz.getAttribute("src") || "").indexOf("public.tableau.com") !== -1) {
    var lib = document.createElement("script");
    lib.type = "module";
    lib.src = "https://public.tableau.com/javascripts/api/tableau.embedding.3.latest.min.js";
    document.head.appendChild(lib);
    viz.style.display = "block";
    document.getElementById("dashboard-fallback").style.display = "none";
  }
</script>
</div>

*The dashboard in one view. Click a bar or a month to filter the other charts. [Full-size image](img/dashboard.png).*
"""

MERMAID_JS = """<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true });
</script>
"""


def embedded_url(index_text):
    m = re.search(r'<tableau-viz id="tableauViz" src="([^"]*)"', index_text or "")
    return m.group(1) if m else PLACEHOLDER


def _link(m):
    text, target = m.group(1), m.group(2)
    if target.startswith(("http", "#", "mailto", "img/")):
        return m.group(0)
    target = target[3:] if target.startswith("../") else f"docs/{target}"   # links are relative to docs/
    kind = "tree" if target.endswith("/") else "blob"
    return f"[{text}]({REPO}/{kind}/main/{target})"


def render(readme, url=PLACEHOLDER):
    m = DASHBOARD_BLOCK.search(readme)
    if not m:
        raise SystemExit("docs/CASE_STUDY.md has no dashboard image block to turn into the embed")
    text = readme[: m.start()] + EMBED.replace("__URL__", url) + readme[m.end():]
    text = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", _link, text)
    text = re.sub(r"```mermaid\n(.*?)\n```", lambda g: f'<pre class="mermaid">\n{g.group(1)}\n</pre>\n\n{MERMAID_JS}', text, flags=re.S)
    front = "---\nlayout: default\ntitle: Late deliveries and bad reviews at Olist\n---\n\n"
    return front + text


if __name__ == "__main__":
    out = ROOT / "docs" / "index.md"
    url = os.environ.get(PLACEHOLDER) or embedded_url(out.read_text() if out.exists() else "")
    out.write_text(render(SOURCE.read_text(), url))
    (ROOT / "docs" / "_config.yml").write_text("theme: minima\ntitle: Olist late deliveries case study\n")
    print(f"wrote docs/index.md (dashboard embed address: {url})")
