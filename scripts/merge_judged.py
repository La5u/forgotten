"""Merge the review into data/judged.json, one row per word (the most-viewed brand wins)."""
import glob, json, collections, re
rows = {(r['word'].lower(), r['brand'].lower()): r for r in json.load(open('data/classified.json'))}
bad = 0
# Eponyms the judge rejected but whose word has its own everyday meaning that the brand now competes with (2026-11-09).
import sys; sys.path.insert(0, 'scripts'); from merge_preferences import PREFERRED
KEEP_EPONYM = {'ford', 'dodge', 'dell', 'miller'}
for p in sorted(glob.glob('data/raw/judge/*.jsonl')):
    for l in open(p):
        if not l.startswith('{'):
            continue
        j = json.loads(l); j['brand'] = re.sub(r' \(\d{4}\)$', '', j['brand']); k = (j['word'].lower(), j['brand'].lower())
        if j['group'] == 'reject' and k[0] in KEEP_EPONYM:
            j['group'] = 'data'  # grouped by traffic in build_site_data
        if k in rows:
            rows[k].update(group=j['group'], winner=j['winner'], confidence=j['confidence'], reason=j['reason'], judged=True)
        else:
            bad += 1
best = {}
for r in rows.values():
    if r.get('judged') and r['group'] != 'reject':
        w = r['word'].lower()
        if w not in best or (r['brand'].lower() == PREFERRED.get(w, '').lower(), r['brand_views'] or 0) > (best[w]['brand'].lower() == PREFERRED.get(w, '').lower(), best[w]['brand_views'] or 0):
            best[w] = r
out = sorted(best.values(), key=lambda r: r['word'].lower())
json.dump(out, open('data/judged.json', 'w'), indent=0)
print('unmatched', bad, 'unjudged', sum(not r.get('judged') for r in rows.values()), 'rejected', sum(r.get('group') == 'reject' for r in rows.values()))
print(collections.Counter(r['group'] for r in out), collections.Counter((r['group'], r['confidence']) for r in out if r['group'] == 'taken'))
print('kinds in taken', collections.Counter(r['kind'] for r in out if r['group'] == 'taken'))
for g in ('taken', 'contested', 'failed', 'watching'):
    print(g, [r['word'] for r in out if r['group'] == g][:150])
