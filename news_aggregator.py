"""
Balanced news aggregator using free RSS feeds.
Generates a PDF digest and an index.html for GitHub Pages.

Dependencies: pip install feedparser fpdf2
"""

import os
import re
import sys
import feedparser
from datetime import datetime
from difflib import SequenceMatcher
from fpdf import FPDF

# ── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SOURCES = [
    # Center
{"name": "ABC News",         "lean": "center",        "url": "https://feeds.abcnews.com/abcnews/topstories"},
    {"name": "CBS News",         "lean": "center",        "url": "https://www.cbsnews.com/latest/rss/main"},
    # Center-Left
    {"name": "NPR",              "lean": "center-left",   "url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "The Guardian",     "lean": "center-left",   "url": "https://www.theguardian.com/world/rss"},
    {"name": "Al Jazeera",       "lean": "center-left",   "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    # Left
    {"name": "Mother Jones",     "lean": "left",          "url": "https://www.motherjones.com/feed/"},
    {"name": "Common Dreams",    "lean": "left",          "url": "https://www.commondreams.org/rss.xml"},
    # Center-Right / Right
    {"name": "Fox News",         "lean": "center-right",  "url": "https://moxie.foxnews.com/google-publisher/latest.xml"},
    {"name": "The Hill",         "lean": "center-right",  "url": "https://thehill.com/news/feed/"},
    {"name": "New York Post",     "lean": "right",         "url": "https://nypost.com/feed/"},
    {"name": "National Review",   "lean": "right",         "url": "https://www.nationalreview.com/feed/"},
]

MAX_PER_SOURCE       = 10
SIMILARITY_THRESHOLD = 0.60
LEAN_ORDER = ["left", "center-left", "center", "center-right", "right"]

# Section header colours (R, G, B) — used in both PDF and HTML
LEAN_COLORS = {
    "left":         (120, 160, 220),
    "center-left":  (160, 190, 230),
    "center":       (180, 180, 180),
    "center-right": (230, 190, 160),
    "right":        (220, 150, 150),
}


# ── Fetching ──────────────────────────────────────────────────────────────────

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

def fetch_articles(source: dict) -> list:
    articles = []
    try:
        feed = feedparser.parse(source["url"], request_headers=HEADERS)
        for entry in feed.entries[:MAX_PER_SOURCE]:
            title = entry.get("title", "").strip()
            link  = entry.get("link",  "").strip()
            if title and link:
                articles.append({
                    "title":           title,
                    "link":            link,
                    "source":          source["name"],
                    "lean":            source["lean"],
                    "also_covered_by": [],
                })
    except Exception as exc:
        print(f"  [!] {source['name']}: {exc}", file=sys.stderr)
    return articles


# ── Deduplication ─────────────────────────────────────────────────────────────

def _normalize(title: str) -> str:
    return re.sub(r"[^\w\s]", "", title.lower())

def _similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio() >= SIMILARITY_THRESHOLD

def deduplicate(articles: list) -> list:
    unique = []
    for article in articles:
        for kept in unique:
            if _similar(article["title"], kept["title"]):
                if article["source"] not in kept["also_covered_by"]:
                    kept["also_covered_by"].append(article["source"])
                break
        else:
            unique.append(article)
    return unique


# ── PDF generation ────────────────────────────────────────────────────────────

def _safe(text: str) -> str:
    """Strip characters outside latin-1 so the built-in PDF font doesn't choke."""
    return text.encode("latin-1", errors="replace").decode("latin-1")

def build_pdf(articles: list, output_path: str) -> None:
    grouped = {}
    for a in articles:
        grouped.setdefault(a["lean"], []).append(a)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Balanced News Digest", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    stamp = datetime.now().strftime("%Y-%m-%d  %H:%M")
    pdf.cell(0, 7, f"{stamp}   |   {len(articles)} unique stories", ln=True, align="C")
    pdf.ln(6)

    for lean in LEAN_ORDER:
        if lean not in grouped:
            continue

        r, g, b = LEAN_COLORS.get(lean, (200, 200, 200))
        pdf.set_fill_color(r, g, b)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 9, f"  {lean.upper()}", ln=True, fill=True)
        pdf.ln(2)

        for a in grouped[lean]:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(0, 5, _safe(a["source"]), ln=True)

            pdf.set_font("Helvetica", "U", 10)
            pdf.set_text_color(0, 70, 180)
            pdf.multi_cell(0, 5, _safe(a["title"]), link=a["link"])
            pdf.set_text_color(0, 0, 0)

            if a["also_covered_by"]:
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(80, 80, 80)
                pdf.cell(0, 5, "Also covered by: " + _safe(", ".join(a["also_covered_by"])), ln=True)
                pdf.set_text_color(0, 0, 0)

            pdf.ln(3)

        pdf.ln(4)

    pdf.output(output_path)
    print(f"  PDF saved: {output_path}")


