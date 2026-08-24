#!/usr/bin/env python3
"""Build wild-agents.github.io from the Obsidian vault.

Sources (copied into the repo on each build when the vault is present):
  - Wild Agents — Draft v0.2.md      -> index.html
  - Wild Agents — Argument Breakdown.md -> breakdown.html
  - references.bib (citations rendered via pandoc --citeproc, Chicago author-date)

Usage: python3 build.py
"""
import re
import shutil
import subprocess
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
VAULT = pathlib.Path.home() / "Projects/Oxford/Obsidian/Wild Agents"

SOURCES = {
    "essay.md": "Wild Agents — Draft v0.2.md",
    "references.bib": "references.bib",
}
if (VAULT / SOURCES["essay.md"]).exists():
    for local, vault_name in SOURCES.items():
        shutil.copy(VAULT / vault_name, ROOT / local)

SMALL_WORDS = {"of", "the", "and", "as", "in", "a", "an", "to"}


def title_case(allcaps):
    words = allcaps.strip().split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        out.append(lw if (i > 0 and lw in SMALL_WORDS) else lw.capitalize())
    return " ".join(out)


def pandoc(md, extra):
    r = subprocess.run(
        ["pandoc", "-f", "markdown", "-t", "html", "--wrap=none"] + extra,
        input=md.encode(), capture_output=True, check=True)
    return r.stdout.decode()


def split_sub(rest):
    if ": " in rest:
        t, s = rest.split(": ", 1)
    else:
        t, s = rest, ""
    return t, s


# ---------------------------------------------------------------- essay
essay_md = (ROOT / "essay.md").read_text(encoding="utf-8")
essay_md = "\n".join(ln for ln in essay_md.split("\n")
                     if not ln.startswith("> Draft v0.2 — assembled"))
i = essay_md.find("# References")
essay_md = essay_md[:i] + "# References\n\nNumbered in order of first citation; click a number in the text to jump here.\n\n::: {#refs}\n:::\n"

essay_html = pandoc(essay_md, ["--citeproc", "--bibliography", str(ROOT / "references.bib"),
                               "--csl", str(ROOT / "nature.csl"),
                               "--metadata", "link-citations=true"])

def transform(html, page):
    """Rewrite pandoc headings into styled head blocks; return (html, toc_entries).

    toc_entries: list of (depth, id, kicker, title, sub) in document order.
    """
    toc = []

    # drop the document-title heading
    html = re.sub(r'<h1 id="[^"]*">Wild Agents(?: — Argument Breakdown)?</h1>\n?', "", html, count=1)

    def act_repl(m):
        hid, roman, rest = m.group(1), m.group(2), title_case(m.group(3))
        toc.append((0, hid, f"Act {roman}", rest, ""))
        return (f'<div class="act-head" id="{hid}"><p class="kicker">Act {roman}</p>'
                f'<h2>{rest}</h2></div><!--act-->')
    html = re.sub(r'<h1 id="([^"]+)">ACT ([IVX]+) — ([^<]+)</h1>', act_repl, html)

    def plain_h1_repl(m):
        hid, rest = m.group(1), m.group(2)
        toc.append((0, hid, "", rest, ""))
        return f'<div class="act-head" id="{hid}"><h2>{rest}</h2></div><!--act-->'
    html = re.sub(r'<h1 id="([^"]+)">([^<]+)</h1>', plain_h1_repl, html)

    def ch_repl(m):
        tag, hid, kicker, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        if kicker.startswith("Ch."):
            kicker = "Chapter " + kicker[3:]
        t, s = split_sub(rest)
        depth = 0 if kicker == "Preface" else 1
        toc.append((depth, hid, kicker, t, s))
        htag = "h2" if tag == "h2" else "h3"
        small = "" if tag == "h2" else " small"
        sub = f'<p class="chapter-sub">{s}</p>' if s else ""
        return (f'<div class="chapter-head{small}" id="{hid}">'
                f'<p class="kicker">{kicker}</p><{htag}>{t}</{htag}>{sub}</div>')
    html = re.sub(r'<(h[23]) id="([^"]+)">(Ch\.\d+|Preface) — ([^<]+)</\1>', ch_repl, html)

    if page == "breakdown":
        def part_repl(m):
            hid, n, rest = m.group(1), m.group(2), m.group(3)
            toc.append((0, hid, f"Part {n}", rest, ""))
            return (f'<div class="act-head" id="{hid}"><p class="kicker">Part {n}</p>'
                    f'<h2>{rest}</h2></div><!--act-->')
        html = re.sub(r'<h2 id="([^"]+)">Part (\d+) — ([^<]+)</h2>', part_repl, html)

        def h3_repl(m):
            hid, rest = m.group(1), m.group(2)
            toc.append((1, hid, "", rest, ""))
            return f'<h3 id="{hid}">{rest}</h3>'
        html = re.sub(r'<h3 id="([^"]+)">([^<]+)</h3>', h3_repl, html)

    # act epigraphs: italic line straight after an act head
    html = re.sub(r'<!--act-->\s*<p><em>([^<]+)</em></p>',
                  r'<p class="act-epigraph"><em>\1</em></p>', html)
    html = html.replace("<!--act-->", "")

    # responsive tables
    html = html.replace("<table>", '<div class="table-wrap"><table>')
    html = html.replace("</table>", "</table></div>")
    # regex passes collect entries by kind, not position — restore document order
    toc.sort(key=lambda e: html.find(f'id="{e[1]}"'))
    return html, toc


