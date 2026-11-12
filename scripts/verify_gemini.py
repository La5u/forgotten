"""Recheck published entries with Gemini; resume from data/raw/verify/gemini.jsonl."""
import csv
import json
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

URL = ('https://aiplatform.googleapis.com/v1/projects/braided-potion-514523-h8/'
       'locations/global/publishers/google/models/gemini-3.8-flash:generateContent')
OUT = Path('data/raw/verify')
GROUPS = {'taken', 'contested', 'failed', 'watching', 'reject'}
CONFIDENCE = {'high', 'medium', 'low'}


def prompt(entries):
    rules = '''Independently verify each entry in this dictionary. Use your own judgment, not the current group.
An entry must be a real pre-existing word, name or place whose meaning a brand, product, publication, show, game, band or fictional character now competes with. Invented coinages do not belong.
Include a brand only if the general public calls it by the bare word alone: Corvette, Mustang, Alexa, Word and Delta qualify; Ford Focus and Alaska Airlines do not. Use one brand per word: the most popular thing the public calls by that bare word.
Groups: taken = the brand or character is what most people think of first today; contested = neither clearly first; failed = the original meaning still clearly comes first; watching = launched too recently to tell; reject = entry does not belong. Discontinued does not mean failed: judge what people remember (e.g. Cortana, Blockbuster).
Traffic numbers are median monthly English Wikipedia views. They over-count brands against everyday words and are wrong when the article is wrong. Titles may be missing.
Each input is word | brand (owner, launch year) | original meaning | current group | discontinued (end year) | brand article and views | original article and views. Values are JSON encoded; null means unknown or none.
Return ONLY a JSON array, one object per entry, in the same order. Each object must contain:
- word: the input word; group: your own judgment, taken|contested|failed|watching|reject; group_confidence: high|medium|low.
- bare_word: boolean, whether people call this brand by the bare word; best_brand: the most popular brand for this word if a different one is clearly better known, otherwise null.
- brand_article_ok: true or false, or null if no article was given; brand_article_better: exact English Wikipedia title for the brand/product itself, not its parent company or a list, or null if the given article is fine or no suitable article exists.
- original_article_ok: true or false, or null if no article was given; original_article_better: exact English Wikipedia title for the ORIGINAL meaning, or null if fine or no article can exist (such as for verbs and adjectives). Use Franz Kafka rather than Kafka (surname), William Herschel rather than a village, the animal rather than a translation, when those are the original meanings.
- discontinued: boolean; end_year: integer or null; original_meaning_ok: boolean, whether the stated original meaning is accurate and really older than the brand.
- comment: fewer than 20 words, only when something is wrong, otherwise "".
Entries:
'''
    def enc(value):
        return json.dumps(value, ensure_ascii=False)
    lines = []
    for e in entries:
        lines.append(' | '.join((enc(e.get('word')), f"{enc(e.get('brand'))} ({enc(e.get('owner'))}, {enc(e.get('launch_year'))})",
            enc(e.get('original_meaning')), enc(e.get('group')),
            f"{enc(e.get('discontinued'))} ({enc(e.get('end_year'))})",
            f"{enc(e.get('brand_article'))} views {enc(e.get('brand_views'))}",
            f"{enc(e.get('original_article'))} views {enc(e.get('original_views'))}")))
    return rules + '\n'.join(lines)


def parse_response(payload, entries):
    parts = payload['candidates'][0]['content']['parts']
    rows = json.loads(''.join(p['text'] for p in parts if 'text' in p))
    if not isinstance(rows, list) or len(rows) != len(entries):
        raise ValueError('wrong number of results')
    for row, entry in zip(rows, entries):
        if not isinstance(row, dict) or row.get('word', '').lower() != entry['word'].lower():
            raise ValueError('missing or out-of-order word')
        if row.get('group') not in GROUPS or row.get('group_confidence') not in CONFIDENCE:
            raise ValueError('invalid group or confidence')
        for key in ('bare_word', 'discontinued', 'original_meaning_ok'):
            if type(row.get(key)) is not bool:
                raise ValueError(f'invalid {key}')
        for key in ('brand_article_ok', 'original_article_ok'):
            if key not in row or (row[key] is not None and type(row[key]) is not bool):
                raise ValueError(f'invalid {key}')
        for key in ('best_brand', 'brand_article_better', 'original_article_better'):
            if key not in row or (row[key] is not None and not isinstance(row[key], str)):
                raise ValueError(f'invalid {key}')
        if 'end_year' not in row or (row['end_year'] is not None and type(row['end_year']) is not int):
            raise ValueError('invalid end_year')
        if not isinstance(row.get('comment'), str):
            raise ValueError('invalid comment')
    return rows


def load_results(path):
    """Read complete JSONL records, tolerating an interrupted final write."""
    results = {}
    if not path.exists():
        return results
    with path.open(encoding='utf-8') as f:
        for line in f:
            try:
                row = json.loads(line)
                if isinstance(row, dict) and isinstance(row.get('word'), str):
                    results[row['word'].lower()] = row
            except json.JSONDecodeError:
                continue
    return results


