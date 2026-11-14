"""Classify brand types: python3 scripts/tag_fiction.py.
Batches of 60; up to four calls each. Validated caches resume automatically.
Progress: data/raw/fiction/status.json. No site data is changed by this script.
"""
import argparse, concurrent.futures, hashlib, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/fiction'
TYPES = {'character', 'work', 'band', 'product'}
PROMPT = """Classify the BRAND side of each entry, using its brand, owner, launch_year and source_url to disambiguate. Do not classify the word's original meaning or another brand sharing the name.
Return JSON only: {"results":[{"word":"exact input word","type":"product"}, ...]}.
Return every input word exactly once, no extras. Each type must be exactly one of:
character: a fictional character or creature (Batman, Elmo, Shrek, Garfield).
work: the title of a film, TV show, video game, book, comic or franchise (The Matrix, Titanic, Fortnite, Minions).
band: a music act or performer.
product: a company, product, service, publication, software, AI model, or anything commercial that is none of the above.
When a name is both a title and its lead character (Shrek, Aladdin, Rocky), use character.
Cortana is product when the entry's brand is the Microsoft assistant, even though it is named after the Halo character.

Entries (word, brand, owner, launch_year, source_url):
"""


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n')
    tmp.replace(path)


def validate(answer, batch):
    if not isinstance(answer, dict) or not isinstance(answer.get('results'), list):
        raise ValueError('expected results array')
    expected = {e['word'] for e in batch}
    out = {}
    for row in answer['results']:
        if not isinstance(row, dict) or set(row) != {'word', 'type'}:
            raise ValueError('expected word, type fields')
        w, kind = row['word'], row['type']
        if not isinstance(w, str) or w not in expected or w in out:
            raise ValueError(f'unknown/duplicate word: {w!r}')
        if not isinstance(kind, str) or kind not in TYPES:
            raise ValueError(f'{w}: invalid type')
        out[w] = kind
    if out.keys() != expected:
        raise ValueError('missing words')
    return out


def deepseek(prompt):
    return subprocess.run([os.path.expanduser('~/.local/bin/mistral'), '--json'], input=prompt,
                          text=True, capture_output=True, check=True, timeout=600).stdout


def read_batch(batch):
    prompt = PROMPT + json.dumps(batch, ensure_ascii=False)
    key = hashlib.sha256(prompt.encode()).hexdigest()[:24]
    path = RAW / 'deepseek' / f'{key}.json'
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            if cached['prompt'] == prompt:
                return validate(cached['answer'], batch), True
        except (ValueError, KeyError, TypeError):
            pass
    for attempt in range(1, 5):
        try:
            text = deepseek(prompt)
            path.parent.mkdir(parents=True, exist_ok=True)
            (path.parent / f'{key}.attempt{attempt}.txt').write_text(text)
            answer = json.loads(text)
            out = validate(answer, batch)
            write_json(path, {'prompt': prompt, 'answer': answer})
            return out, False
        except Exception as exc:
            error = f'deepseek {batch[0]["word"]} attempt {attempt}: {exc}'
            path.parent.mkdir(parents=True, exist_ok=True)
            (path.parent / f'{key}.error.txt').write_text(error + '\n')
            print(error, file=sys.stderr, flush=True)
            if attempt < 4:
                time.sleep(5 * attempt)
    raise RuntimeError(error)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workers', type=int, choices=range(1, 5), default=4, help='parallel calls (1–4)')
    args = ap.parse_args()
    fields = ('word', 'brand', 'owner', 'launch_year', 'source_url')
    entries = [{k: e.get(k) for k in fields} for e in json.loads((ROOT / 'data/judged.json').read_text())]
    entries.sort(key=lambda e: e['word'].lower())
    if len({e['word'].lower() for e in entries}) != len(entries):
        raise ValueError('duplicate lowercase headwords')
    batches = [entries[i:i+60] for i in range(0, len(entries), 60)]
    answers = {}
    total, done, cached, failures, last_error = len(batches), 0, 0, [], None
    start = time.monotonic()
    def status():
        elapsed = time.monotonic() - start
        rate = done / elapsed if elapsed else 0
        write_json(RAW / 'status.json', {'done': done, 'total': total, 'cached': cached,
                   'rate_batches_per_second': round(rate, 4), 'eta_seconds': round((total-done)/rate) if rate else None,
                   'last_error': last_error, 'failed': len(failures)})
    status()
    print(f'{len(entries)} entries, {total} batches; progress: {RAW / "status.json"}', flush=True)
    with concurrent.futures.ThreadPoolExecutor(args.workers) as pool:
        pending = {pool.submit(read_batch, batch) for batch in batches}
        while pending:
            finished, pending = concurrent.futures.wait(pending, timeout=15, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in finished:
                done += 1
                try:
                    result, hit = future.result()
                    answers.update(result)
                    cached += hit
                except Exception as exc:
                    last_error = str(exc)
                    failures.append(last_error)
                print(f'{done}/{total} batches; {cached} cached; {len(failures)} failed', flush=True)
            status()
    if failures:
        raise SystemExit(f'{len(failures)} batches failed; caches kept. Rerun to resume. Last error: {last_error}')
    out = dict(sorted((w.lower(), kind) for w, kind in answers.items()))
    write_json(ROOT / 'data/fiction.json', out)
    print(f'Wrote data/fiction.json: {len(out)} entries', flush=True)


if __name__ == '__main__':
    main()