def toc_entry(hid, kicker, title, sub):
    kick = f'<span class="toc-kicker">{kicker}</span>' if kicker else ""
    subs = f'<span class="toc-sub">{sub}</span>' if sub else ""
    return f'<a href="#{hid}">{kick}<span class="toc-title">{title}</span>{subs}</a>'


def toc_html(entries):
    tree = []
    for d, hid, kicker, title, sub in entries:
        if d == 0 or not tree:
            tree.append([(hid, kicker, title, sub), []])
        else:
            tree[-1][1].append((hid, kicker, title, sub))
    out = ['<ol class="toc-list">']
    for parent, children in tree:
        out.append("<li>" + toc_entry(*parent))
        if children:
            out.append('<ol class="toc-nested">')
            for c in children:
                out.append("<li>" + toc_entry(*c) + "</li>")
            out.append("</ol>")
        out.append("</li>")
    out.append("</ol>")
    return "\n".join(out)


def side_toc_html(entries):
    out = []
    for d, hid, kicker, title, sub in entries:
        if kicker.startswith("Chapter "):
            num = f'<span class="st-num">{kicker[8:]}</span>'
            label = f"{num}{title}"
        elif kicker.startswith("Act "):
            label = f"{kicker} · {title}"
        else:
            label = title
        out.append(f'<a class="st-{d}" href="#{hid}">{label}</a>')
    return "\n".join(out)


essay_html, essay_toc = transform(essay_html, "essay")

template = (ROOT / "template.html").read_text(encoding="utf-8")

HERO_ESSAY = """
  <p class="overline">Draft v0.2 · August 2026</p>
  <h1>Wild&nbsp;Agents</h1>
  <p class="subtitle">A Preemptive Criminology of Feral&nbsp;AI</p>
  <p class="byline"><strong>Botao Amber Hu</strong></p>
  <p class="venue">Drafted for <em>Agentworld</em>, a special issue of the <em>Journal for the Philosophy of Planetary Computation</em> (Antikythera&nbsp;/ MIT&nbsp;Press).</p>
  <span class="draft-tag">Working draft — not final text</span>
"""

pages = [
    ("index.html", "Wild Agents",
     "Wild Agents: A Preemptive Criminology of Feral AI — draft essay by Botao Amber Hu for Agentworld (Antikythera / Journal for the Philosophy of Planetary Computation).",
     "https://wild-agents.github.io/", HERO_ESSAY, essay_toc, essay_html),
]

for fname, title, desc, url, hero, toc, content in pages:
    page = (template
            .replace("{{PAGETITLE}}", title)
            .replace("{{DESC}}", desc)
            .replace("{{URL}}", url)
            .replace("{{HERO}}", hero)
            .replace("{{SIDETOC}}", side_toc_html(toc))
            .replace("{{TOC}}", toc_html(toc))
            .replace("{{CONTENT}}", content))
    (ROOT / fname).write_text(page, encoding="utf-8")
    print(f"Wrote {fname} ({len(page)} bytes), {len(toc)} TOC entries")
