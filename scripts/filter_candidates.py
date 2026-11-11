"""Keep words with real pre-launch use in Google Books, plus hand-kept cases the corpus misjudges."""
import json
KEEP = {'fortnite', 'firefox', 'palantir', 'cortana', 'anduril'}
c = json.load(open('data/candidates.json')); n = json.load(open('data/raw/ngrams.json'))
out = []
for r in c:
    f = r['word'].capitalize() if r['kind'] == 'name' else r['word'].lower()
    s = n.get(f); y = min(r['launch_year'], 2022)
    pre = s[max(0, y-1980-5):max(0, y-1980)] if s else None
    r['pre_launch_per_million'] = round(sum(pre)/len(pre)*1e6, 4) if pre else None
    if (r['pre_launch_per_million'] or 0) >= 0.03 or r['word'].lower() in KEEP:
        out.append(r)
json.dump(out, open('data/filtered.json', 'w'), indent=0); print(len(out))
