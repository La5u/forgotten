"""Attach the capitalization signal and write Terra review batches for not-yet-reviewed rows. Usage: make_judge_prompts.py PREFIX"""
import glob, json, re, sys
sys.path.insert(0, 'scripts')
from ngrams import cap
rows = json.load(open('data/classified.json'))
for r in rows:
    y = min(r['launch_year'], 2022)
    r['cap_pre'] = cap(r['word'], y-5, y) if r['kind'] != 'name' else None
    r['cap_2022'] = cap(r['word'], 2020, 2023) if r['kind'] != 'name' else None
json.dump(rows, open('data/classified.json', 'w'), indent=0)
done = set()
for p in glob.glob('data/raw/judge/*.jsonl'):
    for l in open(p):
        if l.startswith('{'):
            j = json.loads(l); done.add((j['word'].lower(), re.sub(r' \(\d{4}\)$', '', j['brand']).lower()))
rows = [r for r in rows if (r['word'].lower(), r['brand'].lower()) not in done]
P = '''You are the final editor of a dataset of real words and names claimed by companies. Decide each entry using the signals and your knowledge.
Groups:
taken: the brand or character comes to mind first for the general public, ahead of the original meaning.
contested: neither the brand or character nor the original meaning clearly comes first. Say who is winning.
failed: the brand or character claimed the word but the original meaning still clearly comes first, whether the brand is alive or dead.
watching: too new to judge.
Include fictional characters (such as Batman, Chucky, Elmo and Kermit) even without a company behind the name. Include a brand only if the public calls it by the bare word; choose the most popular eligible brand per word.
reject: coincidences, invented coinages that were never a word or name in any language (Canva, Bitbucket, Moodle), founder surnames, or entries that are neither a character nor a real company or product.
Traffic reflects what people look up, so companies are over-counted against everyday words: never mark a common everyday word as taken on traffic alone.
Signals: bv = median monthly Wikipedia views of the brand page, ov = of the original meaning page, share = bv/(bv+ov), caps = share of the capitalized form in Google Books before launch and in 2020-22.
Output only JSON Lines, one object per input, no prose, keys: word, brand, group, winner (brand|original|even), confidence (high|medium|low), reason (under 20 words, plain and specific, no jokes).

'''
fmt = lambda r: f"{r['word']} | {r['brand']} ({r['launch_year']}) | was: {r['original_meaning']} | bv={r['brand_views']} ov={r['original_views']} share={None if r['brand_share'] is None else round(r['brand_share'],2)} caps={r['cap_pre']}->{r['cap_2022']}"
for i in range(0, len(rows), 80):
    open(f'data/raw/judge/{sys.argv[1]}{i//80}.txt', 'w').write(P + '\n'.join(fmt(r) for r in rows[i:i+80]))
print(len(rows))
