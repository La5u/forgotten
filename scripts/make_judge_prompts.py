"""Attach the capitalization signal and write Terra review batches for not-yet-reviewed rows. Usage: make_judge_prompts.py PREFIX"""
import glob, json, re, sys
rows = json.load(open('data/classified.json')); n = json.load(open('data/raw/ngrams.json'))
def cap(w, a, b):
    lo, up = n.get(w.lower()), n.get(w.capitalize())
    if not lo or not up: return None
    s = sum(lo[a:b]); t = sum(up[a:b])
    return round(t/(s+t), 2) if s+t else None
for r in rows:
    y = min(r['launch_year'], 2022) - 1980
    r['cap_pre'] = cap(r['word'], max(0, y-5), max(1, y)) if r['kind'] != 'name' else None
    r['cap_2022'] = cap(r['word'], 40, 43) if r['kind'] != 'name' else None
json.dump(rows, open('data/classified.json', 'w'), indent=0)
done = set()
for p in glob.glob('data/raw/judge/*.jsonl'):
    for l in open(p):
        if l.startswith('{'):
            j = json.loads(l); done.add((j['word'].lower(), re.sub(r' \(\d{4}\)$', '', j['brand']).lower()))
rows = [r for r in rows if (r['word'].lower(), r['brand'].lower()) not in done]
P = '''You are the final editor of a dataset of real words and names claimed by companies. Decide each entry using the signals and your knowledge.
Groups:
taken: an ordinary English speaker today thinks of the brand first and the old meaning has become rare or niche (Alexa, Tinder as a word for kindling, Fortnite).
contested: both meanings stay in heavy everyday use (apple, amazon, target, meta). Say who is winning.
failed: a genuine company or product claimed the word but never became what people think of first, including dead, faded or obscure ones (Echo-scale fame does not belong here, that is contested with original winning).
watching: launched 2021 or later, too early to judge.
reject: fictional characters with no company behind the name, coincidences, invented coinages that were never a word or name in any language (Canva, Bitbucket, Moodle), founder surnames, or anything where you cannot name a real company or product.
Traffic reflects what people look up, so companies are over-counted against everyday words: never mark a common everyday word as taken on traffic alone.
Signals: bv = median monthly Wikipedia views of the brand page, ov = of the original meaning page, share = bv/(bv+ov), caps = share of the capitalized form in Google Books before launch and in 2020-22.
Output only JSON Lines, one object per input, no prose, keys: word, brand, group, winner (brand|original|even), confidence (high|medium|low), reason (under 20 words, plain and specific, no jokes).

'''
fmt = lambda r: f"{r['word']} | {r['brand']} ({r['launch_year']}) | was: {r['original_meaning']} | bv={r['brand_views']} ov={r['original_views']} share={None if r['brand_share'] is None else round(r['brand_share'],2)} caps={r['cap_pre']}->{r['cap_2022']}"
for i in range(0, len(rows), 80):
    open(f'data/raw/judge/{sys.argv[1]}{i//80}.txt', 'w').write(P + '\n'.join(fmt(r) for r in rows[i:i+80]))
print(len(rows))
