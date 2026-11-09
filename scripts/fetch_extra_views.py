"""Monthly views (title + all its redirects) for article titles set by hand in data/review_fixes.json
(brand_article / original_article). Output: data/raw/extra_views.json (title -> {YYYYMM: views})."""
import json, os, time, urllib.parse
import requests
UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
P = 'data/raw/extra_views.json'; out = json.load(open(P)) if os.path.exists(P) else {}
F = json.load(open('data/review_fixes.json'))['fix']
want = ({v[k] for v in F.values() for k in ('brand_article', 'original_article') if v.get(k)} | {t for v in F.values() for t in v.get('extra_brand_articles', [])}) - set(out)
def views(t):
    r = requests.get('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/'
                     + urllib.parse.quote(t.replace(' ', '_'), safe='') + '/monthly/20150701/20261031', headers=UA, timeout=30)
    return {i['timestamp'][:6]: i['views'] for i in r.json().get('items', [])} if r.ok else {}
for t in sorted(want):
    q = requests.get('https://en.wikipedia.org/w/api.php', headers=UA, timeout=30, params={'action': 'query', 'format': 'json',
        'titles': t, 'redirects': 1, 'prop': 'redirects', 'rdnamespace': 0, 'rdlimit': 'max'}).json()['query']
    page = list(q['pages'].values())[0]
    if 'missing' in page: print('missing', t); continue
    s = views(page['title'])
    for r in page.get('redirects', []):
        for k, x in views(r['title']).items(): s[k] = s.get(k, 0) + x
        time.sleep(0.15)
    out[t] = s; print(t, '->', page['title'], len(page.get('redirects', [])))
json.dump(out, open(P, 'w'))
