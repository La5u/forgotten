"""Check the second reader's article suggestions and report status differences."""
import collections, concurrent.futures, csv, glob, json, os, re, statistics, sys, time
from urllib.parse import quote
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wiki_mappings import mappings

UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
API = 'https://en.wikipedia.org/w/api.php'
REST = 'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/'
CHECK = 'data/raw/verify/title_check.json'
VIEWS = 'data/raw/verify/title_views.json'
MAP = 'data/raw/wiki_map/zv_gemini.jsonl'

def title(s):
    return s.strip().replace('_', ' ') if isinstance(s, str) and s.strip().lower() not in ('', 'false', 'none', 'null') else ''

def key(s):
    return title(s).casefold()

def has_word(s, word):
    return bool(word and re.search(r'(?<!\w)' + re.escape(title(word)) + r'(?!\w)', title(s), re.I))

def decide(side, current, suggested, word, owner):
    if not title(current): return 'accept'
    if side == 'brand':
        if (has_word(suggested, word) and not has_word(current, word)) or re.match(r'^list of\b', title(current), re.I) or (key(owner) and key(current) == key(owner)):
            return 'accept'
    elif re.search(r'\((surname|given name|name|disambiguation)\)$', title(current), re.I) or re.fullmatch(r'[^,]+,\s*[^,]+', title(current)):
        return 'accept'
    return 'review'

def parse_pages(batch, q):
    links = {x['from']: x['to'] for group in ('normalized', 'converted', 'redirects') for x in q.get(group, [])}
    pages = {p['title']: p for p in q['pages']}
    out = {}
    for t in batch:
        n, seen = t, set()
        while n in links and n not in seen:
            seen.add(n); n = links[n]
        p = pages.get(n, {})
        status = 'missing' if not p or 'missing' in p or 'invalid' in p else 'disambiguation' if 'disambiguation' in p.get('pageprops', {}) else 'ok'
        out[t] = {'status': status, 'title': p.get('title', n)}
    return out

def load(path):
    return json.load(open(path)) if os.path.exists(path) else {}

