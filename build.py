#!/usr/bin/env python3
"""Build index.html for wild-agents.github.io from content.md.

Usage: python3 build.py
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "content.md"


def slugify(text):
    text = re.sub(r"[—–:.,'’?()/★\[\]]", " ", text)
    text = re.sub(r"\s+", "-", text.strip().lower())
    return re.sub(r"[^a-z0-9\-]", "", text).strip("-")


def inline(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*\s][^*]*)\*", r"<em>\1</em>", text)
    return text


lines = SRC.read_text(encoding="utf-8").split("\n")

# --- lead paragraph: text between the "# " title and the first "## " ---
first_h2 = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
lead = " ".join(ln.strip() for ln in lines[1:first_h2] if ln.strip())
lead_html = inline(lead)

sections = []   # {kicker, title, sub, id}
out = []

in_section = False
in_ul = False
in_ol = False
in_li = False
aside_label = None
aside_paras = []


def close_ol():
    global in_ol
    if in_ol:
        out.append("</ol>")
        in_ol = False


def close_li():
    global in_li
    close_ol()
    if in_li:
        out.append("</li>")
        in_li = False


def close_ul():
    global in_ul
    close_li()
    if in_ul:
        out.append("</ul>")
        in_ul = False


def close_aside():
    global aside_label, aside_paras
    if aside_label is not None:
        out.append('<aside class="note">')
        out.append(f'<p class="note-label">{aside_label}</p>')
        for p in aside_paras:
            out.append(f"<p>{p}</p>")
        out.append("</aside>")
        aside_label = None
        aside_paras = []


for raw in lines[first_h2:]:
    ln = raw.rstrip()
    if ln.startswith("## "):
        close_ul()
        close_aside()
        if in_section:
            out.append("</section>")
        head = ln[3:].strip()
        m = re.match(r"^Ch\.(\d+)\s+—\s+(.*)$", head)
        if m:
            kicker = f"Chapter {m.group(1)}"
            rest = m.group(2)
        else:
            kicker = ""
            rest = head
        if ": " in rest:
            title, sub = rest.split(": ", 1)
        else:
            title, sub = rest, ""
        sid = slugify(("ch-" + m.group(1) + "-" if m else "") + title)
        sections.append({"kicker": kicker, "title": title, "sub": sub, "id": sid})
        out.append(f'<section class="chapter" id="{sid}">')
        out.append('<header class="chapter-head">')
        if kicker:
            out.append(f'<p class="kicker">{inline(kicker)}</p>')
        out.append(f"<h2>{inline(title)}</h2>")
        if sub:
            out.append(f'<p class="chapter-sub">{inline(sub)}</p>')
        out.append("</header>")
        in_section = True
    elif re.match(r"^- ", ln):
        close_aside()
        close_li()
        if not in_ul:
            out.append('<ul class="claims">')
            in_ul = True
        text = ln[2:].strip()
        cls = ""
        if text.startswith("★"):
            cls = ' class="star"'
            text = text.lstrip("★").strip()
        out.append(f"<li{cls}><p>{inline(text)}</p>")
        in_li = True
    elif re.match(r"^\s+\d+\.\s", ln):
        m2 = re.match(r"^\s+\d+\.\s+(.*)$", ln)
        if not in_ol:
            out.append('<ol class="strategies">')
            in_ol = True
        out.append(f"<li><p>{inline(m2.group(1))}</p></li>")
    elif re.match(r"^(Comment|Cool Quotes)\s*:", ln.strip()):
        close_ul()
        close_aside()
        label = ln.strip().split(":")[0]
        aside_label = label
        rest = ln.strip().split(":", 1)[1].strip()
        if rest:
            aside_paras.append(inline(rest))
    elif ln.strip():
        if aside_label is not None:
            aside_paras.append(inline(ln.strip()))
        else:
            close_ul()
            out.append(f"<p>{inline(ln.strip())}</p>")
    # blank lines: no-op (paragraph breaks inside asides are per-line already)

close_ul()
close_aside()
if in_section:
    out.append("</section>")
content = "\n".join(out)

# --- TOC ---
toc = ['<ol class="toc-list">']
for s in sections:
    kick = f'<span class="toc-kicker">{s["kicker"]}</span>' if s["kicker"] else ""
    sub = f'<span class="toc-sub">{inline(s["sub"])}</span>' if s["sub"] else ""
    toc.append(f'<li><a href="#{s["id"]}">{kick}<span class="toc-title">'
               f'{inline(s["title"])}</span>{sub}</a></li>')
toc.append("</ol>")
toc_html = "\n".join(toc)

template = (ROOT / "template.html").read_text(encoding="utf-8")
page = (template
        .replace("{{LEAD}}", lead_html)
        .replace("{{TOC}}", toc_html)
        .replace("{{CONTENT}}", content))
(ROOT / "index.html").write_text(page, encoding="utf-8")
print(f"Wrote index.html ({len(page)} bytes), {len(sections)} sections")
