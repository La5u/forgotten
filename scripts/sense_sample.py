"""Share of recent news sentences (GDELT, pooled over the fetched days) using a word in the brand vs original sense, labelled by Gemini Argon.
Usage: sense_sample.py [--raw DIR] [--labels DIR] [--out TSV] [word ...]   (all site words when none given; resumable)
Raw layouts: DIR/<YYYY-MM-DD>/<quote(word)>.json (sense_fetch.py, default ~/server/forgotten-sense/out) or DIR/<word>.json (pilot cache)."""
import argparse, collections, concurrent.futures, hashlib, json, math, os, re, subprocess, sys, time
from urllib.parse import quote, unquote
import requests
sys.path.insert(0, os.path.expanduser('~/.config/waybar/ai-usage'))
import tally

D = 'data/raw/sense'
ARGON = 'https://aiplatform.googleapis.com/v1/projects/braided-potion-514523-h8/locations/global/publishers/google/models/gemini-4-argon:generateContent'
MAX_N, PER_DOMAIN, THIN = 100, 3, 30
TOK = {'in': 0, 'out': 0}
HITS = collections.Counter()  # how often each cleaning filter fired

def days(raw):
    sub = sorted(d for d in os.listdir(raw) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', d))
    return [os.path.join(raw, d) for d in sub] or [raw]

def load(word, dirs):
    """Articles of all days for word (later days first, so a re-seen URL keeps its newest sentence), and the number of days with a file."""
    arts, n = [], 0
    for d in reversed(dirs):
        p = os.path.join(d, quote(word, safe='') + '.json')
        if os.path.exists(p) and os.path.getsize(p):
            n += 1; arts += json.load(open(p, encoding='utf-8')).get('articles', [])
    return arts, n

MON = r'(?i:jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\.?'
DATE = rf'(?:{MON} \d{{1,2}}(?:st|nd|rd|th)?,? \d{{4}}|\d{{1,2}} {MON},? \d{{4}}|{MON} \d{{4}}|{MON} \d{{1,2}}(?:st|nd|rd|th)|\d{{1,2}}/\d{{1,2}}/\d{{2,4}},?)'
TIME = r'(?:,? (?:at )?\d{1,2}:\d{2}(?: ?(?i:[ap]\.?m\.?))?(?: [A-Z]{2,5})?)'
PREFIX = re.compile(rf"^\W*(?:(?:Updated|Published|Posted):? |(?:[A-Z][\w&'-]*,? ){{0,3}})?{DATE}(?: {DATE})?{TIME}?(?: \|)?"
                    r"(?: Filed under:.{0,200}? — .{0,40}? @ \d{1,2}:\d{2} ?[ap]m)?\s+(?=[A-Z\"'“‘(\d])")
CREDIT = re.compile(r"^\W*(?:Photo|Image|Picture)?\s*(?:Credit|Courtesy)s?:?\s+[^.]{0,80}?(?:Getty Images|Shutterstock|Reuters|AP Photo|AP|AFP|EPA|Alamy|Imagn|Instagram|X)\b\s*", re.I)

def strip(text):
    text = re.sub(r'\s+', ' ', text).strip()
    m = PREFIX.match(text)
    if m: HITS['prefix'] += 1; text = text[m.end():]
    m = CREDIT.match(text)
    if m: HITS['credit prefix'] += 1; text = text[m.end():]
    return text

def junk(text):
    segs = [s.strip() for s in text.split('|')]
    if len(segs) >= 3 and sum(len(s.split()) <= 3 for s in segs) >= 2: HITS['link list'] += 1; return True
    words = re.findall(r"[^\W\d_][\w'’-]*", text)
    if len(words) < 2: HITS['fragment'] += 1; return True
    if len(words) <= 12 and (re.match(r'\W*(?:(?:photo|image|picture|video)s?\b|credits?\b|courtesy\b)', text, re.I)
                             or re.search(r'/\s*(?:Getty|AP|Reuters|AFP|EPA|Shutterstock|Alamy|Imagn)\b', text)):
        HITS['bare credit'] += 1; return True
    return False

def norm(s):
    return re.sub(r'[\W_]+', ' ', s.lower()).strip()

def clean(word, arts):
    *head, last = word.split(' ')
    tail = r"(?:'s|’s|s'|s’)?" if last.endswith('s') else r"(?:s|es|'s|’s|s'|s’)?"  # plural/possessive forms
    pat = re.compile(r'(?<![\w])' + re.escape(word) + tail + r'(?![\w])', re.I)
    seen, urls, rows = set(), set(), []
    for a in arts:
        if a.get('language') != 'ENGLISH' or a.get('url') in urls: continue
        text = next((s for s in map(strip, filter(None, (a.get('sentence'), a.get('context')))) if pat.search(s)), None)
        if not text or junk(text): continue
        k = norm(text)[:150]  # near-duplicates: same text after prefix removal, or truncated differently
        if k in seen: HITS['duplicate'] += 1; continue
        seen.add(k); urls.add(a.get('url'))
        rows.append({'text': text, 'domain': a.get('domain', ''), 'url': a.get('url', ''), 'title': a.get('title', ''), 'seen': a.get('seendate', '')})
    rows.sort(key=lambda r: hashlib.sha1(norm(r['text']).encode()).hexdigest())  # deterministic shuffle
    per, out = collections.Counter(), []
    for r in rows:
        if per[r['domain']] < PER_DOMAIN:
            per[r['domain']] += 1; out.append(r)
    return len(rows), out[:MAX_N]

PROMPT = """You are labelling how the word "{word}" is used in news sentences (plural or possessive forms count too).
Brand sense: {brand} (owned by {owner}).
Original everyday meaning: {orig}

For each numbered sentence, label the use of "{word}" as:
- "brand": refers to {brand} (this brand, product, company or character), including when written with a fuller name or as part of it.
- "original": the original meaning listed above, including its ordinary figurative or extended uses. A clearly different established sense of the word (one not covered by the listed meaning) is not "original": label it "other" with a note naming that sense.
- "other": anything else (a different brand or company, a person, place, title, team, a different sense, etc.) or unclear. For "other" add a 2-4 word note of what it is.
If the original meaning is itself a personal name (a given name or surname), then any real or fictional person called that name who is not {brand} counts as "original"; apply this consistently.
If the word only appears inside website boilerplate (navigation, menus, share buttons, follow-us or social links), label it "other" with note "boilerplate".
If the word appears more than once, label the dominant use. Judge each sentence on its own.

Reply with JSON only: {{"results":[{{"n":1,"label":"brand|original|other","note":""}}, ...]}} with exactly {k} results, n = 1..{k}.

Sentences:
{sents}"""

def token():
    return subprocess.run([os.path.expanduser('~/.config/vertex-token.sh')], capture_output=True, text=True, check=True).stdout.strip()

def argon(prompt):
    body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json', 'thinkingConfig': {'thinkingLevel': 'low'}}}
    for attempt in range(4):
        try:
            r = requests.post(ARGON, json=body, headers={'Authorization': f'Bearer {token()}'}, timeout=300)
            j = r.json()
            u = j.get('usageMetadata', {})
            i, o = u.get('promptTokenCount', 0), u.get('candidatesTokenCount', 0) + u.get('thoughtsTokenCount', 0)
            if i or o:
                tally.record('gemini', 'gemini-4-argon', i, o); TOK['in'] += i; TOK['out'] += o
            if r.status_code == 200:
                return ''.join(p.get('text', '') for p in j['candidates'][0]['content']['parts'] if not p.get('thought'))
            print(f'  argon {r.status_code}: {r.text[:200]}', file=sys.stderr)
        except Exception as e:
            print(f'  argon error: {e}', file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    return ''

def label(word, e, sents, ldir):
    path = f'{ldir}/{quote(word, safe="")}.json'
    key = hashlib.sha1('\n'.join(s['text'] for s in sents).encode()).hexdigest()  # relabel when the pooled sample changes
    if os.path.exists(path):
        c = json.load(open(path))
        if c.get('key') == key: return c['labels']
    k = len(sents)
    prompt = PROMPT.format(word=word, brand=e['brand'], owner=e['owner'], orig=e['original_meaning'], k=k,
                           sents='\n'.join(f'{i}. {s["text"]}' for i, s in enumerate(sents, 1)))
    res = None
    for _ in range(2):
        try:
            got = json.loads(argon(prompt))['results']
            by = {int(x['n']): x for x in got}
            if sorted(by) == list(range(1, k + 1)) and all(x['label'] in ('brand', 'original', 'other') for x in got):
                res = by; break
        except Exception: pass
        print(f'  bad answer for {word}, retrying', file=sys.stderr)
    if res is None: return None
    out = [dict(s, label=res[i]['label'], note=(res[i].get('note') or '').strip()) for i, s in enumerate(sents, 1)]
    os.makedirs(ldir, exist_ok=True)
    json.dump({'key': key, 'labels': out}, open(path, 'w'), ensure_ascii=False, indent=1)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('words', nargs='*')
    ap.add_argument('--raw', default=os.path.expanduser('~/server/forgotten-sense/out'))
    ap.add_argument('--labels', default=f'{D}/labels_week')
    ap.add_argument('--out', default=f'{D}/week.tsv')
    a = ap.parse_args()
    entries = {e['word'].lower(): e for e in json.load(open('site/data.json'))['entries']}
    words = list(dict.fromkeys(w.lower() for w in a.words)) or list(entries)
    missing = [w for w in words if w not in entries]
    words = [w for w in words if w in entries]
    if missing: print('not on site, skipped:', ' '.join(missing))
    dirs = days(a.raw)
    fetched, kept_all = 0, 0

    def one(w):
        nonlocal fetched, kept_all
        arts, nd = load(w, dirs)
        n_eng, s = clean(w, arts)
        fetched += len(arts); kept_all += n_eng
        print(f'{w}: {nd} days, {len(arts)} articles, {n_eng} unique English sentences, {len(s)} sampled', file=sys.stderr)
        return nd, (label(w, entries[w], s, a.labels) if s else [])
    with concurrent.futures.ThreadPoolExecutor(4) as ex:
        res = dict(zip(words, ex.map(one, words)))
    rows = []
    for w in words:
        nd, L = res[w]
        if L is None: print(f'{w}: labelling failed'); continue
        c, n = collections.Counter(x['label'] for x in L), len(L)
        notes = collections.Counter(x['note'].lower() for x in L if x['label'] == 'other' and x['note'])
        pct = lambda k: round(100 * c[k] / n) if n else 0
        bo = c['brand'] + c['original']
        p = c['brand'] / bo if bo else 0
        rows.append([w, entries[w]['brand'], entries[w]['group'], n, pct('brand'), pct('original'), pct('other'),
                     round(100 * p) if bo else '', round(196 * math.sqrt(p * (1 - p) / bo)) if bo else '', nd,
                     '; '.join(f'{k} ({v})' for k, v in notes.most_common(2)), 'THIN' if n < THIN else ''])
    rows.sort(key=lambda r: -r[4])
    head = ['word', 'brand', 'group', 'n', 'brand%', 'orig%', 'other%', 'brand/(b+o)%', '±95%', 'days', 'top other notes', 'flag']
    with open(a.out, 'w') as f:
        f.write('\t'.join(head) + '\n' + ''.join('\t'.join(map(str, r)) + '\n' for r in rows))
    wd = [max(len(str(x)) for x in col) for col in zip(head, *rows)]
    for r in [head] + rows:
        print('  '.join(str(x).ljust(wd[i]) for i, x in enumerate(r)).rstrip())
    print(f'\narticles fetched {fetched}, unique English sentences with word {kept_all}, labelled {sum(r[3] for r in rows)}; '
          f'filters fired {dict(HITS)}; argon tokens this run in {TOK["in"]} out {TOK["out"]}')

if __name__ == '__main__':
    main()
