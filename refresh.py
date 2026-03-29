import anthropic
import re
import json
from datetime import datetime

client = anthropic.Anthropic()

PROMPT = """Search for today's end-of-day closing prices and return ONLY a valid JSON object. No markdown, no explanation, no code blocks. Use exactly this schema:

{
  "eq": [
    {"l": "S&P 500", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 0, "s": []},
    {"l": "Nasdaq 100", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 0, "s": []},
    {"l": "Euro Stoxx 50", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 0, "s": []},
    {"l": "DAX", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 0, "s": []},
    {"l": "FTSE 100", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 0, "s": []},
    {"l": "Nikkei 225", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 0, "s": []},
    {"l": "SMI", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 0, "s": []},
    {"l": "Hang Seng", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 0, "s": []},
    {"l": "MSCI EM (EEM)", "v": 0, "d": 0, "dp": 0, "y": 0, "y1": 0, "dec": 2, "s": []}
  ],
  "rt": [
    {"l": "US 10Y", "v": 0, "d1": 0, "yb": 0, "y1": 0, "s": []},
    {"l": "US 2Y", "v": 0, "d1": 0, "yb": 0, "y1": 0, "s": []},
    {"l": "DE 10Y Bund", "v": 0, "d1": 0, "yb": 0, "y1": 0, "s": []},
    {"l": "UK 10Y Gilt", "v": 0, "d1": 0, "yb": 0, "y1": 0, "s": []},
    {"l": "JP 10Y JGB", "v": 0, "d1": 0, "yb": 0, "y1": 0, "s": []},
    {"l": "IT 10Y BTP", "v": 0, "d1": 0, "yb": 0, "y1": 0, "s": []},
    {"l": "CH 10Y", "v": 0, "d1": 0, "yb": 0, "y1": 0, "s": []}
  ],
  "fx": [
    {"l": "EUR/USD", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "GBP/USD", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "USD/JPY", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "USD/CHF", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "AUD/USD", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "USD/CAD", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "NZD/USD", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "EUR/CHF", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "EUR/GBP", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []}
  ],
  "co": [
    {"l": "Gold", "v": 0, "u": "USD/oz", "dec": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "Silver", "v": 0, "u": "USD/oz", "dec": 2, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "WTI Crude", "v": 0, "u": "USD/bbl", "dec": 2, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "Brent Crude", "v": 0, "u": "USD/bbl", "dec": 2, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "Natural Gas", "v": 0, "u": "USD/MMBtu", "dec": 2, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "Copper", "v": 0, "u": "USD/lb", "dec": 3, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "VIX", "v": 0, "u": "pts", "dec": 2, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "Bitcoin", "v": 0, "u": "USD", "dec": 0, "dp": 0, "y": 0, "y1": 0, "s": []}
  ],
  "cr": [
    {"l": "US IG — LQD", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "US HY — HYG", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "EUR IG — IEAC", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "EUR HY — IHYG", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []},
    {"l": "EM Sov — EMB", "v": 0, "dp": 0, "y": 0, "y1": 0, "s": []}
  ]
}

Fields: v=current price, d=day change (equities), dp=day change %, d1=day change in yield (rates), yb=YTD change in bps (rates), y=YTD %, y1=1Y %, s=array of last 6 daily closes oldest first. For EEM use the ETF price. Return ONLY the JSON."""

def fetch_prices():
    print("Calling Anthropic API with web search...")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": PROMPT}]
    )
    # Extract text blocks only
    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text
    text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    # Find JSON object
    match = re.search(r'\{[\s\S]+\}', text)
    if not match:
        raise ValueError(f"No JSON found in response:\n{text[:500]}")
    return json.loads(match.group())

def build_js_block(d):
    today = datetime.utcnow().strftime("%d %b %Y")
    lines = [f"const D = {{\n  // EOD data — {today} UTC | Auto-refreshed via GitHub Actions"]

    def fmt_arr(arr):
        return "[" + ",".join(str(x) for x in arr) + "]"

    lines.append("  eq:[")
    for r in d.get("eq", []):
        lines.append(f"    {{l:'{r['l']}', v:{r['v']}, d:{r['d']}, dp:{r['dp']}, y:{r['y']}, y1:{r['y1']}, dec:{r.get('dec',0)}, s:{fmt_arr(r.get('s',[]))}}},")
    lines.append("  ],")

    lines.append("  rt:[")
    for r in d.get("rt", []):
        lines.append(f"    {{l:'{r['l']}', v:{r['v']}, d1:{r['d1']}, yb:{r['yb']}, y1:{r['y1']}, s:{fmt_arr(r.get('s',[]))}}},")
    lines.append("  ],")

    lines.append("  fx:[")
    for r in d.get("fx", []):
        lines.append(f"    {{l:'{r['l']}', v:{r['v']}, dp:{r['dp']}, y:{r['y']}, y1:{r['y1']}, s:{fmt_arr(r.get('s',[]))}}},")
    lines.append("  ],")

    lines.append("  co:[")
    for r in d.get("co", []):
        lines.append(f"    {{l:'{r['l']}', v:{r['v']}, u:'{r['u']}', dec:{r.get('dec',2)}, dp:{r['dp']}, y:{r['y']}, y1:{r['y1']}, s:{fmt_arr(r.get('s',[]))}}},")
    lines.append("  ],")

    lines.append("  cr:[")
    for r in d.get("cr", []):
        lines.append(f"    {{l:'{r['l']}', v:{r['v']}, dp:{r['dp']}, y:{r['y']}, y1:{r['y1']}, s:{fmt_arr(r.get('s',[]))}}},")
    lines.append("  ]")
    lines.append("};")
    return "\n".join(lines)

def update_html(new_js_block):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # Replace the entire const D = {...}; block
    pattern = r'const D = \{[\s\S]*?\n\};'
    if not re.search(pattern, html):
        raise ValueError("Could not find 'const D = {...};' block in index.html")

    updated = re.sub(pattern, new_js_block, html)

    # Update date stamp in footer and header
    today_display = datetime.utcnow().strftime("%a %d %b %Y")
    updated = re.sub(r'EOD data \w+ \d+ \w+ \d+', f'EOD data {today_display}', updated)
    updated = re.sub(r'EOD · \w+ \d+ \w+ \d+', f'EOD · {today_display}', updated)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(updated)
    print("index.html updated successfully")

if __name__ == "__main__":
    data = fetch_prices()
    js_block = build_js_block(data)
    update_html(js_block)
    print("Done.")
```

Commit this file to the root of your repo.

---

## How it works after setup
```
Every weekday 18:00 CET
        ↓
GitHub Action runs refresh.py
        ↓
Python calls Anthropic API (web search enabled)
        ↓
Parses fresh price JSON
        ↓
Rewrites const D = {...} in index.html
        ↓
Commits + pushes to main
        ↓
GitHub Pages serves the updated file (~60s delay)
```

---

## File structure in your repo
```
investa-dashboard/
├── index.html              ← your dashboard
├── refresh.py              ← the price update script
└── .github/
    └── workflows/
        └── refresh.yml     ← the automation schedule
