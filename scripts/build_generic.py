"""Build generic trademark casing trends from Google Books. Rerun to resume."""
import argparse, json, os, re, time, requests

RAW = 'data/raw/generic/list.jsonl'
CACHE = 'data/raw/generic/ngrams.json'
OUT = 'site/generic.json'
URL = 'https://books.google.com/ngrams/json'
HELD_LOWER_SHARE_THRESHOLD = 0.10


def plural(word):
    if re.search(r'[^aeiou\W\d_]y$', word, re.IGNORECASE):
        return word[:-1] + 'ies'
    return word + ('es' if word.lower().endswith(('s', 'x', 'z', 'ch', 'sh')) else 's')


def variants(row):
    spellings = {row['word'].lower()}
    spellings.update(s.lower() for s in row.get('alts', []) if isinstance(s, str) and s)
    for word in tuple(spellings):
        if '-' in word or ' ' in word:
            parts = re.split(r'[-\s]+', word)
            spellings.update(separator.join(parts) for separator in ('-', ' ', ''))
    lower = set(spellings)
    skipped = set(row.get('skip_forms', []))
    pos = str(row.get('pos', '')).lower()
    for words, forms in ((spellings, lower), (tuple(skipped), skipped)):
        for word in words:
            if pos in ('noun', 'both'):
                forms.add(plural(word))
            if pos in ('verb', 'both'):
                forms.update(word + suffix for suffix in ('ed', 'd', 'ing'))
                if word.endswith('e'):
                    forms.add(word[:-1] + 'ing')
                if word and word[-1] in 'bcdfghjklmnpqrstvwxyz':
                    forms.update(word + word[-1] + suffix for suffix in ('ed', 'ing'))
    lower.difference_update(skipped)
    cap = {form for word in lower for form in
           (word[:1].upper() + word[1:], word.title(), word.upper())}
    if row.get('brand'):
        cap.update((row['brand'], plural(row['brand'])))
    return lower, cap - lower


def normal(s):
    return re.sub(r"\s*([-'])\s*", r'\1', ' '.join(s.split()))


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
    share = recent['lower_share']
    group = 'lost' if row['status'] == 'lost' else (
        'held' if isinstance(share, (int, float)) and share < HELD_LOWER_SHARE_THRESHOLD else 'slipping')
    counts = {q: sum(series(q, have)[110:120]) for q in lower}
    lower_total = sum(counts.values())
    lower_forms = {q: round(count / lower_total, 3)
                   for q, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
                   if count > 0}
    return {**row, 'group': group, 'decades': decades, 'lower_share_recent': share,
            'lower_forms': lower_forms, 'top_lower_form': next(iter(lower_forms), None),
            'total_recent_per_million': recent['per_million'],
            'first_decade_majority_lower': next((y for y, d in decades.items()
                if d['lower_share'] is not None and d['lower_share'] > 0.5), None)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Build from the cache without fetching')
    parser.add_argument('--out', default=OUT, help='Output JSON path (default: %(default)s)')
    args = parser.parse_args()
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
    if not args.offline:
        fetch(queries, have)
        fetch({spaced(q) for q in queries if '-' in q and q in have and have[q] is None}, have)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    entries = [build(row, have) for row in sorted(rows, key=lambda r: r['word'])]
    with open(args.out, 'w') as f:
        json.dump({'entries': entries}, f, ensure_ascii=False)
    print('word\tlower_share_recent\tfirst_decade_majority_lower')
    for row in entries:
        print(row['word'], row['lower_share_recent'], row['first_decade_majority_lower'], sep='\t')


if __name__ == '__main__':
    main()
