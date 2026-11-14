"""Matched US name comparisons for the two carousels. Run from the repository root."""
import collections, csv, glob, json, re, statistics

LAST = 2025
data = json.load(open('site/names.json'))
counts, totals = collections.defaultdict(dict), {}
for path in sorted(glob.glob('data/raw/ssa/yob*.txt')):
    year = int(re.search(r'yob(\d+)', path)[1])
    if year > LAST: continue
    total = 0
    with open(path) as f:
        for name, sex, count in csv.reader(f):
            count = int(count)
            total += count
            counts[name, sex][year] = count
    totals[year] = total
if not all(y in totals for y in range(1880, LAST+1)):
    raise ValueError('Need SSA files for every year from 1880 to 2025')
peaks = {k: max(c, key=lambda y: (c[y], -y)) for k, c in counts.items()}
sexes = {n['word']: max('FM', key=lambda s: sum(counts.get((n['word'], s), {}).values())) for n in data['names']}
pm = lambda k, y: counts[k].get(y, 0)*1e6/totals[y]
avg = lambda k, ys: statistics.mean(pm(k, y) for y in ys)
rows = []
for n in data['names']:
    name, launch = n['word'], n['launch_year']
    key = name, sexes[name]
    if key not in peaks or launch-3 < 1880 or launch > LAST: continue
    before = range(launch-3, launch)
    # Keep the page's existing minimum, applied to the selected sex.
    births = statistics.mean(counts[key].get(y, 0) for y in before)
    if births < data['min_base']: continue
    baseline, peak_year = avg(key, before), peaks[key]
    peak_count = counts[key][peak_year]
    peers = sorted(k for k in peaks if k[1] == key[1]
                   and k[0][:4].lower() != name[:4].lower()
                   and abs(peaks[k]-peak_year) <= 3
                   and peak_count/2 <= counts[k][peaks[k]] <= peak_count*2
                   and all(counts[k].get(y) for y in before))
    if len(peers) < 10: continue
    start = min(2000, launch-10)
    years = range(start, LAST+1)
    bases = {k: avg(k, before) for k in peers}
    median = lambda y: statistics.median(100*pm(k, y)/bases[k] for k in peers)
    # The median of individually indexed names may not itself average exactly 100.
    scale = statistics.mean(median(y) for y in before)/100
    comparison = {y: median(y)/scale if y in totals else None for y in years}
    target = {y: 100*pm(key, y)/baseline if y in counts[key] else None for y in years}
    end = min(launch+10, LAST)
    after5 = launch+5
    ratio = target.get(after5)/comparison[after5] if target.get(after5) is not None and comparison[after5] else None
    prior = range(launch-8, launch-5)
    previous = avg(key, prior) if launch-8 >= 1880 else 0
    trend = 100*(baseline/previous-1) if previous else None
    flags = []
    if births < 100 or min(counts[key].get(y, 0) for y in (launch, min(after5, LAST), end)) < 20:
        flags.append('Small counts can make this line jump.')
    if trend is not None and abs(trend) >= 15:
        flags.append('It was already '+('rising' if trend > 0 else 'falling')+' before launch.')
    if name == 'Elsa': flags.append('It rose after Frozen, peaked in 2014, then fell again.')
    brand = {
        'Alexa': 'the Echo',
        'Siri': 'the Apple assistant',
        'Apollo': 'Apollo Global Management',
        'Elsa': 'Frozen',
        'Tab': 'the Coca-Cola soda',
        'Barney': 'Barney & Friends',
        'Annabelle': 'the Annabelle film',
        'Destiny': 'the Bungie game',
        'Trinity': 'The Matrix',
        'Archer': 'the Adam Reed series',
        'Leia': 'Star Wars',
        'Cleo': 'the Cleo AI app',
        'Barbie': 'the Mattel doll',
        'Everest': 'the Everest app',
        'Pandora': 'the Pandora music service',
    }.get(name, n['brand'])
    row = {'name': name, 'brand': brand, 'type': n['type'], 'launch': launch, 'sex': key[1],
           'from': start, 'peers': [k[0] for k in peers],
           'name_index': [round(target[y], 3) if target[y] is not None else None for y in years],
           'comparison_index': [round(comparison[y], 3) if comparison[y] is not None else None for y in years],
           'end': end, 'flags': flags}
    rows.append((ratio, row, target, comparison, births, trend))

ranked = sorted((r for r in rows if r[0] is not None), key=lambda r: (r[0], r[1]['name']))
def pick(ordered, first):
    lead = next((r for r in ordered if r[1]['name'] == first), None)
    return ([lead] if lead else []) + [r for r in ordered if r is not lead][:8-bool(lead)]
def qualifies(r, lift=False):
    _, row, target, comparison, *_ = r
    for year in (row['launch']+5, row['end']):
        own, peer = target.get(year), comparison.get(year)
        if own is None or peer is None: return False
        if lift:
            if not (own > 100 and own > peer): return False
        elif not (own < 100 and own < peer): return False
    return True

worst = pick([r for r in ranked if qualifies(r)], 'Alexa')
lift = [r for r in reversed(ranked) if qualifies(r, lift=True)][:8]
selected = {r[1]['name']: r[1] for r in worst+lift}
out = {'to': LAST, 'worst': [r[1]['name'] for r in worst], 'lift': [r[1]['name'] for r in lift], 'names': list(selected.values())}
with open('site/name_controls.json', 'w') as f:
    json.dump(out, f, separators=(',', ':'))
print(f'{len(rows)} usable comparisons; {len(ranked)} with a five-year result; {len(selected)} stored.')
for title, group in [('Worst offenders', worst), ('Names that got a lift', lift)]:
    print('\n'+title+' (indexes: three pre-launch years = 100)')
    for ratio, r, target, comparison, births, trend in group:
        y, end = r['launch']+5, r['end']
        print(f"{r['name']}: launch {r['launch']}, +5 {target[y]:.1f} vs {comparison[y]:.1f}, ratio {ratio:.3f}; "
              f"{births:.1f} baseline births; prior five-year change {trend:.1f}%; "
              f"{r['launch']} to {end}: {100*(target[end]/target[r['launch']]-1):+.1f}% vs {100*(comparison[end]/comparison[r['launch']]-1):+.1f}%. "+' '.join(r['flags']))
        if r['name'] == 'Elsa':
            peak = max((y for y in target if y >= r['launch'] and target[y] is not None), key=target.get)
            print(f"Elsa after-launch peak {peak}: index {target[peak]:.1f}; 2025 {target[LAST]:.1f}, {100*(target[LAST]/target[peak]-1):+.1f}% from that peak.")
