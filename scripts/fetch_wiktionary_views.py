"""Monthly en.wiktionary page views for the plain word, the stand-in for the original meaning when it has no
Wikipedia article of its own. Same agent filter (user) and months as fetch_pageviews.py. Resumable.

Titles are case-sensitive: lowercase = the common word; for kind name/place the capitalised title is fetched too.
Output: data/raw/wiktionary/titles.json (title -> true/false: page exists)
        data/raw/wiktionary/views.json  (existing title -> {YYYYMM: views}; months with no views are absent)
        data/raw/wiktionary/wikitext.json (existing title -> current wikitext)
"""
import json, os, time, urllib.parse, concurrent.futures as cf
import requests

UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
D = 'data/raw/wiktionary'; os.makedirs(D, exist_ok=True)
TITLES, VIEWS = f'{D}/titles.json', f'{D}/views.json'
load = lambda p: json.load(open(p)) if os.path.exists(p) else {}
titles, views = load(TITLES), load(VIEWS)

def wanted(r):
    w = r['word'].lower()
    return [w, w.capitalize()] if r['kind'] in ('name', 'place') else [w]
rows = json.load(open('data/judged.json'))
want = sorted({t for r in rows for t in wanted(r)})

# Existence check (no redirects: a redirect is a different spelling, not the word's own page).
todo = [t for t in want if t not in titles]
for i in range(0, len(todo), 50):
    batch = todo[i:i+50]
    q = requests.get('https://en.wiktionary.org/w/api.php', headers=UA, timeout=30, params={
        'action': 'query', 'format': 'json', 'titles': '|'.join(batch)}).json()['query']
    norm = {x['from']: x['to'] for x in q.get('normalized', [])}
    exists = {p['title'] for p in q['pages'].values() if 'missing' not in p and 'invalid' not in p and 'redirect' not in p}
    for t in batch: titles[t] = norm.get(t, t) in exists
    json.dump(titles, open(TITLES, 'w'))
    time.sleep(1)
print('titles', len(titles), 'exist', sum(titles.values()), flush=True)

def fetch(t):
    a = urllib.parse.quote(t.replace(' ', '_'), safe='')
    for wait in (2, 5, 15, 30, 60):
        r = requests.get('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wiktionary/all-access/user/'
                         f'{a}/monthly/20150701/20261031', headers=UA, timeout=30)
        if r.status_code == 429 or r.status_code >= 500: time.sleep(wait); continue
        if r.status_code == 404: return t, {}  # page exists but no recorded views
        r.raise_for_status()
        return t, {i['timestamp'][:6]: i['views'] for i in r.json().get('items', [])}
    raise SystemExit('rate limited; rerun later')

todo = [t for t in want if titles.get(t) and t not in views]
with cf.ThreadPoolExecutor(4) as ex:
    for n, (t, v) in enumerate(ex.map(fetch, todo)):
        views[t] = v
        if n % 100 == 0: json.dump(views, open(VIEWS, 'w')); print(n, '/', len(todo), flush=True)
json.dump(views, open(VIEWS, 'w'))
print('views', len(views), 'empty', sum(not v for v in views.values()))

# Current wikitext of each existing page, to drop form-of stubs ("plural of") and pages with no English section.
WIKITEXT = f'{D}/wikitext.json'; text = load(WIKITEXT)
todo = [t for t in want if titles.get(t) and t not in text]
for i in range(0, len(todo), 50):
    batch = todo[i:i+50]
    q = requests.get('https://en.wiktionary.org/w/api.php', headers=UA, timeout=60, params={
        'action': 'query', 'format': 'json', 'formatversion': 2, 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main',
        'titles': '|'.join(batch)}).json()['query']
    for p in q['pages']:
        if 'revisions' in p: text[p['title']] = p['revisions'][0]['slots']['main']['content']
    json.dump(text, open(WIKITEXT, 'w'))
    time.sleep(1)
print('wikitext', len(text))
