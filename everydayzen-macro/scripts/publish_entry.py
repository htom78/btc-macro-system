#!/usr/bin/env python3
"""Publish a new EveryDayZen macro note into the static Pages site."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


SITE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = SITE_DIR.parent
DATA_PATH = SITE_DIR / "data" / "entries.json"
ASSET_DIR = SITE_DIR / "assets"
CONTENT_DIR = SITE_DIR / "content"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an EveryDayZen macro article page and update entries.json."
    )
    parser.add_argument("--title", required=True, help="Article title.")
    parser.add_argument("--subtitle", default="", help="Short subtitle/deck.")
    parser.add_argument("--thesis", default="", help="One-sentence core thesis.")
    parser.add_argument("--slug", help="URL slug. Defaults to an ASCII-safe title/date slug.")
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="YYYY-MM-DD.")
    parser.add_argument("--content-file", required=True, help="Markdown/plain-text article body.")
    parser.add_argument("--image", help="Optional image path to copy into assets/.")
    parser.add_argument(
        "--format",
        action="append",
        dest="formats",
        default=[],
        help="Format tag, can be repeated. Example: --format 口播稿 --format 大图",
    )
    parser.add_argument(
        "--no-save-source",
        action="store_true",
        help="Do not save a Markdown source copy under everydayzen-macro/content/.",
    )
    parser.add_argument("--commit", action="store_true", help="Commit only generated files.")
    parser.add_argument("--push", action="store_true", help="Push after committing.")
    return parser.parse_args()


def slugify(title: str, date: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    if slug:
        return slug[:72].strip("-")
    return f"macro-note-{date}"


def load_entries() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def write_entries(entries: list[dict]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def copy_image(image: str | None, slug: str) -> str:
    if not image:
        return ""
    src = Path(image).expanduser()
    if not src.is_absolute():
        src = (Path.cwd() / src).resolve()
    if not src.exists():
        raise FileNotFoundError(f"image not found: {src}")
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    dst = ASSET_DIR / f"{slug}{src.suffix.lower()}"
    if src.resolve() != dst.resolve():
        shutil.copy2(src, dst)
    return f"assets/{dst.name}"


def markdown_to_html(text: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{html.escape(' '.join(paragraph))}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            body = "".join(f"<li>{html.escape(item)}</li>" for item in list_items)
            blocks.append(f"<ul>{body}</ul>")
            list_items = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue
        if line.startswith("### "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
            continue
        if line.startswith("# "):
            flush_paragraph()
            flush_list()
            blocks.append(f"<h2>{html.escape(line[2:].strip())}</h2>")
            continue
        if line.startswith("- "):
            flush_paragraph()
            list_items.append(line[2:].strip())
            continue
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


def strip_duplicate_title(text: str, title: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    first = lines[0].strip()
    if first == f"# {title}":
        return "\n".join(lines[1:]).lstrip()
    return text


def render_article(entry: dict, body_html: str) -> str:
    image_html = ""
    if entry.get("image"):
        image_alt = html.escape(entry["title"])
        image_html = f"""
    <figure class="visual">
      <img src="{html.escape(entry['image'])}" alt="{image_alt}">
    </figure>"""

    formats = " / ".join(entry.get("format") or ["口播稿"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(entry['title'])}</title>
  <style>
    :root {{
      color-scheme: light;
      --paper: #f6f2e8;
      --ink: #181816;
      --muted: #68625a;
      --line: rgba(24, 24, 22, .16);
      --panel: rgba(255, 253, 247, .86);
      --red: #b94b45;
      --gold: #b48635;
      --shadow: 0 24px 80px rgba(28, 25, 20, .12);
      --serif: "Iowan Old Style", "Songti SC", "Noto Serif CJK SC", Georgia, serif;
      --sans: "Avenir Next", "PingFang SC", "Hiragino Sans GB", sans-serif;
      --mono: "SFMono-Regular", "Menlo", monospace;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      color: var(--ink);
      font-family: var(--sans);
      background:
        linear-gradient(90deg, rgba(24, 24, 22, .035) 1px, transparent 1px) 0 0 / 44px 44px,
        linear-gradient(rgba(24, 24, 22, .032) 1px, transparent 1px) 0 0 / 44px 44px,
        radial-gradient(circle at 12% 8%, rgba(180, 134, 53, .18), transparent 28%),
        var(--paper);
      line-height: 1.72;
    }}

    a {{ color: inherit; }}

    .shell {{
      width: min(1080px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 64px;
    }}

    .topline {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }}

    .brand {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
      color: var(--ink);
      text-decoration: none;
      font-weight: 850;
    }}

    .seal {{
      width: 42px;
      height: 42px;
      display: grid;
      place-items: center;
      border: 1px solid rgba(24, 24, 22, .32);
      border-radius: 50%;
      background: rgba(255, 253, 247, .74);
      font-size: 14px;
      line-height: 1.05;
    }}

    .nav {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}

    .nav a,
    .button {{
      display: inline-flex;
      align-items: center;
      min-height: 38px;
      padding: 0 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 253, 247, .72);
      color: var(--ink);
      text-decoration: none;
      font-size: 13px;
      font-weight: 760;
    }}

    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 330px;
      gap: 32px;
      align-items: end;
      padding: 58px 0 34px;
    }}

    .eyebrow {{
      margin: 0 0 12px;
      color: var(--red);
      font: 780 12px/1 var(--mono);
      text-transform: uppercase;
    }}

    h1 {{
      margin: 0;
      max-width: 820px;
      font: 820 clamp(42px, 7vw, 80px)/1 var(--serif);
      letter-spacing: 0;
    }}

    .dek {{
      max-width: 740px;
      margin: 24px 0 0;
      color: #3f3b36;
      font-size: 19px;
      font-weight: 560;
    }}

    .quote {{
      padding: 24px;
      border: 1px solid rgba(24, 24, 22, .18);
      background: #181816;
      color: #fffdf7;
      box-shadow: var(--shadow);
    }}

    .quote strong {{
      display: block;
      margin-bottom: 12px;
      color: var(--gold);
      font: 780 12px/1 var(--mono);
      text-transform: uppercase;
    }}

    .quote p {{
      margin: 0;
      font: 760 24px/1.42 var(--serif);
    }}

    .visual {{
      margin: 10px 0 34px;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}

    .visual img {{
      display: block;
      width: 100%;
      height: auto;
    }}

    article {{
      padding: clamp(26px, 5vw, 52px);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 18px 50px rgba(28, 25, 20, .08);
    }}

    article h2 {{
      margin: 34px 0 12px;
      font: 820 32px/1.2 var(--serif);
    }}

    article h2:first-child {{ margin-top: 0; }}

    article h3 {{
      margin: 28px 0 10px;
      font-size: 22px;
    }}

    article p,
    article li {{
      color: #282622;
      font-size: 19px;
    }}

    article p {{ margin: 0 0 18px; }}
    article ul {{ margin: 0 0 22px; padding-left: 22px; }}

    footer {{
      margin-top: 42px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
      display: flex;
      justify-content: space-between;
      gap: 18px;
      flex-wrap: wrap;
    }}

    @media (max-width: 880px) {{
      .hero {{ grid-template-columns: 1fr; }}
    }}

    @media (max-width: 560px) {{
      h1 {{
        font-size: 36px;
        line-height: 1.08;
      }}

      .quote p {{
        font-size: 26px;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topline">
      <a class="brand" href="index.html">
        <span class="seal">动<br>中</span>
        <span>动中禅宏观观察</span>
      </a>
      <nav class="nav" aria-label="站点导航">
        <a href="index.html">内容索引</a>
        <a href="../index.html">策略工作台</a>
        {f'<a href="{html.escape(entry["image"])}">大图</a>' if entry.get("image") else ''}
      </nav>
    </header>

    <section class="hero">
      <div>
        <p class="eyebrow">{html.escape(formats)} / {html.escape(entry['date'])}</p>
        <h1>{html.escape(entry['title'])}</h1>
        <p class="dek">{html.escape(entry.get('subtitle') or entry.get('thesis') or '')}</p>
      </div>
      <aside class="quote">
        <strong>一句话看懂</strong>
        <p>{html.escape(entry.get('thesis') or entry.get('subtitle') or entry['title'])}</p>
      </aside>
    </section>
{image_html}
    <article>
{body_html}
    </article>

    <footer>
      <span>仅作宏观研究和内容整理，不构成投资建议。</span>
      <span><a href="index.html">返回索引</a> · <a href="data/entries.json">entries.json</a></span>
    </footer>
  </main>
</body>
</html>
"""


