"""Find brand-like uses on English Wikipedia disambiguation pages.

Run from the repo root: python -I scripts/scan_disambig.py [word_limit]
Progress and hits are stored in data/raw/disambig. A limit selects a stable
shuffled prefix; a later run without a limit continues across the full list.
"""
import collections, glob, json, math, os, random, re, sys, time
import requests
sys.path.insert(0, 'scripts'); from english import LOWER

UA = {'User-Agent': 'forgotten-research/0.1 (https://github.com/la5u/forgotten)'}
API = 'https://en.wikipedia.org/w/api.php'
DIR = 'data/raw/disambig'; STATE = DIR + '/state.json'; HITS = DIR + '/hits.jsonl'
COMMON = {'action': 'query', 'format': 'json', 'formatversion': 2, 'maxlag': 5}
PROPS = {'prop': 'pageprops|description', 'ppprop': 'disambiguation|wikibase-shortdesc'}

# Ordered, so the recorded type is stable when several keywords match.
TYPES = [
    ('video game', r'video games?|computer games?'), ('television series', r'television series|tv series'),
    ('company', r'compan(?:y|ies)|corporation|business|enterprise|firm'),
    ('brand', r'brands?'), ('software', r'software|applications?|apps?|operating system|search engine'),
    ('website', r'websites?|web services?|online services?|social networks?'),
    ('magazine', r'magazines?'), ('newspaper', r'newspapers?'),
    ('television', r'television|\btv\b|channels?|broadcasters?'),
    ('game', r'games?'), ('film', r'films?|movies?'), ('series', r'series'),
    ('band', r'bands?|musical groups?|rock groups?'), ('character', r'characters?|superheroes|superhero'),
    ('automobile', r'automobiles?|cars?|vehicles?|automakers?|car manufacturers?'),
    ('retailer', r'retailers?|retail chains?|stores?'), ('airline', r'airlines?'),
    ('drink', r'drinks?|beverages?|beers?|brewer(?:y|ies)|soft drinks?'),
    ('product', r'products?|consumer electronics|devices?'),
    ('publication', r'publications?|comics?|books?|publishers?'),
]
NOISE = re.compile(r'\b(disambiguation|surnames?|given names?|villages?|rivers?|species|ships?|albums?|songs?|episodes?)\b', re.I)
SUFFIX = re.compile(r'(?:inc\.?|incorporated|company|co\.?|corporation|corp\.?|ltd\.?|limited|llc|plc|magazine|newspaper|the)', re.I)


def pages(response):
    """Return existing pages from a formatversion=2 response (also accept v1)."""
    query = response.get('query') or {}
    result = query.get('pages') or []
    if isinstance(result, dict): result = result.values()
    return [p for p in result if isinstance(p, dict) and 'missing' not in p and 'invalid' not in p and p.get('title')]


def description(page):
    return page.get('description') or (page.get('pageprops') or {}).get('wikibase-shortdesc') or ''


def resolve_titles(titles, responses):
    """Merge continued property results and resolve normalization and redirect chains."""
    edges = {}; found = {}
    for response in responses:
        query = response.get('query') or {}
        for key in ('normalized', 'converted', 'redirects'):
            for item in query.get(key) or []:
                if item.get('from') and item.get('to'): edges[item['from']] = item['to']
        for p in pages(response):
            old = found.setdefault(p['title'], {})
            props = dict(old.get('pageprops') or {}); props.update(p.get('pageprops') or {})
            old.update(p); old['pageprops'] = props
    result = {}
    for title in titles:
        target = title; seen = set()
        while target in edges and target not in seen:
            seen.add(target); target = edges[target]
        if target not in seen and target in found: result[title] = found[target]
    return result


def plausible_title(word, title):
    word = word.casefold(); title = title.strip().casefold()
    if title == word: return True
    if not title.startswith(word): return False
    rest = title[len(word):].strip()
    if rest.startswith('(') and rest.endswith(')') and rest[1:-1].strip(): return True
    return bool(rest and SUFFIX.fullmatch(rest.lstrip(', ').strip()))


def classify(word, title, desc, via):
    if via != 'bare' and not plausible_title(word, title): return None
    text = title + ' ' + desc
    if NOISE.search(text): return None
    for kind, pattern in TYPES:
        if re.search(r'\b(?:' + pattern + r')\b', text, re.I): return kind
    return None


def word_list():
    peak = collections.Counter()
    for path in glob.glob('data/raw/ssa/yob19[5-9]*.txt') + glob.glob('data/raw/ssa/yob20*.txt'):
        with open(path, encoding='utf-8') as f:
            for line in f:
                name, sex, count = line.strip().split(','); peak[name] = max(peak[name], int(count))
    with open('data/candidates.json', encoding='utf-8') as f:
        existing = {x.get('word', '').casefold() for x in json.load(f)}
    words = {w.lower() for w in LOWER if w.isalpha() and len(w) >= 3}
    words.update(n.lower() for n, count in peak.items() if count >= 300)
    result = sorted(w for w in words if w.casefold() not in existing)
    random.Random(20261111).shuffle(result)
    return result


