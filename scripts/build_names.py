"""Build site/names.json: yearly births for every site entry that is also a given name, per source, as counts and per million births.
Sources: US SSA (data/raw/ssa, 1880 on), England and Wales ONS (names_unified.csv, 1996 on), Ontario (data/raw/ontario, 1913 on).
NSW is left out: it publishes only the top 100 names, so its totals are not all births. Totals are sums of the same file, so
names under each publishing threshold (US 5, ONS 3, Ontario 5) are missing from both name and total.
Kept: entries with at least MIN_PEAK US births (both sexes) in their best year. Types come from data/raw/name_types.jsonl
(cheap model, cached; rerun the prompt by hand for new words). Stats use the US share; an absent year counts as 0."""
import collections, csv, glob, json, re, statistics
MIN_PEAK, MIN_BASE, LAST = 100, 20, 2025  # MIN_BASE: average US births a year before launch needed to measure a change
E = json.load(open('site/data.json'))['entries']
W = {}
for e in sorted(E, key=lambda e: -(e.get('brand_views') or 0)):
    W.setdefault(e['word'][:1].upper() + e['word'][1:].lower(), e)
cnt = {s: collections.defaultdict(collections.Counter) for s in ('us', 'uk', 'ontario')}
tot = {s: collections.Counter() for s in cnt}
for p in glob.glob('data/raw/ssa/yob*.txt'):
    y = int(re.search(r'yob(\d+)', p)[1])
    for n, _, c in csv.reader(open(p)):
        tot['us'][y] += int(c)
        if n in W: cnt['us'][n][y] += int(c)
for r in csv.reader(open('data/raw/names_unified.csv')):
    if r[0] == 'uk':
        y, c = int(r[3]), int(r[4]); tot['uk'][y] += c
        if r[1] in W: cnt['uk'][r[1]][y] += c
for f in ('female', 'male'):
    for r in csv.reader(open(f'data/raw/ontario/{f}.csv', encoding='utf-8-sig')):
        if r[0].isdigit() and r[2].isdigit():
            y, n, c = int(r[0]), r[1].capitalize(), int(r[2]); tot['ontario'][y] += c
            if n in W: cnt['ontario'][n][y] += c
TYPES = {}
for l in open('data/raw/name_types.jsonl'):
    try: d = json.loads(l); TYPES[d['word'].capitalize()] = d['type']
    except (ValueError, KeyError, AttributeError): pass
US0 = min(tot['us'])
pm = lambda s, n, y: 1e6 * cnt[s][n].get(y, 0) / tot[s][y] if y in tot[s] else None  # per million births, absent name = 0
def avg(n, a, b):
    v = [pm('us', n, y) for y in range(a, b)]
    return None if None in v else sum(v) / len(v)
def stats(n, L):
    base = avg(n, L-3, L)
    if base is None or sum(cnt['us'][n].get(y, 0) for y in range(L-3, L)) / 3 < MIN_BASE: return None
    prev = avg(n, L-8, L-5)
    ch = lambda v: None if v is None else round(100 * (v / base - 1))
    return {'baseline': round(base, 2), 'baseline_births': round(sum(cnt['us'][n].get(y, 0) for y in range(L-3, L)) / 3),
            'after': {k: ch(pm('us', n, L+k)) if L+k <= LAST else None for k in (1, 3, 5, 10)},
            'before5': None if not prev else round(100 * (base / prev - 1))}  # same 3-year window five years earlier -> baseline
out, miss = [], []
for n, e in W.items():
    if max(cnt['us'][n].values(), default=0) < MIN_PEAK: continue
    if n not in TYPES: miss.append(n)
    ser = {}
    for s in cnt:
        ys = sorted(cnt[s][n])
        if not ys: continue
        a, b = ys[0], max(tot[s])
        ser[s] = {'from': a, 'count': [cnt[s][n].get(y) for y in range(a, b+1)], 'per_million': [round(pm(s, n, y), 3) if y in cnt[s][n] else None for y in range(a, b+1)]}
    st = stats(n, e['launch_year'])
    out.append({'word': n, 'kind': e['kind'], 'type': TYPES.get(n, 'other'), **{k: e.get(k) for k in ('brand', 'owner', 'launch_year', 'group', 'brand_views', 'discontinued', 'end_year')},
                'us_peak': max(cnt['us'][n].values()), 'us_peak_year': max(cnt['us'][n], key=cnt['us'][n].get), 'stats': st, 'series': ser})
med = lambda v: round(statistics.median(v)) if v else None
def table(rows):
    t = {}
    for ty in ('company', 'character'):
        r = [x['stats'] for x in rows if x['type'] == ty and x['stats']]
        t[ty] = {f'after{k}': {'median': med([s['after'][k] for s in r if s['after'][k] is not None]), 'n': sum(s['after'][k] is not None for s in r)} for k in (5, 10)}
        a5 = [s['after'][5] for s in r if s['after'][5] is not None]
        t[ty]['halved5'], t[ty]['up50_5'] = sum(v <= -50 for v in a5), sum(v >= 50 for v in a5)
        t[ty]['before5'] = {'median': med([s['before5'] for s in r if s['before5'] is not None and s['after'][5] is not None]), 'n': sum(s['before5'] is not None and s['after'][5] is not None for s in r)}
    return t
summary = {'all': table(out), 'took_word': table([x for x in out if x['group'] in ('taken', 'contested')]), 'names_only': table([x for x in out if x['kind'] == 'name'])}
# Cards on the page: names the brief singled out, then the most-viewed measurable brands that took the word, up to 14 per type,
# skipping names that never reached 300 US births a year (too noisy). Alexa has its own chart.
LEAD = 'Siri Dora Garfield Elsa Barbie Mario Tesla Mercedes'.split()
rest = [x for x in sorted(out, key=lambda x: -(x['brand_views'] or 0)) if x['word'] not in LEAD + ['Alexa'] and x['stats']
        and x['group'] in ('taken', 'contested') and x['us_peak'] >= 300]
pick = {x['word'] for ty in ('company', 'character') for x in [x for x in rest if x['type'] == ty][:14]}
strip = [w for w in LEAD if any(x['word'] == w for x in out)] + [x['word'] for x in rest if x['word'] in pick]
json.dump({'strip': strip, 'min_peak': MIN_PEAK, 'min_base': MIN_BASE, 'last_year': LAST,
           'sources': {'us': 'United States (SSA)', 'uk': 'England and Wales (ONS)', 'ontario': 'Ontario'},
           'summary': summary, 'names': out}, open('site/names.json', 'w'), separators=(',', ':'))
print(len(out), 'names,', collections.Counter(x['type'] for x in out), 'measurable:', sum(1 for x in out if x['stats']))
if miss: print('no type cached for:', ', '.join(miss))
for k, t in summary.items():
    print(f'\n{k}: median change in US share of births vs the 3 years before launch')
    print(f"{'type':10} {'+5 yrs':>8} {'n':>4} {'+10 yrs':>8} {'n':>4} {'5 yrs before':>13} {'n':>4} {'fell 50%+':>9} {'rose 50%+':>9}")
    for ty, v in t.items(): print(f"{ty:10} {v['after5']['median']!s:>8} {v['after5']['n']:>4} {v['after10']['median']!s:>8} {v['after10']['n']:>4} {v['before5']['median']!s:>13} {v['before5']['n']:>4} {v['halved5']:>9} {v['up50_5']:>9}")
