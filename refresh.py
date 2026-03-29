"""
Investa Morning Dashboard — Daily Refresh Script
Runs via GitHub Actions every weekday at 18:00 CET.

Steps each run:
  1. Fetch EOD market prices (equities, rates, FX, commodities, credit)
  2. Fetch today's market news with fresh article links
  3. Translate market news (brief + headlines + body) into Italian and French
  4. Fetch latest news for each of 24 portfolio companies
  5. Translate portfolio company news headlines into Italian and French
  6. Bake everything into index.html:
       prices      → JS const D = {...}
       market news → HTML with data-it / data-fr attributes on each element
       portfolio   → each pnews div replaced with fresh content + translations
"""

import anthropic
import re
import json
import html as html_lib
from datetime import datetime, timezone

client = anthropic.Anthropic()
TODAY         = datetime.now(timezone.utc).strftime("%d %b %Y")
TODAY_DISPLAY = datetime.now(timezone.utc).strftime("%a %d %b %Y")
WEEKDAY       = datetime.now(timezone.utc).strftime("%A")

# ── Utilities ────────────────────────────────────────────────────────────────

def esc(s):
    return html_lib.escape(str(s), quote=True)

def slug(name):
    return re.sub(r"[^a-z0-9]", "_", name.lower().strip()).strip("_")

def parse_obj(text):
    text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    m = re.search(r'\{[\s\S]+\}', text)
    if not m:
        raise ValueError(f"No JSON object: {text[:200]}")
    return json.loads(m.group())

def parse_arr(text):
    text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    m = re.search(r'\[[\s\S]+\]', text)
    if not m:
        raise ValueError(f"No JSON array: {text[:200]}")
    return json.loads(m.group())