def save_source(content: str, slug: str, title: str) -> Path:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTENT_DIR / f"{slug}.md"
    if not content.lstrip().startswith("#"):
        content = f"# {title}\n\n{content.strip()}\n"
    path.write_text(content, encoding="utf-8")
    return path


def commit_and_push(paths: list[Path], title: str, push: bool) -> None:
    rel_paths = [str(path.relative_to(ROOT_DIR)) for path in paths if path.exists()]
    subprocess.run(["git", "add", *rel_paths], cwd=ROOT_DIR, check=True)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT_DIR)
    if diff.returncode == 0:
        print("No generated changes to commit.")
        return
    subprocess.run(
        ["git", "commit", "-m", f"Add EveryDayZen macro note: {title[:48]}"],
        cwd=ROOT_DIR,
        check=True,
    )
    if push:
        subprocess.run(["git", "push"], cwd=ROOT_DIR, check=True)


def main() -> int:
    args = parse_args()
    date = dt.date.fromisoformat(args.date).isoformat()
    slug = args.slug or slugify(args.title, date)
    page_path = SITE_DIR / f"{slug}.html"
    body_text = Path(args.content_file).expanduser().read_text(encoding="utf-8")
    image_path = copy_image(args.image, slug)
    formats = args.formats or ["口播稿"]

    entry = {
        "id": slug,
        "title": args.title,
        "subtitle": args.subtitle,
        "date": date,
        "format": formats,
        "thesis": args.thesis,
        "page": page_path.name,
        "image": image_path,
    }

    body_html = markdown_to_html(strip_duplicate_title(body_text, args.title))
    page_path.write_text(render_article(entry, body_html), encoding="utf-8")

    entries = [item for item in load_entries() if item.get("id") != slug]
    entries.insert(0, entry)
    write_entries(entries)

    changed_paths = [page_path, DATA_PATH]
    if image_path:
        changed_paths.append(SITE_DIR / image_path)
    if not args.no_save_source:
        changed_paths.append(save_source(body_text, slug, args.title))

    if args.commit or args.push:
        commit_and_push(changed_paths, args.title, args.push)

    print(f"Published local entry: {page_path.relative_to(ROOT_DIR)}")
    print(f"Updated index data: {DATA_PATH.relative_to(ROOT_DIR)}")
    if args.push and not args.commit:
        print("--push implies committing generated files before pushing.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
