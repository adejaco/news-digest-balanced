# News Aggregator — Project Context

## What this does
Fetches RSS feeds from news sources across the political spectrum, deduplicates similar stories by title similarity, generates a colour-coded PDF digest, and emails it as an attachment.

## How to run
```
.\venv\Scripts\python.exe news_aggregator.py
```
The virtual environment is in `.\venv\` (Python 3.9.13).
The PDF is saved in this folder as `news_YYYYMMDD_HHMM.pdf`.

## Dependencies
```
pip install feedparser fpdf2
```

## Current sources
| Source           | Lean         |
|------------------|--------------|
| Mother Jones     | left         |
| Common Dreams    | left         |
| NPR              | center-left  |
| The Guardian     | center-left  |
| Al Jazeera       | center-left  |
| AP News          | center       |
| Reuters          | center       |
| USA Today        | center       |
| Fox News         | center-right |
| The Hill         | center-right |
| Washington Times | right        |

Lean labels are based on AllSides and Ad Fontes Media ratings. To change a label, edit the `"lean"` field in the `SOURCES` list. To add a source, add a dict with `name`, `lean`, and `url` (must be an RSS feed URL).

## Key design decisions
- **Deduplication**: uses `difflib.SequenceMatcher` on normalized titles; threshold is `0.60` (tunable via `SIMILARITY_THRESHOLD`). When a duplicate is found the first-seen article is kept and the duplicate's source is recorded in "Also covered by".
- **PDF**: uses `fpdf2` with built-in Helvetica font. Article titles are blue, underlined, and clickable. Sections are colour-coded by lean. Non-latin-1 characters are replaced to avoid font errors.
- **Email**: Gmail SMTP SSL on port 465. Credentials are hardcoded in `main()`. The send call is currently commented out with a placeholder — re-enable `send_email(...)` when ready to resume emailing.

## Known issues / sources to watch
- **Reuters** discontinued their public RSS feed; it may return 0 articles.
- **The Nation** RSS feed returned no articles — removed and replaced with Mother Jones and Common Dreams.
- **BBC News** was removed because articles require a subscription.
- **Microsoft Start (MSN)** does not publish a usable public RSS feed.

## Possible next steps
- Re-enable the email send once credentials are confirmed working
- Add topic filtering (e.g. politics only, or exclude sports)
- Schedule the script to run automatically (Windows Task Scheduler)
- Add a summary count table at the top of the PDF showing articles per source
