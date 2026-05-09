"""
Balanced news aggregator using free RSS feeds.
Generates a PDF digest and an index.html for GitHub Pages.

Dependencies: pip install feedparser fpdf2
"""

import html as html_lib
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
    # Left
    {"name": "Mother Jones",        "lean": "left",          "url": "https://www.motherjones.com/feed/"},
    {"name": "Common Dreams",       "lean": "left",          "url": "https://www.commondreams.org/rss.xml"},
    {"name": "HuffPost",            "lean": "left",          "url": "https://www.huffpost.com/section/front-page/feed"},
    {"name": "Democracy Now",       "lean": "left",          "url": "https://www.democracynow.org/democracynow.rss"},
    # Center-Left
    {"name": "NPR",                 "lean": "center-left",   "url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "The Guardian",        "lean": "center-left",   "url": "https://www.theguardian.com/world/rss"},
    {"name": "Al Jazeera",          "lean": "center-left",   "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "Politico",            "lean": "center-left",   "url": "https://www.politico.com/rss/politicopicks.xml"},
    {"name": "Vox",                 "lean": "center-left",   "url": "https://www.vox.com/rss/index.xml"},
    {"name": "PBS NewsHour",        "lean": "center-left",   "url": "https://www.pbs.org/newshour/feeds/rss/headlines"},
    # Center
    {"name": "ABC News",            "lean": "center",        "url": "https://feeds.abcnews.com/abcnews/topstories"},
    {"name": "CBS News",            "lean": "center",        "url": "https://www.cbsnews.com/latest/rss/main"},
    {"name": "CNBC",                "lean": "center",        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    # Center-Right
    {"name": "Fox News",            "lean": "center-right",  "url": "https://moxie.foxnews.com/google-publisher/latest.xml"},
    {"name": "The Hill",            "lean": "center-right",  "url": "https://thehill.com/news/feed/"},
    {"name": "Reason",              "lean": "center-right",  "url": "https://reason.com/feed/"},
    {"name": "Washington Examiner", "lean": "center-right",  "url": "https://www.washingtonexaminer.com/feed"},
    # Right
    {"name": "New York Post",       "lean": "right",         "url": "https://nypost.com/feed/"},
    {"name": "National Review",     "lean": "right",         "url": "https://www.nationalreview.com/feed/"},
    {"name": "Breitbart",           "lean": "right",         "url": "https://feeds.feedburner.com/breitbart"},
    {"name": "Daily Caller",        "lean": "right",         "url": "https://dailycaller.com/feed/"},
    {"name": "The Federalist",      "lean": "right",         "url": "https://thefederalist.com/feed/"},
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

def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities so summaries are plain text."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_articles(source: dict) -> list:
    articles = []
    try:
        feed = feedparser.parse(source["url"], request_headers=HEADERS)
        for entry in feed.entries[:MAX_PER_SOURCE]:
            title = entry.get("title", "").strip()
            link  = entry.get("link",  "").strip()
            if title and link:
                raw_summary = entry.get("summary", "") or entry.get("description", "")
                articles.append({
                    "title":           title,
                    "link":            link,
                    "summary":         _strip_html(raw_summary)[:600],
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
    pdf.cell(0, 12, "Daily Balanced News", ln=True, align="C")
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

def _section(lean: str, grouped: dict) -> str:
    if lean not in grouped:
        return ""
    bg = _rgb_css(lean)
    label = lean.upper()
    items = ""
    for a in grouped[lean]:
        also = ""
        if a["also_covered_by"]:
            covered = ", ".join(a["also_covered_by"])
            also = f'<p class="also"><span class="also-label">Also covered by:</span> {covered}</p>'
        summary_attr = a.get("summary", "").replace('"', "&quot;")
        items += f"""
        <div class="article" data-summary="{summary_attr}">
          <span class="source">{a["source"]}</span>
          <a href="{a["link"]}" target="_blank" rel="noopener">{a["title"]}</a>
          {also}
        </div>"""
    return f'<section><div class="lean-header" style="background:{bg}">{label}</div>{items}</section>'


def _spectrum_legend() -> str:
    items = ""
    for lean in LEAN_ORDER:
        color = _rgb_css(lean)
        label = lean.upper()
        items += f'<span class="sp-item"><span class="sp-dot" style="background:{color}"></span>{label}</span>'
    return f'<div class="spectrum">{items}</div>'


def build_html(articles: list, output_path: str) -> None:
    grouped = {}
    for a in articles:
        grouped.setdefault(a["lean"], []).append(a)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    col_left         = _section("left",         grouped)
    col_center       = _section("center",       grouped)
    col_right        = _section("right",        grouped)
    col_center_left  = _section("center-left",  grouped)
    col_center_right = _section("center-right", grouped)
    spectrum         = _spectrum_legend()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Balanced News</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', sans-serif;
      background: #f1f5f9;
      color: #1e293b;
      line-height: 1.5;
    }}

    /* ── Header ── */
    header {{
      background: #0f172a;
      color: #fff;
      text-align: center;
      padding: 2rem 1.5rem 0;
    }}
    header h1 {{
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -0.5px;
    }}
    .header-meta {{
      margin-top: 0.35rem;
      font-size: 0.82rem;
      color: #94a3b8;
    }}

    /* ── Search ── */
    .search-bar {{
      background: #0f172a;
      padding: 1.1rem 1.5rem 1.25rem;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.4rem;
    }}
    .search-input-wrap {{
      position: relative;
      width: 100%;
      max-width: 580px;
    }}
    .search-icon {{
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      color: #64748b;
      pointer-events: none;
    }}
    .search-input-wrap input {{
      width: 100%;
      padding: 0.65rem 1rem 0.65rem 2.75rem;
      font-family: 'Inter', sans-serif;
      font-size: 0.95rem;
      border: 1px solid #334155;
      border-radius: 999px;
      background: #1e293b;
      color: #f1f5f9;
      outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }}
    .search-input-wrap input::placeholder {{ color: #64748b; }}
    .search-input-wrap input:focus {{
      border-color: #3b82f6;
      box-shadow: 0 0 0 3px rgba(59,130,246,0.2);
    }}
    #search-status {{
      font-size: 0.78rem;
      color: #64748b;
      min-height: 1.1em;
    }}

    /* ── Spectrum legend ── */
    .spectrum {{
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: 1.25rem;
      padding: 0.7rem 1rem;
      background: #fff;
      border-bottom: 1px solid #e2e8f0;
    }}
    .sp-item {{
      display: flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.6px;
      color: #64748b;
    }}
    .sp-dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      flex-shrink: 0;
    }}

    /* ── Main grid ── */
    main {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 1.25rem;
    }}
    .grid-top {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 1.1rem;
      margin-bottom: 1.1rem;
    }}
    .grid-bottom {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.1rem;
    }}

    /* ── Column card ── */
    .col-card {{
      background: #fff;
      border-radius: 10px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}

    /* ── Lean header ── */
    .lean-header {{
      padding: 0.55rem 1rem;
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 1.2px;
      color: #fff;
    }}

    /* ── Article rows ── */
    .article {{
      padding: 0.8rem 1rem;
      border-bottom: 1px solid #f1f5f9;
      transition: background 0.1s;
    }}
    .article:last-child {{ border-bottom: none; }}
    .article:hover {{ background: #f8fafc; }}

    .source {{
      display: block;
      font-size: 0.62rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.7px;
      color: #94a3b8;
      margin-bottom: 0.28rem;
    }}
    .article a {{
      display: block;
      font-size: 0.875rem;
      font-weight: 500;
      color: #1e293b;
      text-decoration: none;
      line-height: 1.45;
    }}
    .article a:hover {{
      color: #2563eb;
      text-decoration: underline;
      text-underline-offset: 2px;
    }}
    .also {{
      margin-top: 0.35rem;
      font-size: 0.68rem;
      color: #94a3b8;
    }}
    .also-label {{ font-weight: 600; color: #64748b; }}

    /* ── Footer ── */
    footer {{
      text-align: center;
      padding: 2rem 1rem;
      font-size: 0.75rem;
      color: #94a3b8;
    }}

    /* ── Responsive ── */
    @media (max-width: 960px) {{
      .grid-top   {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 640px) {{
      .grid-top, .grid-bottom {{ grid-template-columns: 1fr; }}
      header h1 {{ font-size: 1.5rem; }}
    }}
  </style>
</head>
<body>

  <header>
    <h1>Daily Balanced News</h1>
    <p class="header-meta">{stamp} &nbsp;&bull;&nbsp; {len(articles)} unique stories across the political spectrum</p>
  </header>

  <div class="search-bar">
    <div class="search-input-wrap">
      <svg class="search-icon" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
      </svg>
      <input id="search" type="search" placeholder="Search topics from the daily feeds below" autocomplete="off">
    </div>
    <p id="search-status"></p>
  </div>

  {spectrum}

  <main>
    <div class="grid-top">
      <div class="col-card">{col_left}</div>
      <div class="col-card">{col_center}</div>
      <div class="col-card">{col_right}</div>
    </div>
    <div class="grid-bottom">
      <div class="col-card">{col_center_left}</div>
      <div class="col-card">{col_center_right}</div>
    </div>
  </main>

  <footer>Daily Balanced News &bull; Powered by public RSS feeds &bull; {stamp}</footer>

  <script>
    const input  = document.getElementById('search');
    const status = document.getElementById('search-status');

    input.addEventListener('input', function () {{
      const raw   = this.value.trim();
      const terms = raw.toLowerCase().split(/\s+/).filter(Boolean);
      let visible = 0;

      document.querySelectorAll('.article').forEach(function (card) {{
        const title    = (card.querySelector('a') || {{}}).textContent || '';
        const summary  = card.dataset.summary || '';
        const haystack = (title + ' ' + summary).toLowerCase();
        const match    = terms.length === 0 || terms.every(function (t) {{
          return haystack.includes(t);
        }});
        card.style.display = match ? '' : 'none';
        if (match) visible++;
      }});

      document.querySelectorAll('section').forEach(function (sec) {{
        const any = Array.from(sec.querySelectorAll('.article'))
                        .some(function (c) {{ return c.style.display !== 'none'; }});
        sec.style.display = any ? '' : 'none';
      }});

      status.textContent = terms.length === 0
        ? ''
        : visible + ' stor' + (visible === 1 ? 'y' : 'ies') + ' matching “' + raw + '”';
    }});
  </script>
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