def call_claude(prompt, max_tokens=4000, use_search=True):
    kwargs = dict(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    if use_search:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
    r = client.messages.create(**kwargs)
    return "".join(b.text for b in r.content if hasattr(b, "text"))

# ── Step 1: Prices ───────────────────────────────────────────────────────────

def fetch_prices():
    print("Fetching prices...")
    prompt = f"""Search for today's EOD closing prices ({TODAY}). Return ONLY valid JSON, no markdown.

{{
  "eq":[{{"l":"S&P 500","v":0,"d":0,"dp":0,"y":0,"y1":0,"dec":0,"s":[]}}],
  "rt":[{{"l":"US 10Y","v":0,"d1":0,"yb":0,"y1":0,"s":[]}}],
  "fx":[{{"l":"EUR/USD","v":0,"dp":0,"y":0,"y1":0,"s":[]}}],
  "co":[{{"l":"Gold","v":0,"u":"USD/oz","dec":0,"dp":0,"y":0,"y1":0,"s":[]}}],
  "cr":[{{"l":"US IG — LQD","v":0,"dp":0,"y":0,"y1":0,"s":[]}}]
}}

eq: S&P 500, Nasdaq 100, Euro Stoxx 50, DAX, FTSE 100, Nikkei 225, SMI, Hang Seng, MSCI EM (EEM)
rt: US 10Y, US 2Y, DE 10Y Bund, UK 10Y Gilt, JP 10Y JGB, IT 10Y BTP, CH 10Y
fx: EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD, EUR/CHF, EUR/GBP
co: Gold, Silver, WTI Crude, Brent Crude, Natural Gas, Copper, VIX, Bitcoin
cr: LQD, HYG, IEAC, IHYG, EMB

v=price, d=day chg(eq), dp=day%, d1=yield chg(rt), yb=YTD bps(rt), y=YTD%, y1=1Y%, s=last 6 closes oldest-first."""
    data = parse_obj(call_claude(prompt, max_tokens=4000))
    print(f"  OK: {len(data.get('eq',[]))} indices, {len(data.get('fx',[]))} FX")
    return data

def build_price_js(d):
    def fa(a): return "[" + ",".join(str(x) for x in (a or [])) + "]"
    L = [f"const D = {{\n  // EOD data — {TODAY} | Auto-refreshed via GitHub Actions"]
    L.append("  eq:[")
    for r in d.get("eq",[]):
        L.append(f"    {{l:'{r['l']}',v:{r['v']},d:{r.get('d',0)},dp:{r.get('dp',0)},y:{r.get('y',0)},y1:{r.get('y1',0)},dec:{r.get('dec',0)},s:{fa(r.get('s'))}}},")
    L.append("  ],\n  rt:[")
    for r in d.get("rt",[]):
        L.append(f"    {{l:'{r['l']}',v:{r['v']},d1:{r.get('d1',0)},yb:{r.get('yb',0)},y1:{r.get('y1',0)},s:{fa(r.get('s'))}}},")
    L.append("  ],\n  fx:[")
    for r in d.get("fx",[]):
        L.append(f"    {{l:'{r['l']}',v:{r['v']},dp:{r.get('dp',0)},y:{r.get('y',0)},y1:{r.get('y1',0)},s:{fa(r.get('s'))}}},")
    L.append("  ],\n  co:[")
    for r in d.get("co",[]):
        L.append(f"    {{l:'{r['l']}',v:{r['v']},u:'{r.get('u','')}',dec:{r.get('dec',2)},dp:{r.get('dp',0)},y:{r.get('y',0)},y1:{r.get('y1',0)},s:{fa(r.get('s'))}}},")
    L.append("  ],\n  cr:[")
    for r in d.get("cr",[]):
        L.append(f"    {{l:'{r['l']}',v:{r['v']},dp:{r.get('dp',0)},y:{r.get('y',0)},y1:{r.get('y1',0)},s:{fa(r.get('s'))}}},")
    L.append("  ]\n};")
    return "\n".join(L)

# ── Step 2: Market News ───────────────────────────────────────────────────────

def fetch_news():
    print("Fetching market news...")
    prompt = f"""Today is {TODAY} ({WEEKDAY}). Search for today's financial market news. Return ONLY valid JSON.

{{
  "date": "{TODAY}",
  "brief": "4-6 sentence morning commentary with specific numbers and key events today.",
  "sections": [{{
    "id": "equities", "label": "Equities", "tag_class": "eq",
    "cards": [{{"tag":"Equities","tag_class":"eq","source":"","date":"","headline":"","url":"","body":"","link_label":"Read on Source \u2197"}}]
  }}]
}}

Include sections: equities(eq,3-4 cards), rates(rates,2-3), fx(fx,2), oil(oil,2-3), macro(macro,2).
All URLs must be real articles published today or yesterday.
Sources: Bloomberg, Reuters, CNBC, FT, WSJ, Trading Economics preferred. Return ONLY JSON."""
    data = parse_obj(call_claude(prompt, max_tokens=6000))
    total = sum(len(s.get("cards",[])) for s in data.get("sections",[]))
    print(f"  OK: {len(data.get('sections',[]))} sections, {total} cards")
    return data

# ── Step 3: Translate Market News ────────────────────────────────────────────

def translate_news(news_data, lang_name):
    print(f"Translating market news to {lang_name}...")
    items = [{"id":"brief","text":news_data["brief"]}]
    for s in news_data.get("sections",[]):
        for i,card in enumerate(s.get("cards",[])):
            p = f"{s['id']}_{i}"
            items += [
                {"id":f"{p}_headline","text":card["headline"]},
                {"id":f"{p}_body",    "text":card["body"]},
                {"id":f"{p}_link",    "text":card.get("link_label","Read more \u2197")},
            ]
    prompt = f"""Translate these financial texts from English to professional {lang_name} for institutional investors.
Return ONLY JSON array: [{{"id":"...","text":"..."}}]
Keep numbers, percentages, tickers, company names unchanged. No markdown.

{json.dumps(items)}"""
    translated = parse_arr(call_claude(prompt, max_tokens=6000, use_search=False))
    result = {{item["id"]: item["text"] for item in translated}}
    print(f"  OK: {len(result)} strings")
    return result

# ── Step 4: Build Market News HTML ───────────────────────────────────────────

SECT = {{
    "equities":{"en":"Equities",            "it":"Azioni",                   "fr":"Actions"},
    "rates":   {"en":"Rates & Fixed Income","it":"Tassi & Reddito Fisso",    "fr":"Taux & Obligataire"},
    "fx":      {"en":"FX & Currency",       "it":"Valute",                   "fr":"Devises"},
    "oil":     {"en":"Oil & Commodities",   "it":"Petrolio & Materie Prime", "fr":"Pétrole & Matières Premières"},
    "macro":   {"en":"Macro & Geopolitics", "it":"Macro & Geopolitica",      "fr":"Macro & Géopolitique"},
}}
BRIEF_LBL = {"en":"Morning Commentary","it":"Commento del Mattino","fr":"Commentaire du Matin"}

def build_news_html(news_data, ti, tf):
    ds = news_data.get("date", TODAY)
    be = news_data.get("brief","")
    L = ['<div id="pg-news-inner" style="padding:12px 14px 30px;">']
    L.append(f'  <div class="morning-brief" data-it="{esc(ti.get("brief",be))}" data-fr="{esc(tf.get("brief",be))}">')
    L.append(f'    <div class="meta">{BRIEF_LBL["en"]} · {WEEKDAY} {ds}</div>')
    L.append(f'    {html_lib.escape(be)}')
    L.append('  </div>')
    for sec in news_data.get("sections",[]):
        sid = sec.get("id","")
        lbl = SECT.get(sid,{}).get("en", sec.get("label",sid.title()))
        tc  = sec.get("tag_class","eq")
        L.append('  <div class="section">')
        L.append(f'    <div class="section-hdr" data-sect="sect_{sid}"><span>{html_lib.escape(lbl)}</span></div>')
        L.append('    <div class="cards">')
        for i,card in enumerate(sec.get("cards",[])):
            p   = f"{sid}_{i}"
            he  = card.get("headline","")
            be2 = card.get("body","")
            le  = card.get("link_label","Read more \u2197")
            url = card.get("url","#")
            src = html_lib.escape(card.get("source",""))
            dt  = html_lib.escape(card.get("date",""))
            tag = html_lib.escape(card.get("tag",lbl))
            hi  = ti.get(f"{p}_headline",he); hf = tf.get(f"{p}_headline",he)
            bi  = ti.get(f"{p}_body",be2);    bf = tf.get(f"{p}_body",be2)
            li  = ti.get(f"{p}_link",le);     lf = tf.get(f"{p}_link",le)
            L.append(f'      <div class="card {tc}">')
            L.append(f'        <div class="card-top"><span class="ctag {tc}">{tag}</span><span class="csrc">{src}</span><span class="cdate">{dt}</span></div>')
            L.append(f'        <div class="cheadline" data-it=\'<a href="{esc(url)}" target="_blank">{esc(hi)}</a>\' data-fr=\'<a href="{esc(url)}" target="_blank">{esc(hf)}</a>\'><a href="{html_lib.escape(url)}" target="_blank">{html_lib.escape(he)}</a></div>')
            L.append(f'        <div class="cbody" data-it="{esc(bi)}" data-fr="{esc(bf)}">{html_lib.escape(be2)}</div>')
            L.append(f'        <a class="clink" href="{html_lib.escape(url)}" target="_blank" data-it="{esc(li)}" data-fr="{esc(lf)}">{html_lib.escape(le)}</a>')
            L.append('      </div>')
        L.append('    </div>\n  </div>')
    L.append(f'  <div class="news-footer">Sources compiled {TODAY} · Bloomberg · Reuters · CNBC · FT · WSJ · Trading Economics</div>')
    L.append('</div>')
    return "\n".join(L)

# ── Step 5: Portfolio Company News ───────────────────────────────────────────

COMPANY_SEARCH = {
    "Anthropic":               "Anthropic AI company news",
    "Anthropic 2":             "Anthropic AI company news",
    "OpenAI":                  "OpenAI company news",
    "Crescendo":               "Crescendo AI contact centre news",
    "Klarna":                  "Klarna NYSE KLAR stock news",
    "Revolut":                 "Revolut neobank news",
    "AGAM":                    "AGAM microcredit emerging markets fintech",
    "Altheia — Tranche 1":     "Altheia biotech news",
    "Altheia — Tranche 2":     "Altheia biotech news",
    "Arsenale":                "Arsenale bioreactor biotech startup",
    "NanoRetinal":             "NanoRetinal retinal implant vision",
    "Mitral (Valcare Medical)":"Valcare Medical mitral valve MedTech",
    "Rise":                    "Rise EV city transport startup",
    "Metamorphosies":          "Metamorphosies energy storage startup",
    "Newcleo":                 "Newcleo nuclear SMR reactor news",
    "Afterwind Potential":     "wind turbine blade recycling climate tech",
    "V-Nova":                  "V-Nova LCEVC video compression news",
    "Pasqal":                  "Pasqal quantum computing news",
    "Leipzig Stadium":         "Red Bull Arena Leipzig stadium news",
    "Project Marie (Lucid III)":"Tracht Bavarian traditional dress retail",
    "Canva":                   "Canva design platform news IPO",
    "Shopcircle":              "Shop Circle ecommerce B2B SaaS news",
    "Fyeld (Pomos)":           "Fyeld Pomos agriculture machinery",
    "SpaceX":                  "SpaceX news Starlink launch",
}

def fetch_portfolio_news():
    print("Fetching portfolio company news (4 batches of 6)...")
    results = {}
    companies = list(COMPANY_SEARCH.items())
    for bi, batch_start in enumerate(range(0, len(companies), 6)):
        batch = companies[batch_start:batch_start+6]
        search_lines = "\n".join(f"- {n} (search: {q})" for n,q in batch)
        slug_lines   = "\n".join(f"- {n} -> {slug(n)}" for n,_ in batch)
        prompt = f"""Search for latest news ({TODAY}) about these companies. Return JSON array.

{search_lines}

Structure: [{{"company_id":"slug","items":[{{"headline":"...","url":"...","source":"...","date":"..."}}]}}]

Slugs: {slug_lines}

Rules: 1-2 items max per company. Real URLs only. If no news: items:[{{"headline":"No recent public news found","url":"","source":"","date":""}}].
Return ONLY JSON array."""
        try:
            arr = parse_arr(call_claude(prompt, max_tokens=3000))
            for item in arr:
                results[item.get("company_id","")] = item.get("items",[])
            print(f"  Batch {bi+1}: {len(arr)} companies OK")
        except Exception as e:
            print(f"  Batch {bi+1} failed: {e}")
    return results

def translate_portfolio_news(news_map, lang_name):
    print(f"Translating portfolio news to {lang_name}...")
    items = []
    for cid, news_items in news_map.items():
        for i,item in enumerate(news_items):
            h = item.get("headline","")
            if h and h != "No recent public news found":
                items.append({"id":f"{cid}_{i}","text":h})
    if not items:
        return {}
    prompt = f"""Translate these headlines from English to professional {lang_name} for institutional investors.
Return ONLY JSON array: [{{"id":"...","text":"..."}}]. Keep numbers/tickers/names unchanged. No markdown.

{json.dumps(items)}"""
    try:
        translated = parse_arr(call_claude(prompt, max_tokens=3000, use_search=False))
        result = {{item["id"]: item["text"] for item in translated}}
        print(f"  OK: {len(result)} headlines")
        return result
    except Exception as e:
        print(f"  Failed: {e}")
        return {}

NO_NEWS = {"en":"No recent public news found.","it":"Nessuna notizia pubblica recente.","fr":"Aucune actualité publique récente."}

def build_pnews_html(cid, items, ti, tf):
    if not items:
        return (f'<div class="pnews" data-news-id="{cid}"><div class="pnews-row">'
                f'<div class="pnews-dot"></div><span class="pnote" '
                f'data-it="{esc(NO_NEWS["it"])}" data-fr="{esc(NO_NEWS["fr"])}">'
                f'{NO_NEWS["en"]}</span></div></div>')
    rows = []
    for i,item in enumerate(items[:2]):
        h   = item.get("headline","")
        url = item.get("url","")
        src = item.get("source","")
        key = f"{cid}_{i}"
        if not h or h == "No recent public news found":
            rows.append(f'<div class="pnews-row"><div class="pnews-dot"></div>'
                        f'<span class="pnote" data-it="{esc(NO_NEWS["it"])}" data-fr="{esc(NO_NEWS["fr"])}">'
                        f'{NO_NEWS["en"]}</span></div>')
            continue
        hi = ti.get(key,h); hf = tf.get(key,h)
        sh = f'<span class="psrc">{html_lib.escape(src)}</span>' if src else ""
        if url:
            en = f'<a href="{html_lib.escape(url)}" target="_blank">{html_lib.escape(h)}</a>{sh}'
            it = esc(f'<a href="{url}" target="_blank">{hi}</a>{sh}')
            fr = esc(f'<a href="{url}" target="_blank">{hf}</a>{sh}')
        else:
            en = f'<span style="color:var(--text2)">{html_lib.escape(h)}</span>{sh}'
            it = esc(f'<span style="color:var(--text2)">{hi}</span>{sh}')
            fr = esc(f'<span style="color:var(--text2)">{hf}</span>{sh}')
        rows.append(f'<div class="pnews-row" data-it="{it}" data-fr="{fr}"><div class="pnews-dot"></div>{en}</div>')
    return f'<div class="pnews" data-news-id="{cid}">{"".join(rows)}</div>'

def patch_portfolio_news(news_map, ti, tf):
    with open("index.html","r",encoding="utf-8") as f:
        content = f.read()
    replaced = 0
    for name in COMPANY_SEARCH:
        cid = slug(name)
        new_div = build_pnews_html(cid, news_map.get(cid,[]), ti, tf)
        pattern = rf'<div class="pnews" data-news-id="{re.escape(cid)}"[^>]*>[\s\S]*?</div>'
        new_content = re.sub(pattern, new_div, content, count=1)
        if new_content != content:
            content = new_content
            replaced += 1
    with open("index.html","w",encoding="utf-8") as f:
        f.write(content)
    print(f"  OK: {replaced}/24 portfolio news blocks updated")

# ── Step 6: Patch index.html ──────────────────────────────────────────────────

def patch_html(price_js, news_html):
    with open("index.html","r",encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'const D = \{[\s\S]*?\n\};', price_js, content)
    pattern = r'(<div class="page"[^>]*id="pg-news"[^>]*>\s*)[\s\S]*?(</div>\s*\n<!-- .*?PAGE 3)'
    new = re.sub(pattern, lambda m: m.group(1)+"\n"+news_html+"\n\n"+m.group(2), content)
    if new == content:
        raise ValueError("Could not find news page in index.html")
    content = new
    content = re.sub(r'EOD data \w+ \d+ \w+ \d+', f'EOD data {TODAY_DISPLAY}', content)
    content = re.sub(r'EOD · \w+ \d+ \w+ \d+',    f'EOD · {TODAY_DISPLAY}',    content)
    with open("index.html","w",encoding="utf-8") as f:
        f.write(content)
    print(f"  OK: index.html patched ({len(content):,} bytes)")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*60}\n  Investa Dashboard Refresh — {TODAY}\n{'='*60}\n")

    price_js = None
    try:
        price_js = build_price_js(fetch_prices())
    except Exception as e:
        print(f"  FAIL prices: {e}")

    news_data = None
    try:
        news_data = fetch_news()
    except Exception as e:
        print(f"  FAIL news: {e}")

    ti, tf = {}, {}
    if news_data:
        try: ti = translate_news(news_data, "Italian")
        except Exception as e: print(f"  FAIL IT translate: {e}")
        try: tf = translate_news(news_data, "French")
        except Exception as e: print(f"  FAIL FR translate: {e}")

    news_html = None
    if news_data:
        try:
            news_html = build_news_html(news_data, ti, tf)
            print(f"  OK news HTML: {len(news_html):,} bytes")
        except Exception as e:
            print(f"  FAIL news HTML: {e}")

    try:
        patch_html(
            price_js  or "const D = {};",
            news_html or "<div id='pg-news-inner' style='padding:12px 14px'><p>Refresh failed — check Actions log.</p></div>"
        )
    except Exception as e:
        print(f"  FAIL patch: {e}")
        raise

    port_map = {}
    try:
        port_map = fetch_portfolio_news()
    except Exception as e:
        print(f"  FAIL portfolio news: {e}")

    pit, pft = {}, {}
    if port_map:
        try: pit = translate_portfolio_news(port_map, "Italian")
        except Exception as e: print(f"  FAIL portfolio IT: {e}")
        try: pft = translate_portfolio_news(port_map, "French")
        except Exception as e: print(f"  FAIL portfolio FR: {e}")

    if port_map:
        try:
            patch_portfolio_news(port_map, pit, pft)
        except Exception as e:
            print(f"  FAIL portfolio patch: {e}")

    print(f"\n{'='*60}\n  Refresh complete.\n{'='*60}\n")

if __name__ == "__main__":
    main()