def get(session, params):
    delay = 5
    while True:
        try:
            response = session.get(API, headers=UA, timeout=30, params={**COMMON, **params})
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict): raise ValueError('API response is not an object')
            if data.get('error'):
                error = data['error']; code = error.get('code', '')
                if code not in ('maxlag', 'ratelimited', 'readonly'):
                    raise RuntimeError('API error: ' + str(error))
                raise ValueError('API temporarily unavailable: ' + str(error))
            time.sleep(0.6)
            return data
        except (requests.RequestException, ValueError) as e:
            retry = getattr(getattr(e, 'response', None), 'headers', {}).get('Retry-After', '')
            try: wait = max(delay, float(retry))
            except (TypeError, ValueError): wait = delay
            print('request error', e, 'retry in', wait, 'seconds', flush=True)
            time.sleep(wait); delay = min(delay * 2, 300)


def query_all(session, params):
    continuation = {}; responses = []
    while True:
        data = get(session, {**params, **continuation}); responses.append(data)
        continuation = data.get('continue') or {}
        if not continuation: return responses


def save_state(state):
    tmp = STATE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, STATE)


def load_hits():
    """Discard an incomplete last line, and rebuild the deduplication index."""
    seen = set()
    if not os.path.exists(HITS): return seen
    with open(HITS, 'rb+') as f:
        while True:
            start = f.tell(); line = f.readline()
            if not line: break
            if not line.endswith(b'\n'):
                f.truncate(start); break
            hit = json.loads(line)
            seen.add((hit['word'], hit['article title'], hit['via']))
    return seen


def write_hit(out, seen, word, page, via):
    title = page.get('title', ''); desc = description(page)
    kind = classify(word, title, desc, via)
    key = (word, title, via)
    if not kind or key in seen: return
    hit = {'word': word, 'article title': title, 'short description': desc, 'type': kind, 'via': via}
    out.write(json.dumps(hit, ensure_ascii=False) + '\n'); out.flush(); os.fsync(out.fileno())
    seen.add(key)


def main():
    if len(sys.argv) > 2: raise SystemExit('usage: scan_disambig.py [word_limit]')
    try: limit = int(sys.argv[1]) if len(sys.argv) == 2 else None
    except ValueError: raise SystemExit('word_limit must be a nonnegative integer')
    if limit is not None and limit < 0: raise SystemExit('word_limit must be a nonnegative integer')
    words = word_list()
    if limit is not None: words = words[:limit]
    os.makedirs(DIR, exist_ok=True)
    if os.path.exists(STATE):
        with open(STATE, encoding='utf-8') as f: state = json.load(f)
    else: state = {'checked': {}, 'scanned': {}, 'bare': {}}
    checked = state.setdefault('checked', {}); scanned = state.setdefault('scanned', {}); bare_pages = state.setdefault('bare', {})
    seen = load_hits(); todo = [w for w in words if w not in checked]
    pending = sum(len(set(checked.get(w, [])) - set(scanned.get(w, []))) for w in words)
    print('words', len(words), 'unchecked', len(todo), 'known pending disambiguation pages', pending,
          'estimated requests:', math.ceil(len(todo) / 25), 'stage A +', pending,
          'known stage B (minimum; newly found pages and continuation add requests)', flush=True)
    session = requests.Session()
    with open(HITS, 'a', encoding='utf-8') as out:
        for i in range(0, len(todo), 25):
            batch = todo[i:i+25]
            titles = [t for w in batch for t in (w.capitalize(), w.capitalize() + ' (disambiguation)')]
            resolved = resolve_titles(titles, query_all(session, {**PROPS, 'redirects': 1, 'titles': '|'.join(titles)}))
            for w in batch:
                bare = w.capitalize(); page = resolved.get(bare)
                bare_pages[w] = {'title': page['title'], 'description': description(page)} if page else None
                if page and 'disambiguation' not in (page.get('pageprops') or {}): write_hit(out, seen, w, page, 'bare')
                checked[w] = list(dict.fromkeys(p['title'] for t in (bare, bare + ' (disambiguation)')
                    if (p := resolved.get(t)) and 'disambiguation' in (p.get('pageprops') or {})))
            save_state(state)
            print('stage A', min(i + len(batch), len(todo)), '/', len(todo), 'hits', len(seen), flush=True)
        for i, w in enumerate(words):
            for title in checked.get(w, []):
                if title in scanned.get(w, []): continue
                params = {**PROPS, 'generator': 'links', 'titles': title, 'gplnamespace': 0, 'gpllimit': 50}
                responses = query_all(session, params)
                # Merge page properties across continuation, without resolving linked redirects.
                linked = resolve_titles([p['title'] for r in responses for p in pages(r)], responses)
                for page in linked.values():
                    if 'disambiguation' not in (page.get('pageprops') or {}): write_hit(out, seen, w, page, 'disambig')
                scanned.setdefault(w, []).append(title); save_state(state)
                print('stage B', i + 1, '/', len(words), title, 'hits', len(seen), flush=True)
    print('done hits', len(seen), flush=True)


if __name__ == '__main__': main()
