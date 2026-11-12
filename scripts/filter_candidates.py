"""Keep words with real pre-launch use in Google Books, plus hand-kept cases the corpus misjudges."""
import json, sys
sys.path.insert(0, 'scripts')
from ngrams import prefreq
KEEP = {'fortnite', 'firefox', 'palantir', 'cortana', 'anduril'}
c = json.load(open('data/candidates.json'))
out = []
for r in c:
    r['pre_launch_per_million'] = prefreq(r)
    if (r['pre_launch_per_million'] or 0) >= 0.03 or r['word'].lower() in KEEP:
        out.append(r)
json.dump(out, open('data/filtered.json', 'w'), indent=0); print(len(out))
