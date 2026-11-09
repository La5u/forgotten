"""Brand-first scan: which given names / dictionary words have a Wikipedia article titled 'X (company|software|...)'?
Batches 50 titles per API query (existence only, redirects followed). Resumable. Output: data/raw/scan_hits.json"""
import collections, glob, json, os, sys, time
import requests
sys.path.insert(0, 'scripts'); from english import LOWER
UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
P = 'data/raw/scan_hits.json'; S = json.load(open(P)) if os.path.exists(P) else {'done': [], 'hits': {}}
done = set(S['done'])
peak = collections.Counter()
for f in glob.glob('data/raw/ssa/yob19[5-9]*.txt') + glob.glob('data/raw/ssa/yob20*.txt'):
    for l in open(f):
        n, s, c = l.strip().split(','); peak[n] = max(peak[n], int(c))
names = sorted(n for n, c in peak.items() if c >= 300)
words = sorted(w.capitalize() for w in LOWER if w.isalpha() and len(w) >= 4 and w.capitalize() not in peak)
NS = ['company', 'software', 'app', 'chatbot', 'language model', 'virtual assistant', 'brand', 'AI']
WS = ['company', 'software', 'app', 'brand']
titles = [f'{n} ({s})' for n in names for s in NS] + [f'{w} ({s})' for w in words for s in WS]
todo = [t for t in titles if t not in done]
print('names', len(names), 'words', len(words), 'titles', len(titles), 'todo', len(todo), flush=True)
for i in range(0, len(todo), 50):
    b = todo[i:i+50]
    try:
        q = requests.get('https://en.wikipedia.org/w/api.php', headers=UA, timeout=30, params={'action': 'query', 'format': 'json',
            'redirects': 1, 'titles': '|'.join(b)}).json()['query']
    except Exception as e:
        print('err', e, flush=True); time.sleep(30); continue
    norm = {x['from']: x['to'] for x in q.get('normalized', [])}; red = {x['from']: x['to'] for x in q.get('redirects', [])}
    ok = {p['title'] for p in q['pages'].values() if 'missing' not in p and 'invalid' not in p}
    for t in b:
        n = red.get(norm.get(t, t), norm.get(t, t))
        if n in ok: S['hits'][t] = n
    S['done'] += b
    if i % 2500 == 0:
        json.dump(S, open(P, 'w')); print(i, len(todo), 'hits', len(S['hits']), flush=True)
    time.sleep(0.6)
json.dump(S, open(P, 'w')); print('done hits', len(S['hits']))