def prepare_append(path):
    """Remove a partial final line before appending, or terminate a complete one."""
    if not path.exists() or not path.stat().st_size:
        return
    with path.open('rb+') as f:
        f.seek(0, 2)
        end = f.tell()
        f.seek(end - 1)
        if f.read(1) == b'\n':
            return
        pos = end
        while pos:
            pos -= 1
            f.seek(pos)
            if f.read(1) == b'\n':
                pos += 1
                break
        f.seek(pos)
        try:
            json.loads(f.read().decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            f.truncate(pos)
        else:
            f.seek(0, 2)
            f.write(b'\n')


class Token:
    def __init__(self):
        self.lock = threading.Lock()
        self.value = None
        self.expiry = 0

    def get(self, rejected=None):
        with self.lock:
            if self.value is None or time.monotonic() >= self.expiry or (rejected is not None and rejected == self.value):
                self.value = subprocess.check_output([str(Path('~/.config/vertex-token.sh').expanduser())], text=True).strip()
                if not self.value:
                    raise ValueError('empty Vertex token')
                self.expiry = time.monotonic() + 40 * 60
            return self.value


def verify(entries, token):
    body = {'contents': [{'role': 'user', 'parts': [{'text': prompt(entries)}]}],
            'generationConfig': {'thinkingConfig': {'thinkingLevel': 'low'},
                                 'responseMimeType': 'application/json', 'temperature': 0}}
    rejected = None
    for attempt in range(8):
        try:
            value = token.get(rejected)
            rejected = None
            response = requests.post(URL, headers={'Authorization': f'Bearer {value}'}, json=body, timeout=180)
            if response.status_code == 401:
                rejected = value
                raise RuntimeError('HTTP 401')
            if response.status_code in (429, 500, 503):
                raise RuntimeError(f'HTTP {response.status_code}')
            response.raise_for_status()
            return parse_response(response.json(), entries)
        except (requests.Timeout, requests.ConnectionError, RuntimeError) as exc:
            if attempt == 7:
                raise RuntimeError(f'after 8 attempts: {exc}') from exc
            time.sleep(min(2 ** attempt, 60))
    return []


def report(entries, results, path):
    disagreements = []
    counts = Counter()
    groups = Counter()
    verified = 0
    for entry in entries:
        row = results.get(entry['word'].lower())
        if row is None:
            continue
        verified += 1
        def add(field, current, gemini):
            disagreements.append((entry['word'], field, current, gemini, row.get('group_confidence'), row.get('comment', '')))
        if entry.get('group') != row.get('group'):
            groups[(entry.get('group'), row.get('group'))] += 1
            add('group', entry.get('group'), row.get('group'))
        for key in ('bare_word', 'brand_article_ok', 'original_article_ok', 'original_meaning_ok'):
            if row.get(key) is False:
                counts[key] += 1
                current = {'bare_word': True, 'brand_article_ok': entry.get('brand_article'),
                           'original_article_ok': entry.get('original_article'),
                           'original_meaning_ok': entry.get('original_meaning')}[key]
                better = row.get(key.replace('_ok', '_better')) if key.endswith('_article_ok') else False
                add(key, current, better if better is not None else False)
        for kind in ('brand', 'original'):
            if row.get(f'{kind}_article_ok') is None and row.get(f'{kind}_article_better'):
                add(f'{kind}_article_ok', entry.get(f'{kind}_article'), row[f'{kind}_article_better'])
        if row.get('best_brand'):
            add('best_brand', entry.get('brand'), row['best_brand'])
        for key in ('discontinued', 'end_year'):
            if entry.get(key) != row.get(key):
                if key == 'discontinued':
                    counts[key] += 1
                add(key, entry.get(key), row.get(key))
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(('word', 'field', 'current', 'gemini', 'confidence', 'comment'))
        writer.writerows(sorted(disagreements, key=lambda r: (r[1], r[0].lower())))
    print(f'Entries verified: {verified}')
    print('Group disagreements:')
    for (current, gemini), count in sorted(groups.items()):
        print(f'  {current} -> {gemini}: {count}')
    for key in ('bare_word', 'brand_article_ok', 'original_article_ok', 'discontinued', 'original_meaning_ok'):
        print(f'{key} {"mismatches" if key == "discontinued" else "false"}: {counts[key]}')


def main():
    if len(sys.argv) > 2:
        sys.exit('Usage: python -I scripts/verify_gemini.py [limit]')
    try:
        limit = int(sys.argv[1]) if len(sys.argv) == 2 else None
        if limit is not None and limit < 0:
            raise ValueError
    except ValueError:
        sys.exit('Limit must be a non-negative integer')
    entries = json.loads(Path('site/data.json').read_text(encoding='utf-8'))['entries']
    judged = {r['word'].lower(): r for r in json.loads(Path('data/judged.json').read_text(encoding='utf-8'))}
    entries = [{**e, **{k: judged.get(e['word'].lower(), {}).get(k) for k in ('brand_article', 'original_article')}} for e in entries]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'gemini.jsonl'
    prepare_append(path)
    results = load_results(path)
    pending = [e for e in entries if e['word'].lower() not in results]
    if limit is not None:
        pending = pending[:limit]
    batches = [pending[i:i + 20] for i in range(0, len(pending), 20)]
    token = Token()
    with path.open('a', encoding='utf-8') as f, ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(verify, batch, token): batch for batch in batches}
        for future in as_completed(futures):
            batch = futures[future]
            try:
                rows = future.result()
            except Exception as exc:
                print(f"Skipped batch starting {batch[0]['word']}: {exc}", file=sys.stderr)
                continue
            f.write(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
            f.flush()
            results.update((row['word'].lower(), row) for row in rows)
            print(f"Saved {len(rows)} entries starting {batch[0]['word']}", file=sys.stderr)
    report(entries, results, OUT / 'disagreements.tsv')


if __name__ == '__main__':
    main()
