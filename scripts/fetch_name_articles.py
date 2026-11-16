"""Wikipedia articles about a given name ("Mercedes (name)", "Kimi (given name)", or a plain "Mickey" whose first sentence calls it a given name) as the original-meaning side for
kind name/place entries that have no comparison article. Redirects are followed; disambiguation pages are skipped.
Output: data/raw/name_articles.json (word -> [article, median monthly user views 2025-11..2026-10])."""
import json, re, statistics, time, urllib.parse, requests
UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
LAST12 = [f'{y}{m:02d}' for y in (2025, 2026) for m in range(1, 13) if '202511' <= f'{y}{m:02d}' <= '202610']
words = [e['word'] for e in json.load(open('site/data.json'))['entries'] if e['kind'] in ('name', 'place') and not e.get('original_views')]
cands = [f'{w} ({s})' for w in words for s in ('given name', 'name')]
found = {}
for i in range(0, len(cands), 50):
    q = requests.get('https://en.wikipedia.org/w/api.php', headers=UA, timeout=30, params={'action': 'query', 'format': 'json',
        'formatversion': 2, 'redirects': 1, 'prop': 'pageprops', 'ppprop': 'disambiguation', 'titles': '|'.join(cands[i:i+50])}).json()['query']
    red = {r['from']: r['to'] for r in q.get('redirects', [])}
    ok = {p['title'] for p in q['pages'] if not p.get('missing') and 'disambiguation' not in p.get('pageprops', {})}
    for c in cands[i:i+50]:
        t, w = red.get(c, c), c.split(' (')[0]
        if t in ok and w not in found and t.split(' (')[0] == w and '(' in t: found[w] = t  # must still be a name article, not the brand
# Plain title ("Mickey", "Celine" -> "Céline") when it is itself the name article, not a disambiguation page.
rest = [w for w in words if w not in found]
red, pages = {}, {}
for i in range(0, len(rest), 20):  # extracts are returned for at most 20 pages per request
    q = requests.get('https://en.wikipedia.org/w/api.php', headers=UA, timeout=30, params={'action': 'query', 'format': 'json', 'formatversion': 2,
        'redirects': 1, 'prop': 'pageprops|extracts', 'ppprop': 'disambiguation', 'exintro': 1, 'explaintext': 1, 'exsentences': 1, 'exlimit': 'max', 'titles': '|'.join(rest[i:i+20])}).json()['query']
    red |= {r['from']: r['to'] for r in q.get('redirects', [])}
    pages |= {p['title']: p for p in q['pages'] if not p.get('missing') and 'disambiguation' not in p.get('pageprops', {})}
for w in rest:
    p = pages.get(red.get(w, w))
    if p and re.search(r'\b(given|first) name\b', p.get('extract', '')): found[w] = p['title']
def load_prev():
    try: return json.load(open('data/raw/name_articles.json'))  # build fills original_views from this file, so keep earlier finds
    except FileNotFoundError: return {}
def med(t):
    a = urllib.parse.quote(t.replace(' ', '_'), safe='')
    r = requests.get(f'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{a}/monthly/20251101/20261031', headers=UA, timeout=30)
    v = {i['timestamp'][:6]: i['views'] for i in r.json().get('items', [])} if r.ok else {}
    time.sleep(.3)
    return statistics.median(v.get(k, 0) for k in LAST12)
out = load_prev() | {w.lower(): [t, v] for w, t in found.items() if (v := med(t))}  # no recorded views = no figure
json.dump(out, open('data/raw/name_articles.json', 'w'), indent=1)
print(len(words), 'checked;', out)