def save(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f: json.dump(data, f, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, path)

def get(url, **kwargs):
    for attempt in range(6):
        try:
            r = requests.get(url, headers=UA, timeout=30, **kwargs)
            if r.status_code == 429 or 500 <= r.status_code < 600:
                if attempt == 5: r.raise_for_status()
                retry = r.headers.get('Retry-After', '')
                time.sleep(max(2 ** attempt, min(int(retry), 120)) if retry.isdigit() else 2 ** attempt)
                continue
            return r
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 5: raise
            time.sleep(2 ** attempt)
    raise RuntimeError('request retries exhausted')

def check_titles(titles, cache):
    todo = sorted(set(titles) - cache.keys())
    for i in range(0, len(todo), 50):
        batch = todo[i:i+50]
        r = get(API, params={'action': 'query', 'titles': '|'.join(batch), 'redirects': 1, 'prop': 'pageprops|description', 'ppprop': 'disambiguation', 'format': 'json', 'formatversion': 2})
        r.raise_for_status(); data = r.json()
        if 'error' in data: raise RuntimeError(data['error'])
        cache.update(parse_pages(batch, data['query'])); save(CHECK, cache)
        print('titles', min(i+50, len(todo)), '/', len(todo), flush=True)
        time.sleep(0.6)

def fetch_views(t):
    url = REST + quote(t.replace(' ', '_'), safe='') + '/monthly/2025100100/2026103100'
    r = get(url)
    if r.status_code == 404: return 0
    r.raise_for_status()
    items = r.json()['items']
    if not items: raise ValueError('empty pageview response for ' + t)
    return statistics.median(x['views'] for x in items)

def check_views(titles, cache):
    todo = sorted(set(titles) - cache.keys())
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        pending = {}
        it = iter(todo)
        def submit():
            t = next(it, None)
            if t is not None: pending[pool.submit(fetch_views, t)] = t
        submit(); submit()
        while pending:
            done, _ = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
            for f in done:
                t = pending.pop(f); cache[t] = f.result(); save(VIEWS, cache)
                print('views', len(cache), t, flush=True)
                time.sleep(0.3); submit()

def write_tsv(path, fields, rows):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n'); w.writerow(fields); w.writerows(rows)

def main():
    site = {r['word'].lower(): r for r in json.load(open('site/data.json'))['entries']}
    judged = {r['word'].lower(): r for r in json.load(open('data/judged.json'))}
    readers = [json.loads(l) for l in open('data/raw/verify/gemini.jsonl') if l.strip()]
    maps = mappings(); candidates = []; statuses = []
    for r in readers:
        k = r['word'].lower()
        if k not in site or k not in judged: continue
        j, s = judged[k], site[k]
        if r.get('discontinued') != s.get('discontinued') or r.get('end_year') != s.get('end_year'):
            statuses.append((s['word'], s.get('discontinued'), s.get('end_year'), r.get('discontinued'), r.get('end_year')))
        brand_key = re.sub(r' \(\d{4}\)$', '', j['brand']).lower()
        m = maps.get((k, brand_key), j)
        for side in ('brand', 'original'):
            field = side + '_article'
            current = title(m.get(field))
            suggested = title(r.get(field + '_better'))
            if suggested and key(suggested) != key(current): candidates.append((j, side, current, suggested))
    checks = load(CHECK); check_titles((x[3] for x in candidates), checks)
    view_titles = set()
    for j, side, current, suggested in candidates:
        if checks[suggested]['status'] == 'ok':
            view_titles.add(checks[suggested]['title'])
            if current: view_titles.add(current)
    views = load(VIEWS); check_views(view_titles, views)
    changes, rows = {}, []
    if os.path.exists(MAP):
        for line in open(MAP):
            if line.strip():
                row = json.loads(line); changes[(row['word'].lower(), row['brand'].lower())] = row
    for j, side, current, suggested in candidates:
        result = checks[suggested]; status = result['status']
        resolved = result['title'] if status == 'ok' else suggested
        decision = decide(side, current, resolved, j['word'], j.get('owner')) if status == 'ok' else 'rejected-' + status
        cv = views.get(current, '') if current else ''
        sv = views.get(resolved, '') if status == 'ok' else ''
        rows.append((j['word'], side, current, cv, resolved, sv, decision))
        if decision == 'accept' and key(current) != key(resolved):
            k = (j['word'].lower(), j['brand'].lower())
            row = changes.setdefault(k, {'word': j['word'], 'brand': j['brand'], 'is_real_prior_word': True, 'brand_named_after_word': True})
            row[side + '_article'] = resolved
    rows.sort(key=lambda r: (r[6], r[0].lower(), r[1]))
    write_tsv('data/raw/verify/article_changes.tsv', ['word', 'side', 'current', 'current_views', 'suggested', 'suggested_views', 'decision'], rows)
    write_tsv('data/raw/verify/status_changes.tsv', ['word', 'current discontinued', 'current end_year', 'reader discontinued', 'reader end_year'], sorted(statuses, key=lambda r: r[0].lower()))
    newest = max((os.stat(p).st_mtime_ns for p in glob.glob('data/raw/wiki_map/*.jsonl') if p != MAP), default=0)
    with open(MAP, 'w') as f:
        for k in sorted(changes): f.write(json.dumps(changes[k], ensure_ascii=False) + '\n')
    now = max(time.time_ns(), newest + 1); os.utime(MAP, ns=(now, now))
    counts = collections.Counter(r[6] for r in rows)
    for decision in ('accept', 'review', 'rejected-missing', 'rejected-disambiguation'): print(decision, counts[decision])
    for r in sorted((r for r in rows if r[6] == 'accept'), key=lambda r: abs((r[5] or 0) - (r[3] or 0)), reverse=True)[:40]: print(*r, sep='\t')

if __name__ == '__main__': main()
