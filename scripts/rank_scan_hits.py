"""Rank scan hits by median monthly Wikipedia pageviews. Resumable."""
import concurrent.futures, json, os, statistics, threading, time
from urllib.parse import quote
import requests

UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
CACHE = 'data/raw/scan_rank_views.json'; OUTPUT = 'data/raw/scan_ranked.jsonl'
URL = 'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{}/monthly/20251001/20261031'
local = threading.local()


def load_hits():
    existing = {r['word'].lower() for r in json.load(open('data/candidates.json'))}
    hits = []
    for line in open('data/raw/disambig/hits.jsonl'):
        r = json.loads(line); word = r['word'].lower()
        if word not in existing:
            hits.append({'word': word, 'article': r['article title'], 'description': r['short description'], 'type': r['type'], 'source': 'disambig'})
    for title, article in json.load(open('data/raw/scan_hits.json'))['hits'].items():
        word, qualifier = title.rsplit(' (', 1); word = word.lower()
        if word not in existing and not article.endswith('(disambiguation)'):
            hits.append({'word': word, 'article': article, 'description': '', 'type': qualifier[:-1], 'source': 'titles'})
    return hits


def median_views(items):
    months = {str(x['timestamp'])[:6]: x['views'] for x in items}
    return statistics.median(months.get(f'{year}{month:02}', 0) for year, month in [(2025, m) for m in range(10, 13)] + [(2026, m) for m in range(1, 11)])


def fetch(title):
    if not hasattr(local, 'session'):
        local.session = requests.Session(); local.session.headers.update(UA)
    url = URL.format(quote(title.replace(' ', '_'), safe=''))
    for attempt in range(12):
        try:
            r = local.session.get(url, timeout=30)
            if r.status_code == 404: return 0
            if r.status_code == 429 or 500 <= r.status_code < 600:
                raise requests.HTTPError(f'{r.status_code} for {title}')
            r.raise_for_status()
            return median_views(r.json()['items'])
        except requests.RequestException as e:
            if isinstance(e, requests.HTTPError) and e.response is not None: raise
            if attempt == 11: raise
            time.sleep(min(120, 5 * 2 ** attempt))


def rank(hits, views):
    best = {}
    for hit in hits:
        row = dict(hit, views=views[hit['article']]); word = row['word']
        if word not in best or row['views'] > best[word]['views']: best[word] = row
    return sorted(best.values(), key=lambda r: (-r['views'], r['word']))


def save(views):
    with open(CACHE + '.tmp', 'w') as f: json.dump(views, f)
    os.replace(CACHE + '.tmp', CACHE)


def main():
    hits = load_hits(); views = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    todo = sorted({r['article'] for r in hits} - views.keys())
    print('titles', len(todo), 'cached', len(views), flush=True)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(fetch, title): title for title in todo}
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                views[futures[future]] = future.result()
                if i % 500 == 0: save(views)
                if i % 1000 == 0: print('fetched', i, 'of', len(todo), flush=True)
    finally:
        save(views)
    rows = rank(hits, views)
    with open(OUTPUT, 'w') as f:
        for row in rows: f.write(json.dumps(row, ensure_ascii=False) + '\n')
    for threshold in (1000, 3000, 10000, 30000):
        print('views >=', threshold, sum(r['views'] >= threshold for r in rows), flush=True)


if __name__ == '__main__': main()
