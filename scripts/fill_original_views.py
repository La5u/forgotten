"""Fill missing original-meaning traffic: Terra picked the closest Wikipedia article for the original sense
(data/raw/orig_fill/*.jsonl); validate it (exists, not a disambiguation page), fetch median monthly views
2024-11..2026-10 into data/raw/orig_fill/views.json as {word: [title, views]}."""
import glob, json, statistics, time, urllib.parse
import requests
UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
want = {}
for p in glob.glob('data/raw/orig_fill/*.jsonl'):
    for l in open(p):
        if l.strip().startswith('{'):
            r = json.loads(l)
            if r.get('original_article'): want[r['word'].lower()] = r['original_article']
out = {}
items = list(want.items())
for i in range(0, len(items), 40):
    batch = items[i:i+40]
    q = requests.get('https://en.wikipedia.org/w/api.php', headers=UA, timeout=30, params={'action': 'query', 'format': 'json', 'redirects': 1,
        'prop': 'pageprops', 'ppprop': 'disambiguation', 'titles': '|'.join(t for _, t in batch)}).json()['query']
    norm = {x['from']: x['to'] for x in q.get('normalized', [])}; red = {x['from']: x['to'] for x in q.get('redirects', [])}
    ok = {p['title'] for p in q['pages'].values() if 'missing' not in p and 'invalid' not in p and 'disambiguation' not in p.get('pageprops', {})}
    for w, t in batch:
        n = red.get(norm.get(t, t), norm.get(t, t))
        if n in ok: out[w] = [n, None]
    time.sleep(1)
for w, (t, _) in out.items():
    r = requests.get('https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/'
                     + urllib.parse.quote(t.replace(' ', '_'), safe='') + '/monthly/20241101/20261031', headers=UA, timeout=30)
    xs = [x['views'] for x in r.json().get('items', [])] if r.ok else []
    out[w][1] = statistics.median(xs) if xs else None
    time.sleep(0.3)
json.dump(out, open('data/raw/orig_fill/views.json', 'w'), indent=0)
print('asked', len(want), 'valid', len(out), 'with views', sum(v[1] is not None for v in out.values()))
