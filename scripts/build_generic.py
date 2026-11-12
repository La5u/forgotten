"""Build generic trademark casing trends from Google Books. Rerun to resume."""
import json, os, re, time, requests

RAW = 'data/raw/generic/list.jsonl'
CACHE = 'data/raw/generic/ngrams.json'
OUT = 'site/generic.json'
URL = 'https://books.google.com/ngrams/json'


def variants(row):
    word = row['word'].lower()
    lower = {word}
    if str(row.get('pos', '')).lower() in ('verb', 'both'):
        lower.update(word + suffix for suffix in ('ed', 'd', 'ing'))
        if word.endswith('e'):
            lower.add(word[:-1] + 'ing')
        if word and word[-1] in 'bcdfghjklmnpqrstvwxyz':
            lower.update(word + word[-1] + suffix for suffix in ('ed', 'ing'))
    cap = {word[:1].upper() + word[1:], word.title(), word.upper()}
    if row.get('brand'):
        cap.add(row['brand'])
    return lower, cap - lower


def normal(s):
    return re.sub(r'\s*-\s*', '-', ' '.join(s.split()))


def match(batch, rows):
    # Google may insert spaces around punctuation or omit absent queries.
    found = {}
    for row in rows:
        candidates = [q for q in batch if normal(q) == normal(row['ngram'])]
        if len(candidates) == 1:
            found[candidates[0]] = row['timeseries']
    if len(rows) == len(batch):
        for q, row in zip(batch, rows):
            if q not in found and not any(normal(row['ngram']) == normal(x) for x in found):
                found[q] = row['timeseries']
    return {q: found.get(q) for q in batch}


def fetch(queries, have):
    todo = sorted(set(queries) - have.keys())
    fails = 0
    for i in range(0, len(todo), 12):
        batch = todo[i:i + 12]
        res = requests.get(URL, timeout=30, params={'content': ','.join(batch),
            'year_start': 1900, 'year_end': 2019, 'corpus': 'en', 'smoothing': 0})
        if res.status_code != 200:
            fails += 1
            print('http', res.status_code, 'at', i, flush=True)
            if fails >= 3:
                print('stopping; rerun later')
                break
            time.sleep(60 * fails)
            continue
        fails = 0
        have.update(match(batch, res.json()))
        with open(CACHE, 'w') as f:
            json.dump(have, f)
        time.sleep(3)


def spaced(q):
    return re.sub(r'\s*-\s*', ' - ', q)


def series(q, have):
    result = have.get(q)
    if result is None and '-' in q:
        result = have.get(spaced(q))
    return result or [0] * 120


SKIP = {'lp', 'zoom', 'uber', 'mace', 'matchbox', 'coke'}  # ordinary words or abbreviations: case share says nothing


def build(row, have):
    lower, cap = variants(row)
    decades = {}
    for year in range(max(1900, row['launch_year'] // 10 * 10), 2020, 10):  # decades before launch are other senses
        start = year - 1900
        lo = sum(sum(series(q, have)[start:start + 10]) for q in lower)
        hi = sum(sum(series(q, have)[start:start + 10]) for q in cap)
        total = lo + hi
        decades[str(year)] = {'lower_share': lo / total if total else None,
                              'per_million': round(total / 10 * 1e6, 4)}
    recent = decades.get('2010', {'lower_share': None, 'per_million': None})
    return {**row, 'decades': decades, 'lower_share_recent': recent['lower_share'],
            'total_recent_per_million': recent['per_million'],
            'first_decade_majority_lower': next((y for y, d in decades.items()
                if d['lower_share'] is not None and d['lower_share'] > 0.5), None)}


def main():
    rows = []
    with open(RAW) as f:
        for line in f:
            try:
                row = json.loads(line)
                if row['word'] in SKIP: continue
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get('word'), str) and row['word']:
                rows.append(row)
    have = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    queries = set().union(*(set.union(*variants(row)) for row in rows))
    fetch(queries, have)
    fetch({spaced(q) for q in queries if '-' in q and q in have and have[q] is None}, have)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    entries = [build(row, have) for row in sorted(rows, key=lambda r: r['word'])]
    with open(OUT, 'w') as f:
        json.dump({'entries': entries}, f, ensure_ascii=False)
    print('word\tlower_share_recent\tfirst_decade_majority_lower')
    for row in entries:
        print(row['word'], row['lower_share_recent'], row['first_decade_majority_lower'], sep='\t')


if __name__ == '__main__':
    main()
