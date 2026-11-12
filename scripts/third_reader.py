"""Independently resolve Gemini disagreements and article proposals with DeepSeek."""
import csv
import json
import runpy
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

URL = 'https://api.mistral.ai/v1/chat/completions'
VERIFY = Path('data/raw/verify')
RESULTS = VERIFY / 'deepseek.jsonl'
GROUPS = {'taken', 'contested', 'failed', 'watching', 'reject'}
GEMINI = runpy.run_path('scripts/verify_gemini.py')


def key(word, task):
    return word.lower(), task


def judgement_prompt(entries):
    # Reuse the dataset rules and exact entry format, withholding the published group.
    text = GEMINI['prompt']([{**e, 'group': None} for e in entries])
    rules, lines = text.split('Return ONLY a JSON array', 1)
    lines = lines.split('Entries:\n', 1)[1]
    return (rules + 'The current group is withheld and shown as null. '
            'Return ONLY a JSON object {"results": [...]} with one result per entry, in order. '
            'Each result has word, group (taken|contested|failed|watching|reject), '
            'bare_word (boolean), and best_brand (string or null: the most popular thing '
            'the public calls by this bare word, if different from the listed brand).\nEntries:\n' + lines)


def article_prompt(items):
    lines = []
    for item in items:
        row, entry = item['row'], item['entry']
        lines.append(json.dumps({'word': entry['word'], 'brand': entry['brand'],
            'original_meaning': entry['original_meaning'], 'side': row['side'],
            'option 1': {'title': row['current'] or 'none', 'views': row['current_views'] or 'none'},
            'option 2': {'title': row['suggested'], 'views': row['suggested_views'] or 'none'}}, ensure_ascii=False))
    return ("Choose the right English Wikipedia article for the specified side. For the brand side, "
            "choose the article about the brand or product itself that people mean by the bare word. "
            "For the original side, choose the article about the original everyday meaning of the word. "
            "For a given name, choose the name itself or its most famous historical bearer only if "
            "that is plainly what the word meant before the brand; never a mere synonym or translation, "
            "never a loosely related topic. Choose neither if neither option is right. "
            'Return ONLY a JSON object {"results": [...]} in input order, each with word, side, '
            'and choice (1, 2, or "neither").\nEntries:\n' + '\n'.join(lines))


def parse_response(payload, items, task):
    rows = json.loads(payload['choices'][0]['message']['content'])['results']
    if not isinstance(rows, list) or len(rows) != len(items):
        raise ValueError('wrong number of results')
    for row, item in zip(rows, items):
        entry = item if task == 'judgement' else item['entry']
        if not isinstance(row, dict) or not isinstance(row.get('word'), str) or row['word'].lower() != entry['word'].lower():
            raise ValueError('missing or out-of-order word')
        if task == 'judgement':
            if row.get('group') not in GROUPS or type(row.get('bare_word')) is not bool:
                raise ValueError('invalid group or bare_word')
            if 'best_brand' not in row or (row['best_brand'] is not None and not isinstance(row['best_brand'], str)):
                raise ValueError('invalid best_brand')
            row['task'] = task
        else:
            if row.get('side') != item['row']['side'] or not (type(row.get('choice')) is int and row['choice'] in (1, 2) or row.get('choice') == 'neither'):
                raise ValueError('invalid side or choice')
            row['task'] = 'article:' + row['side']
        row['word'] = entry['word']
    return rows


def verify(items, task, token):
    content = judgement_prompt(items) if task == 'judgement' else article_prompt(items)
    body = {'model': 'deepseek-v4-1-flash-1017', 'temperature': 0,
            'response_format': {'type': 'json_object'},
            'messages': [{'role': 'user', 'content': content}]}
    for attempt in range(8):
        try:
            response = requests.post(URL, headers={'Authorization': 'Bearer ' + token}, json=body, timeout=180)
            if response.status_code == 429 or 500 <= response.status_code < 600:
                raise requests.ConnectionError(f'HTTP {response.status_code}')
            response.raise_for_status()
            return parse_response(response.json(), items, task)
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == 7:
                raise RuntimeError(f'after 8 attempts: {exc}') from exc
            time.sleep(min(2 ** attempt, 60))


