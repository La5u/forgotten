"""Merge Terra JSONL candidates into data/candidates.json, keeping single-token entries."""
import glob, json, re
rows = {}
for p in sorted(glob.glob('data/raw/candidates_*.jsonl')):
    for l in open(p):
        l = l.strip()
        if not l.startswith('{'):
            continue
        r = json.loads(l)
        if not re.fullmatch(r"[A-Za-z]+", r['word']):
            continue
        rows.setdefault((r['word'].lower(), r['brand'].lower()), r)
out = sorted(rows.values(), key=lambda r: r['word'].lower())
json.dump(out, open('data/candidates.json', 'w'), indent=0)
print(len(out), 'pairs', len({r['word'].lower() for r in out}), 'words')
