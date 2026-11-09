"""Wikipedia page moves split an article's traffic across titles (Claude (language model) -> Claude (AI) in
2026-06). For every article with an abrupt break, add the monthly views of all titles that now redirect to it.
Resumable. Output: data/raw/pageviews_merged.json (title -> {YYYYMM: views}); unflagged titles copied as-is."""
import json, os, time, urllib.parse
import requests
UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
V = json.load(open('data/raw/pageviews.json'))
C = 'data/raw/redirect_views.json'; cache = json.load(open(C)) if os.path.exists(C) else {}
def flagged(s):
    xs = [s[k] for k in sorted(s)]
    for i in range(3, len(xs) - 2):
        a, b = sum(xs[i-3:i]) / 3 + 1, sum(xs[i:i+3]) / 3 + 1
        if (b / a < 0.2 or a / b < 0.2) and max(a, b) > 500: return True
    return False
def views(t):
    r = requests.get('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/'
                     + urllib.parse.quote(t.replace(' ', '_'), safe='') + '/monthly/20150701/20261031', headers=UA, timeout=30)
    if r.status_code == 429: raise SystemExit('rate limited; rerun')
    return {i['timestamp'][:6]: i['views'] for i in r.json().get('items', [])} if r.ok else {}
todo = [t for t, s in V.items() if s and flagged(s) and t not in cache]
for n, t in enumerate(todo):
    q = requests.get('https://en.wikipedia.org/w/api.php', headers=UA, timeout=30, params={'action': 'query', 'format': 'json',
        'titles': t, 'prop': 'redirects', 'rdnamespace': 0, 'rdlimit': 'max'}).json()['query']['pages']
    reds = [x['title'] for p in q.values() for x in p.get('redirects', [])]
    cache[t] = {}
    for rt in reds:
        s = views(rt)
        if sum(s.values()) > 100: cache[t][rt] = s  # skip negligible redirects
        time.sleep(0.2)
    if n % 10 == 0: json.dump(cache, open(C, 'w')); print(n, len(todo), t, len(reds), flush=True)
json.dump(cache, open(C, 'w'))
out = {}
for t, s in V.items():
    m = dict(s)
    for rs in cache.get(t, {}).values():
        for k, x in rs.items(): m[k] = m.get(k, 0) + x
    out[t] = m
json.dump(out, open('data/raw/pageviews_merged.json', 'w'))
print('merged', sum(1 for t in cache if cache[t]), 'articles gained redirect traffic')
