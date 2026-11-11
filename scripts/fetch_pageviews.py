"""Validate mapped Wikipedia titles, then fetch monthly en.wikipedia pageviews. Resumable.

Input:  data/raw/wiki_map/*.jsonl
Output: data/raw/wiki_titles.json (requested title -> resolved title or null)
        data/raw/pageviews.json   (resolved title -> {YYYYMM: views})
"""
import json, os, time, urllib.parse, sys
sys.path.insert(0, 'scripts'); from wiki_mappings import mappings
import requests

UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
TITLES, VIEWS = 'data/raw/wiki_titles.json', 'data/raw/pageviews.json'
load = lambda p: json.load(open(p)) if os.path.exists(p) else {}
titles, views = load(TITLES), load(VIEWS)

wanted = {t for r in mappings().values() for t in (r.get('brand_article'), r.get('original_article')) if t}

todo = sorted(wanted - set(titles))
for i in range(0, len(todo), 50):
    batch = todo[i:i+50]
    q = requests.get('https://en.wikipedia.org/w/api.php', headers=UA, timeout=30, params={
        'action': 'query', 'format': 'json', 'redirects': 1, 'titles': '|'.join(batch)}).json()['query']
    norm = {x['from']: x['to'] for x in q.get('normalized', [])}
    redir = {x['from']: x['to'] for x in q.get('redirects', [])}
    exists = {p['title'] for p in q['pages'].values() if 'missing' not in p and 'invalid' not in p}
    for t in batch:
        n = norm.get(t, t)
        n = redir.get(n, n)
        titles[t] = n if n in exists else None
    json.dump(titles, open(TITLES, 'w'))
    time.sleep(1.5)
print('titles', len(titles), 'invalid', sum(v is None for v in titles.values()), flush=True)

for n, t in enumerate(sorted({v for v in titles.values() if v} - set(views))):
    a = urllib.parse.quote(t.replace(' ', '_'), safe='')
    res = requests.get('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/'
                       f'{a}/monthly/20150701/20261031', headers=UA, timeout=30)
    if res.status_code == 429:
        print('rate limited; rerun later', flush=True)
        break
    views[t] = {i['timestamp'][:6]: i['views'] for i in res.json().get('items', [])} if res.ok else {}
    if n % 50 == 0:
        json.dump(views, open(VIEWS, 'w'))
    time.sleep(0.3)
json.dump(views, open(VIEWS, 'w'))
print('views', len(views), 'empty', sum(not v for v in views.values()))

# Short histories can be page moves. Cache redirect lists so reruns do not add traffic twice.
C = 'data/raw/short_redirects.json'; done = load(C)
for t in sorted(t for t, s in views.items() if len(s) < 24 and t not in done):
    reds, cont = [], {}
    while True:
        r = requests.get('https://en.wikipedia.org/w/api.php', headers=UA, timeout=30, params={
            'action': 'query', 'format': 'json', 'titles': t, 'prop': 'redirects',
            'rdnamespace': 0, 'rdlimit': 'max', **cont})
        r.raise_for_status(); q = r.json()
        if 'error' in q: raise RuntimeError(q['error'])
        reds += [x['title'] for p in q['query']['pages'].values() for x in p.get('redirects', []) if x['title'] != t]
        time.sleep(0.3)
        cont = q.get('continue', {})
        if not cont: break
    merged = dict(views[t])
    for rt in sorted(set(reds)):
        a = urllib.parse.quote(rt.replace(' ', '_'), safe='')
        r = requests.get('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/'
                         f'{a}/monthly/20150701/20261031', headers=UA, timeout=30)
        if r.status_code == 429: raise SystemExit('rate limited; rerun later')
        if r.status_code != 404: r.raise_for_status()
        for x in r.json().get('items', []) if r.ok else []:
            k = x['timestamp'][:6]; merged[k] = merged.get(k, 0) + x['views']
        time.sleep(0.3)
    # Cache the finished result first; a rerun can safely restore it after interruption.
    done[t] = {'redirects': sorted(set(reds)), 'views': merged}
    json.dump(done, open(C, 'w'))
    views[t] = merged; json.dump(views, open(VIEWS, 'w'))
for t, r in done.items(): views[t] = r['views']
json.dump(views, open(VIEWS, 'w'))