# ── HTML generation ───────────────────────────────────────────────────────────

def _rgb_css(lean: str) -> str:
    r, g, b = LEAN_COLORS.get(lean, (200, 200, 200))
    return f"rgb({r},{g},{b})"

def _section(lean: str, articles: list) -> str:
    if lean not in articles:
        return ""
    bg = _rgb_css(lean)
    items = ""
    for a in articles[lean]:
        also = ""
        if a["also_covered_by"]:
            also = f'<p class="also">Also covered by: {", ".join(a["also_covered_by"])}</p>'
        items += f"""
        <div class="article">
          <span class="source">{a["source"]}</span>
          <a href="{a["link"]}" target="_blank" rel="noopener">{a["title"]}</a>
          {also}
        </div>"""
    return f'<section><h2 style="background:{bg}">{lean.upper()}</h2>{items}</section>'

def build_html(articles: list, output_path: str) -> None:
    grouped = {}
    for a in articles:
        grouped.setdefault(a["lean"], []).append(a)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    col_left        = _section("left",         grouped)
    col_center      = _section("center",       grouped)
    col_right       = _section("right",        grouped)
    col_center_left  = _section("center-left",  grouped)
    col_center_right = _section("center-right", grouped)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Balanced News Digest</title>
  <style>
    body {{ font-family: sans-serif; margin: 0; padding: 1rem; }}
    h1 {{ text-align: center; }}
    .meta {{ text-align: center; color: #555; margin-bottom: 2rem; }}
    h2 {{ padding: 6px 12px; border-radius: 4px; font-size: 1rem; margin-top: 0; }}
    .article {{ margin: 0.75rem 0 0.75rem 0.5rem; }}
    .source {{ display: block; font-size: 0.75rem; font-weight: bold; color: #444; }}
    a {{ color: #0046b8; }}
    .also {{ font-size: 0.75rem; color: #666; margin: 2px 0 0; }}

    .three-col {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 1.5rem;
      margin-bottom: 2rem;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
    }}
    .col {{ min-width: 0; }}
  </style>
</head>
<body>
  <h1>Balanced News Digest</h1>
  <p class="meta">{stamp} &nbsp;|&nbsp; {len(articles)} unique stories</p>

  <div class="three-col">
    <div class="col">{col_left}</div>
    <div class="col">{col_center}</div>
    <div class="col">{col_right}</div>
  </div>

  <div class="two-col">
    <div class="col">{col_center_left}</div>
    <div class="col">{col_center_right}</div>
  </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML saved: {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Fetching news feeds...\n")
    all_articles = []
    ok = 0
    for source in SOURCES:
        print(f"  {source['name']}...", end=" ", flush=True)
        batch = fetch_articles(source)
        print(f"{len(batch)} articles")
        if batch:
            ok += 1
        all_articles.extend(batch)

    print(f"\nFetched {len(all_articles)} articles from {ok}/{len(SOURCES)} sources.")

    print("Deduplicating...", end=" ", flush=True)
    unique = deduplicate(all_articles)
    print(f"{len(unique)} unique stories.\n")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    pdf_path  = os.path.join(SCRIPT_DIR, f"news_{timestamp}.pdf")
    html_path = os.path.join(SCRIPT_DIR, "index.html")

    print("Building PDF...")
    build_pdf(unique, pdf_path)

    print("Building HTML...")
    build_html(unique, html_path)


if __name__ == "__main__":
    main()
