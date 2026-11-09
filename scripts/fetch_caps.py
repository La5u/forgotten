"""Add Capitalized Google Books series for common/rare words, for the case-shift signal. Resumable."""
import json, os, time, requests
OUT = 'data/raw/ngrams.json'
have = json.load(open(OUT))
todo = sorted({r['word'].capitalize() for r in json.load(open('data/candidates.json')) if r['kind'] != 'name'} - set(have))
print('todo', len(todo), flush=True)
fails = 0
for i in range(0, len(todo), 12):
    b = todo[i:i+12]
    res = requests.get('https://books.google.com/ngrams/json', timeout=30, params={
        'content': ','.join(b), 'year_start': 1980, 'year_end': 2022, 'corpus': 'en', 'smoothing': 0})
    if res.status_code != 200:
        fails += 1; print('http', res.status_code, flush=True)
        if fails >= 3:
            print('stopping; rerun later'); break
        time.sleep(60 * fails); continue
    fails = 0
    got = {r['ngram']: r['timeseries'] for r in res.json()}
    for w in b:
        have[w] = got.get(w)
    json.dump(have, open(OUT, 'w')); time.sleep(3)
print('done', len(have))
