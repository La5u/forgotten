"""Alexa and girls' names with similar US peaks. Run from the repository root."""
import collections, csv, glob, json, re, statistics

counts, totals = collections.defaultdict(dict), {}
for path in sorted(glob.glob('data/raw/ssa/yob*.txt')):
    year = int(re.search(r'yob(\d+)', path)[1])
    total = 0
    with open(path) as f:
        for name, sex, count in csv.reader(f):
            count = int(count)
            total += count
            if sex == 'F': counts[name][year] = count
    totals[year] = total
if not all(y in totals for y in range(1990, 2026)):
    raise ValueError('Need SSA files for every year from 1990 to 2025')
peak = lambda n: max(counts[n], key=lambda y: (counts[n][y], -y))
ay = peak('Alexa')
ap = counts['Alexa'][ay]
peers = sorted(n for n, c in counts.items() if not n.lower().startswith('alex')
               and abs(peak(n)-ay) <= 3 and ap/2 <= max(c.values()) <= ap*2)
if not peers: raise ValueError('No matching peers')
pm = lambda n, y: counts[n].get(y, 0)*1e6/totals[y]
indexed = lambda n, y: 100*pm(n, y)/pm(n, 2014)
if any(not counts[n].get(2014) for n in peers):
    raise ValueError('A peer has no published 2014 baseline')
from_year = 1970 if all(y in totals for y in range(1970, 2026)) else 1990
years = range(from_year, 2026)
out = {'from': from_year, 'to': 2025, 'base_year': 2014,
       'unit': "Girls given the name per million US births (both sexes, published SSA counts)",
       'peers': peers,
       'series': {n: [round(pm(n, y), 6) if y in counts[n] else None for y in years]
                  for n in ('Alexa',)},
       'peers_index': [round(statistics.median(indexed(n, y) for n in peers), 6) for y in years]}
# SSA suppresses counts below five; their contribution to these common peers is tiny.
with open('site/name_controls.json', 'w') as f:
    json.dump(out, f, separators=(',', ':'))
print(f'Alexa peak: {ay}, {ap} girls; {len(peers)} peers: '+', '.join(peers))
for year in (2014, 2015, 2020, 2025):
    print(year, 'Alexa index', round(indexed('Alexa', year), 2),
          'peers index', out['peers_index'][year-from_year])
