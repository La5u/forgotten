"""Two independent region/place readers. Run from the repo: python3 scripts/tag_regions.py.
Batches of 60; up to four calls per reader. Validated caches resume automatically.
Progress: data/raw/regions/status.json. No site data is changed by this script.
"""
import argparse, concurrent.futures, csv, hashlib, json, os, subprocess, sys, time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/regions'
ARGON = 'https://aiplatform.googleapis.com/v1/projects/braided-potion-514523-h8/locations/global/publishers/google/models/gemini-4-argon:generateContent'
MODEL = 'gemini-4-argon'
PROMPT = """Classify each entry independently using the specific brand, not its owner or another brand sharing the word.
Return JSON only: {"results":[{"word":"exact input word","region":null,"place":null}, ...]}.
Return every input word exactly once, no extras.

region: a short country/region name if this brand is known mainly in one country or region rather than across the English-speaking world; otherwise null. Judge public recognition, not merely where it is sold, registered or headquartered. A US household brand is NOT worldwide unless it is also widely known in at least one other major English-speaking country (UK, Canada, Australia, New Zealand, Ireland, etc.). US-only household brands are regional "US". Target is regional "US". Amazon, Zoom and Tide are not regional. LINE messaging is "Japan" (Japan/East Asia), Orange telecom is "France/Europe", Jio is "India", Quavers and Hobnobs are "UK", Biedronka is "Poland". Use short labels such as "UK", "US", "Japan", "India", "Europe"; do not infer region from the word's original meaning.

place: independently of region, for capitalised input words only, true if the original meaning is a geographical place, false if a personal name (given name, surname or person), null if neither or uncertain. America, Amazon (river/region), Boston and Java are places (true); Alexa and Zara are personal names (false). Follow the supplied original meaning when ambiguous. For lowercase input words always return null.

Entries (word, brand, owner, launch_year, original_meaning):
"""


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def validate(answer, batch):
    if not isinstance(answer, dict) or not isinstance(answer.get('results'), list):
        raise ValueError('expected results array')
    expected = {e['word']: e for e in batch}
    out = {}
    for row in answer['results']:
        if not isinstance(row, dict) or set(row) != {'word', 'region', 'place'}:
            raise ValueError('expected word, region, place fields')
        w, region, place = row['word'], row['region'], row['place']
        if not isinstance(w, str) or w not in expected or w in out:
            raise ValueError(f'unknown/duplicate word: {w!r}')
        if region is not None and (not isinstance(region, str) or not region.strip() or
                                   region != region.strip() or len(region) > 40 or any(c in region for c in '\t\r\n')):
            raise ValueError(f'{w}: invalid region')
        if place is not None and type(place) is not bool:
            raise ValueError(f'{w}: invalid place')
        if not w[0].isupper() and place is not None:
            raise ValueError(f'{w}: lowercase place must be null')
        out[w] = {'region': region, 'place': place}
    if out.keys() != expected.keys():
        raise ValueError('missing words')
    return out


def deepseek(prompt):
    return subprocess.run([os.path.expanduser('~/.local/bin/mistral'), '--json'], input=prompt,
                          text=True, capture_output=True, check=True, timeout=600).stdout


