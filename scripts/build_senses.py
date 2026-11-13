"""Collect and build runner-up brand senses; fetch missing article views."""
import json, os, statistics, sys, time
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, 'scripts'); from wiki_mappings import mappings
from merge_preferences import SWAPS
P = 'data/raw/senses'
UA = 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'
def read(p, default=None):
    return json.load(open(p)) if os.path.exists(p) else default
def lines(p):
    for l in open(p):
        try:
            r = json.loads(l)
            if isinstance(r, dict): yield r
        except ValueError: pass
def title(t):
    return t.replace('_', ' ').strip() if t else None
def published():
    return {r['word'].lower(): r for r in read('site/data.json')['entries']}
def pub_articles(entries):
    judged = {r['word'].lower(): r for r in read('data/judged.json')}
    out = {}
    for w, e in entries.items():
        u = urlparse(e.get('source_url') or '')
        t = unquote(u.path[6:]) if u.hostname in ('en.wikipedia.org', 'www.en.wikipedia.org') and u.path.startswith('/wiki/') else None
        r = judged.get(w, {})
        out[w] = title(t or (r.get('brand_article') if r.get('brand', '').lower() == e['brand'].lower() else None))
    return out

def collect():
    entries = published(); articles = pub_articles(entries); maps = mappings()
    titles = read('data/raw/wiki_titles.json'); views = read('data/raw/pageviews.json')
    tv = read('data/raw/verify/title_views.json'); alts = {}; seen = {}
    months = [f'{y}{m:02d}' for y in (2025, 2026) for m in range(1, 13) if '202511' <= f'{y}{m:02d}' <= '202610']
    def add(w, brand, article, v, owner=None, launch_year=None):
        e = entries.get(w); article = title(article)
        if not e or not brand or brand.lower() == e['brand'].lower(): return
        if article and article == articles[w]: return
        if v is not None and e.get('brand_views') is not None and v < e['brand_views']/3: return
        key = article or ('brand:' + brand.lower())
        if key in seen.setdefault(w, set()): return
        seen[w].add(key)
        alts.setdefault(w, []).append(dict(brand=brand, article=article, views=v, owner=owner, launch_year=launch_year))
    for r in read('data/candidates.json'):
        w, b = r['word'].lower(), r['brand']
        t = titles.get(maps.get((w, b.lower()), {}).get('brand_article'))
        v = views.get(t)
        add(w, b, t, statistics.median(v.get(m, 0) for m in months) if v else None, r.get('owner'), r.get('launch_year'))
    for r in lines('data/raw/verify/gemini.jsonl'):
        w = r.get('word', '').lower(); t = r.get('brand_article_better')
        add(w, r.get('best_brand'), t, tv.get(t))
    alts = dict(sorted(alts.items()))
    os.makedirs(P, exist_ok=True)
    json.dump(alts, open(P + '/alts.json', 'w'), indent=2, ensure_ascii=False)
    with open(P + '/prompt.txt', 'w') as f:
        f.write('Each line is word | published brand | alternative brand | Wikipedia article | monthly views. Research each alternative using the web. Return JSON Lines, one per line, no prose: {"word": lowercase, "alt": the alternative brand exactly as given, "bare_word": true only if the general public calls this alternative by the bare word alone (Sonic yes; Ford Explorer or Samsung Galaxy as just Galaxy yes if people do say it; Kia Soul no), "same_thing": true if it is the same brand/product/franchise as the published brand under another name or its parent (then it is not a runner-up), "brand": short display name, "owner": company/creator, "launch_year": int, "what": the thing in under 8 words starting lowercase with an article, e.g. "the British rock band", "the fast-food drive-in chain", "article": exact English Wikipedia title of the alternative itself}.\n\n')
        for w, rows in alts.items():
            for r in rows: f.write(f"{w} | {entries[w]['brand']} | {r['brand']} | {r['article'] or ''} | {r['views'] if r['views'] is not None else ''}\n")
    print(sum(map(len, alts.values())), 'alternatives,', len(alts), 'words')

def build():
    entries = published(); articles = pub_articles(entries); alts = read(P + '/alts.json'); fetched = read(P + '/views.json', {})
    out = {}; need = set(); seen = {}
    for r in lines(P + '/checked.jsonl'):
        w = r.get('word', '').lower(); e = entries.get(w)
        if not e or r.get('bare_word') is not True or r.get('same_thing') is not False: continue
        a = next ( (a for a in alts.get(w, []) if a['brand'] == r.get('alt')), None)
        if not a: continue
        t = title(r.get('article'))
        if not t or t == articles[w]: continue
        v = fetched.get(t)
        if v is None and t == title(a.get('article')): v = a.get('views')
        if v is None: need.add(t); continue
        if e.get('brand_views') is None or v < e['brand_views']/3: continue
        if t in seen.setdefault(w, set()): continue
        seen[w].add(t)
        out.setdefault(w, []).append(dict(brand=r.get('brand'), owner=r.get('owner'), launch_year=r.get('launch_year'), what=r.get('what'), views=v, article=t))
    for w, s in SWAPS.items():  # Keep the former published brands even below the traffic cutoff.
        if w in entries: out[w] = s['senses']
    out = {w: sorted(rows, key=lambda r: r['views'], reverse=True)[:2] for w, rows in sorted(out.items())}
    json.dump(out, open('data/senses.json', 'w'), indent=2, ensure_ascii=False)
    with open(P + '/need_views.txt', 'w') as f:
        for t in sorted(need): f.write(t + '\n')
    for w, rows in out.items():
        print(f"{w}: {entries[w]['brand']} ({entries[w]['brand_views']}) | " + ' | '.join(f"{r['brand']} ({r['views']})" for r in rows))
    print('Alternatives with more views:')
    for w, rows in out.items():
        for r in rows:
            if r['views'] > entries[w]['brand_views']: print(f"{w}: {r['brand']} ({r['views']}) > {entries[w]['brand']} ({entries[w]['brand_views']})")
    print(len(need), 'titles need views')

def fetch_views():
    result = read(P + '/views.json', {})
    for t in dict.fromkeys(l.strip() for l in open(P + '/need_views.txt') if l.strip()):
        if t in result: continue
        url = 'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/' + quote(t.replace(' ', '_'), safe='') + '/monthly/20251001/20261031'
        delay = 1
        while True:
            try:
                with urlopen(Request(url, headers={'User-Agent': UA}), timeout=30) as response: data = json.load(response)
                monthly = {x['timestamp'][:6]: x['views'] for x in data['items']}
                result[t] = statistics.median(monthly.get(f'{y}{m:02d}', 0) for y in (2025, 2026) for m in range(1, 13) if '202511' <= f'{y}{m:02d}' <= '202610')
                break
            except HTTPError as e:
                if e.code == 404: result[t] = 0; break
                if e.code != 429: raise
                time.sleep(delay); delay = min(delay * 2, 60)
        json.dump(result, open(P + '/views.json', 'w'), indent=2, ensure_ascii=False)
        time.sleep(0.3)
    print(len(result), 'titles with views')

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('collect', 'build', 'views'): sys.exit('Usage: python3 -I scripts/build_senses.py collect|build|views')
    {'collect': collect, 'build': build, 'views': fetch_views}[sys.argv[1]]()
