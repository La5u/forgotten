"""Fetch 1800-2022 Google Books series per word (ordinary-word casing). Resumable; backs off and stops on rate limits."""
import json, os, time, requests
OUT = 'data/raw/ngrams_1800.json'
have = json.load(open(OUT)) if os.path.exists(OUT) else {}
def form(r):
    return r['word'].capitalize() if r['kind'] == 'name' else r['word'].lower()
todo = sorted({form(r) for r in json.load(open('data/candidates.json'))} - set(have))
print('todo', len(todo), flush=True)
fails = 0
for i in range(0, len(todo), 12):
    batch = todo[i:i+12]
    res = requests.get('https://books.google.com/ngrams/json', timeout=30, params={
        'content': ','.join(batch), 'year_start': 1800, 'year_end': 2022, 'corpus': 'en', 'smoothing': 0})
    if res.status_code != 200:
        fails += 1
        print('http', res.status_code, 'at', i, flush=True)
        if fails >= 3:
            print('stopping; rerun later'); break
        time.sleep(60 * fails); continue
    fails = 0
    got = {r['ngram']: r['timeseries'] for r in res.json()}
    for w in batch:
        have[w] = got.get(w)          # None = not in corpus
    json.dump(have, open(OUT, 'w'))
    time.sleep(3)
print('done', len(have), 'missing-from-corpus', sum(v is None for v in have.values()))