def gemini(prompt):
    sys.path.insert(0, os.path.expanduser('~/.config/waybar/ai-usage'))
    import tally
    token = subprocess.check_output([os.path.expanduser('~/.config/vertex-token.sh')], text=True, timeout=60).strip()
    body = {'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json',
                                 'thinkingConfig': {'thinkingLevel': 'low'}}}
    req = Request(ARGON, data=json.dumps(body).encode(),
                  headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    j = {}
    try:
        try:
            with urlopen(req, timeout=300) as response:
                j = json.load(response)
        except HTTPError as exc:
            j = json.loads(exc.read())
            raise RuntimeError(f'Vertex HTTP {exc.code}: {j.get("error", {}).get("message", "")[:200]}') from None
    finally:  # also tally rejected/failed calls; no usage metadata means zero
        u = j.get('usageMetadata', {})
        tally.record('gemini', MODEL, u.get('promptTokenCount', 0),
                     u.get('candidatesTokenCount', 0) + u.get('thoughtsTokenCount', 0))
    return ''.join(p.get('text', '') for p in j['candidates'][0]['content']['parts'] if not p.get('thought'))


def read_batch(reader, batch):
    prompt = PROMPT + json.dumps(batch, ensure_ascii=False)
    key = hashlib.sha256(prompt.encode()).hexdigest()[:24]
    path = RAW / reader / f'{key}.json'
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if cached['prompt'] == prompt:
                return validate(cached['answer'], batch), True
        except (ValueError, KeyError, TypeError):
            pass
    for attempt in range(1, 5):
        try:
            text = (deepseek if reader == 'deepseek' else gemini)(prompt)
            # Retain raw answers too, including invalid JSON, for inspection.
            path.parent.mkdir(parents=True, exist_ok=True)
            (path.parent / f'{key}.attempt{attempt}.txt').write_text(text)
            answer = json.loads(text)
            out = validate(answer, batch)
            write_json(path, {'prompt': prompt, 'answer': answer})
            return out, False
        except Exception as exc:
            error = f'{reader} {batch[0]["word"]} attempt {attempt}: {exc}'
            (RAW / reader).mkdir(parents=True, exist_ok=True)
            (RAW / reader / f'{key}.error.txt').write_text(error + '\n')
            print(error, file=sys.stderr, flush=True)
            if attempt < 4:
                time.sleep(5 * attempt)
    raise RuntimeError(error)


def merge(entries, answers):
    out, disagreements = {}, []
    for e in entries:
        w = e['word']
        a, b = answers['deepseek'][w], answers['gemini'][w]
        out[w.lower()] = {'region': a['region'] if a['region'] and b['region'] else None,
                          'place': a['place'] if a['place'] is b['place'] else None}
        if a != b:
            disagreements.append([w, a['region'], b['region'], a['place'], b['place']])
    return out, disagreements


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workers', type=int, choices=range(1, 5), default=4, help='parallel calls per reader (1–4)')
    args = ap.parse_args()
    fields = ('word', 'brand', 'owner', 'launch_year', 'original_meaning')
    entries = [{k: e.get(k) for k in fields} for e in json.loads((ROOT / 'site/data.json').read_text())['entries'] if e.get('english')]
    entries.sort(key=lambda e: e['word'].lower())
    if len({e['word'].lower() for e in entries}) != len(entries):
        raise ValueError('duplicate lowercase headwords')
    batches = [entries[i:i+60] for i in range(0, len(entries), 60)]
    answers = {'deepseek': {}, 'gemini': {}}
    total, done, cached, failures, last_error = 2 * len(batches), 0, 0, [], None
    start = time.monotonic()
    def status():
        elapsed = time.monotonic() - start
        rate = done / elapsed if elapsed else 0
        write_json(RAW / 'status.json', {'done': done, 'total': total, 'cached': cached,
                   'rate_batches_per_second': round(rate, 4), 'eta_seconds': round((total-done)/rate) if rate else None,
                   'last_error': last_error, 'failed': len(failures)})
    status()
    print(f'{len(entries)} English entries, {total} reader batches; progress: {RAW / "status.json"}', flush=True)
    with concurrent.futures.ThreadPoolExecutor(args.workers) as ds, concurrent.futures.ThreadPoolExecutor(args.workers) as gm:
        pending = {pool.submit(read_batch, reader, batch): reader
                   for reader, pool in [('deepseek', ds), ('gemini', gm)] for batch in batches}
        while pending:
            finished, _ = concurrent.futures.wait(pending, timeout=15, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in finished:
                reader = pending.pop(future)
                done += 1
                try:
                    result, hit = future.result()
                    answers[reader].update(result)
                    cached += hit
                except Exception as exc:
                    last_error = str(exc)
                    failures.append(last_error)
                print(f'{done}/{total} batches; {cached} cached; {len(failures)} failed', flush=True)
            status()
    if failures:
        raise SystemExit(f'{len(failures)} batches failed; caches kept. Rerun to resume. Last error: {last_error}')
    out, disagreements = merge(entries, answers)
    write_json(ROOT / 'data/regions.json', out)
    with (RAW / 'disagreements.tsv').open('w', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['word', 'deepseek_region', 'gemini_region', 'deepseek_place', 'gemini_place'])
        writer.writerows(disagreements)
    print(f'{len(out)} entries; {sum(v["region"] is not None for v in out.values())} regional; '
          f'{sum(v["place"] is True for v in out.values())} places; '
          f'{sum(v["place"] is False for v in out.values())} personal names; {len(disagreements)} disagreements')
    print('Wrote data/regions.json and data/raw/regions/disagreements.tsv')


if __name__ == '__main__':
    main()