def load_results(path):
    results = {}
    if path.exists():
        with path.open(encoding='utf-8') as f:
            for line in f:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and isinstance(row.get('word'), str) and isinstance(row.get('task'), str):
                        results[key(row['word'], row['task'])] = row
                except json.JSONDecodeError:
                    continue
    return results


def write_tsv(path, columns, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def needs_judgement(entry, second):
    return (second.get('group') != entry['group'] or second.get('bare_word') is False or
            bool(second.get('best_brand')) or second.get('group') == 'reject')


def resolve(entries, gemini, results, articles, judged, protected):
    groups, overrides, maps, article_report = [], [], {}, []
    for entry in entries:
        word = entry['word']
        second = gemini.get(word.lower())
        third = results.get(key(word, 'judgement'))
        if not second:
            continue
        if not third:
            groups.append({'word': word, 'brand': entry['brand'], 'brand_views': entry.get('brand_views'),
                           'published': entry['group'], 'gemini': second.get('group'), 'deepseek': '',
                           'outcome': 'pending' if needs_judgement(entry, second) else 'keep'})
            continue
        old, new, other = entry['group'], second.get('group'), third['group']
        same_brand = (second.get('best_brand') and third.get('best_brand') and
                      second['best_brand'].strip().casefold() == third['best_brand'].strip().casefold() and
                      second['best_brand'].strip().casefold() != entry['brand'].strip().casefold())
        agreement = new == other and new != old
        if (agreement and (old in ('taken', 'reject') or new in ('taken', 'reject')) or
                second.get('bare_word') is False and third.get('bare_word') is False or same_brand):
            outcome = 'ask-owner'
        elif agreement and word.lower() not in protected:
            outcome = 'apply'
            overrides.append({'word': word, 'brand': entry['brand'], 'group': new,
                'winner': {'taken': 'brand', 'failed': 'original', 'contested': 'even', 'watching': entry.get('winner') or 'original'}[new],
                'confidence': 'medium', 'reason': 'Second and third readers agree.'})
        else:
            outcome = 'keep'
        groups.append({'word': word, 'brand': entry['brand'], 'brand_views': entry.get('brand_views'),
                       'published': old, 'gemini': new, 'deepseek': other, 'outcome': outcome,
                       'gemini_bare_word': second.get('bare_word'), 'deepseek_bare_word': third.get('bare_word'),
                       'gemini_best_brand': second.get('best_brand'), 'deepseek_best_brand': third.get('best_brand')})
    for row in articles:
        selected = row['decision'] in ('accept', 'review')
        result = results.get(key(row['word'], 'article:' + row['side'])) if selected else None
        outcome = 'skipped' if not selected else 'pending' if not result else 'apply' if result['choice'] == 2 else 'keep'
        article_report.append({**row, 'deepseek': result['choice'] if result else '', 'outcome': outcome})
        if outcome == 'apply':
            published = judged[row['word'].lower()]
            k = row['word'].lower()
            if k not in maps:
                maps[k] = {'word': published['word'], 'brand': published['brand'],
                           'is_real_prior_word': True, 'brand_named_after_word': True}
            maps[k][row['side'] + '_article'] = row['suggested']
    return groups, overrides, article_report, list(maps.values())


def entries_by_word(entries):
    return {e['word'].lower(): e for e in entries}


def main():
    entries = json.loads(Path('site/data.json').read_text(encoding='utf-8'))['entries']
    judged = entries_by_word(json.loads(Path('data/judged.json').read_text(encoding='utf-8')))
    entries = [{**e, **{k: judged.get(e['word'].lower(), {}).get(k) for k in ('brand_article', 'original_article')}} for e in entries]
    by_word = entries_by_word(entries)
    gemini = GEMINI['load_results'](VERIFY / 'gemini.jsonl')
    protected = set(GEMINI['load_results'](Path('data/raw/judge/zz_owner.jsonl')))
    fixes = json.loads(Path('data/review_fixes.json').read_text(encoding='utf-8'))['fix']
    protected.update(w.lower() for w, v in fixes.items() if 'group' in v)
    with (VERIFY / 'article_changes.tsv').open(encoding='utf-8', newline='') as f:
        articles = list(csv.DictReader(f, delimiter='\t', fieldnames=('word', 'side', 'current', 'current_views', 'suggested', 'suggested_views', 'decision')))
    if articles and articles[0]['word'].lower() == 'word' and articles[0]['side'].lower() == 'side':
        articles.pop(0)
    VERIFY.mkdir(parents=True, exist_ok=True)
    GEMINI['prepare_append'](RESULTS)
    results = load_results(RESULTS)
    pending = [e for e in entries if (g := gemini.get(e['word'].lower())) and
               needs_judgement(e, g) and
               key(e['word'], 'judgement') not in results]
    article_pending = []
    for row in articles:
        if row['decision'] not in ('accept', 'review'):
            continue
        if row['side'] not in ('brand', 'original') or row['word'].lower() not in by_word or row['word'].lower() not in judged or not row['suggested']:
            raise ValueError(f'invalid article row: {row}')
        if key(row['word'], 'article:' + row['side']) not in results:
            article_pending.append({'row': row, 'entry': by_word[row['word'].lower()]})
    batches = [(task, items[i:i + 20]) for task, items in [('judgement', pending), ('article', article_pending)] for i in range(0, len(items), 20)]
    failures = 0
    if batches:
        token = Path('~/.config/mistral.key').expanduser().read_text(encoding='utf-8').strip()
        if not token:
            raise ValueError('empty Mistral API key')
        with RESULTS.open('a', encoding='utf-8') as f, ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(verify, batch, task, token): (task, batch) for task, batch in batches}
            for future in as_completed(futures):
                task, batch = futures[future]
                try:
                    rows = future.result()
                except Exception as exc:
                    failures += 1
                    print(f'Skipped {task} batch: {exc}', file=sys.stderr)
                    continue
                f.write(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
                f.flush()
                results.update((key(row['word'], row['task']), row) for row in rows)
                print(f'Saved {len(rows)} {task} results', file=sys.stderr)
    groups, overrides, article_report, maps = resolve(entries, gemini, results, articles, judged, protected)
    write_tsv(VERIFY / 'consensus_groups.tsv', ('word', 'published', 'gemini', 'deepseek', 'outcome', 'brand', 'brand_views', 'gemini_bare_word', 'deepseek_bare_word', 'gemini_best_brand', 'deepseek_best_brand'), groups)
    write_jsonl(Path('data/raw/judge/zzzz_consensus.jsonl'), overrides)
    write_tsv(VERIFY / 'consensus_articles.tsv', ('word', 'side', 'current', 'current_views', 'suggested', 'suggested_views', 'decision', 'deepseek', 'outcome'), article_report)
    write_jsonl(Path('data/raw/wiki_map/zv_consensus.jsonl'), maps)
    for label, rows in [('Groups', groups), ('Articles', article_report)]:
        print(f'{label}: {dict(Counter(r["outcome"] for r in rows))}')
    print('Ask owner (descending monthly brand views):')
    for row in sorted((r for r in groups if r['outcome'] == 'ask-owner'), key=lambda r: -(r['brand_views'] or 0)):
        print(f"{row['word']}\t{row['brand']}\t{row['brand_views']}\t{row['published']} -> {row['gemini']} / {row['deepseek']}	bare: {row.get('gemini_bare_word')} / {row.get('deepseek_bare_word')}	best: {row.get('gemini_best_brand')} / {row.get('deepseek_best_brand')}")

    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
