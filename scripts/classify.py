"""Join mapped pairs with pageviews and assign taken / contested / failed / unknown. Writes data/classified.json."""
# 2026-11-09: no longer requires the brand to be named after the word (Python, Mac, Hummer still take it).
import glob, json, statistics as st
OWNER_KEEP = {'slack', 'fortnite'}  # from the original README
FAME = 4000          # median monthly brand views over the last 24 months
TAKEN = 0.70         # brand share of brand + original views
titles = json.load(open('data/raw/wiki_titles.json')); views = json.load(open('data/raw/pageviews.json'))
cand = {(r['word'].lower(), r['brand'].lower()): r for r in json.load(open('data/candidates.json'))}
recent = [f'{y}{m:02d}' for y in (2024, 2025, 2026) for m in range(1, 13) if '202411' <= f'{y}{m:02d}' <= '202610']
def med(t):
    t = titles.get(t)
    v = views.get(t) if t else None
    return st.median(v.get(m, 0) for m in recent) if v else None
out = {}
for p in glob.glob('data/raw/wiki_map/*.jsonl'):
    for l in open(p):
        if not l.startswith('{'):
            continue
        m = json.loads(l); k = (m['word'].lower(), m['brand'].lower())
        c = cand.get(k)
        if not c or (m['word'].lower() not in OWNER_KEEP and not m.get('is_real_prior_word')):
            continue
        b, o = med(m.get('brand_article')), med(m.get('original_article'))
        share = b/(b+o) if b is not None and o is not None and b+o else None
        if b is None:
            g = 'unknown'
        elif b < FAME:
            g = 'failed'
        elif share is None:
            g = 'unknown'
        elif share >= TAKEN:
            g = 'taken'
        else:
            g = 'contested'
        out[k] = {**c, 'brand_article': titles.get(m.get('brand_article')), 'original_article': titles.get(m.get('original_article')),
                  'brand_views': b, 'original_views': o, 'brand_share': share, 'group': g}
rows = sorted(out.values(), key=lambda r: r['word'].lower())
json.dump(rows, open('data/classified.json', 'w'), indent=0)
import collections
print(collections.Counter(r['group'] for r in rows), 'of', len(rows))
for g in ('taken', 'contested', 'failed', 'unknown'):
    print(g, [(r['word'], round(r['brand_share'], 2) if r['brand_share'] is not None else None) for r in rows if r['group'] == g][:45])
