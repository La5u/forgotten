"""Daily GDELT fetch (raw only, no labelling) for the week-long sense sample. Standard library only; runs on the home server.
Usage: sense_fetch.py WORDS_FILE OUT_DIR
Saves OUT_DIR/<UTC date of run start>/<quote(word)>.json; <quote(word)>.err = permanent error or given up (not retried that day).
Resumable; exits at once when OUT_DIR holds DAYS complete days (every word has a .json or .err)."""
import json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from urllib.parse import quote

UA = {'User-Agent': 'research-script/0.1'}
GDELT = 'https://api.gdeltproject.org/api/v2/context/context?format=json&mode=artlist&maxrecords=200&query='
DAYS, GAP = 7, 6.5

def safe(word):  # reversible: urllib.parse.unquote(name[:-5])
    return quote(word, safe='')

def complete(d, words):
    have = {f.rsplit('.', 1)[0] for f in os.listdir(d)}
    return all(safe(w) in have for w in words)

def put(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(data)
    os.replace(tmp, path)

last = [0.0]
def get(url):
    wait = GAP - (time.monotonic() - last[0])
    if wait > 0: time.sleep(wait)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            return r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.read().decode('utf-8', 'replace') or f'HTTP {e.code}'
    finally:
        last[0] = time.monotonic()

def fetch(word):
    """Returns (status, data): 'ok' + dict, 'perm' (GDELT rejects the query) or 'fail' (gave up after retries)."""
    q = word if re.fullmatch(r'\w+', word) else f'"{word}"'  # GDELT rejects short quoted phrases ("zara")
    for attempt in range(5):
        if attempt: time.sleep(10 * attempt)
        try:
            txt = get(GDELT + quote(q))
            if txt.lstrip().startswith('{'):  # GDELT sometimes emits invalid \escapes: double stray backslashes
                try: data = json.loads(txt, strict=False)
                except ValueError: data = json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', txt), strict=False)
                if isinstance(data, dict):
                    data.setdefault('articles', [])
                    return 'ok', data
            else:
                print(f'  gdelt {word}: {txt[:100].strip()}', flush=True)
                if re.search(r'too short|must be|invalid', txt, re.I): return 'perm', None
        except Exception as e:
            print(f'  gdelt {word} retry {attempt}: {e}', flush=True)
    return 'fail', None

def main():
    words_file, out = sys.argv[1], sys.argv[2]
    words = list(dict.fromkeys(w.strip().lower() for w in open(words_file, encoding='utf-8') if w.strip()))
    os.makedirs(out, exist_ok=True)
    days = sorted(d for d in os.listdir(out) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', d))
    done = [d for d in days if complete(os.path.join(out, d), words)]
    if len(done) >= DAYS:
        print(f'{datetime.now().isoformat(timespec="seconds")} {len(done)} complete days already, nothing to do', flush=True)
        return
    day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    d = os.path.join(out, day)
    os.makedirs(d, exist_ok=True)
    t0, stats, failed = time.time(), {'ok': 0, 'perm': 0, 'fail': 0, 'skip': 0}, []
    print(f'{datetime.now().isoformat(timespec="seconds")} start day {day}: {len(words)} words, {len(done)} complete days so far', flush=True)
    for i, w in enumerate(words, 1):
        base = os.path.join(d, safe(w))
        if os.path.exists(base + '.json') or os.path.exists(base + '.err'):
            stats['skip'] += 1
        else:
            st, data = fetch(w)
            stats[st] += 1
            if st == 'ok': put(base + '.json', json.dumps(data, ensure_ascii=False))
            elif st == 'perm': put(base + '.err', '')
            else: failed.append(w)
        if i % 50 == 0:
            print(f'{datetime.now().isoformat(timespec="seconds")} {i}/{len(words)} {stats} {time.time() - t0:.0f}s', flush=True)
    if failed:  # one more try; if still failing and few, close them so the day can complete
        print(f'retrying {len(failed)} failed words', flush=True)
        still = []
        for w in failed:
            st, data = fetch(w)
            base = os.path.join(d, safe(w))
            if st == 'ok': put(base + '.json', json.dumps(data, ensure_ascii=False)); stats['ok'] += 1; stats['fail'] -= 1
            elif st == 'perm': put(base + '.err', ''); stats['perm'] += 1; stats['fail'] -= 1
            else: still.append(w)
        if still and len(still) <= 0.05 * len(words):
            for w in still: put(os.path.join(d, safe(w)) + '.err', 'gave up')
        elif still:
            print(f'{len(still)} words still failing: day left incomplete', flush=True)
    print(f'{datetime.now().isoformat(timespec="seconds")} done day {day}: {stats}, complete={complete(d, words)}, '
          f'{time.time() - t0:.0f}s', flush=True)

if __name__ == '__main__':
    main()
