"""Matched US name checks. Run with python3 -I from the repository root."""
import collections
import csv
import glob
import json
from pathlib import Path
import re
import statistics

LAST = 2025
MIN_BASELINE_BIRTHS = 75
MIN_COMPARISONS = 10
MIN_BRAND_VIEWS = 1_000
FALL_THRESHOLD = -0.20
LIFT_THRESHOLD = 0.25
WINDOW_YEARS = 6
MIN_AVAILABLE_YEARS = 3
END_YEARS = 10
LONG_FALL_FACTOR = 0.6
LONG_LIFT_FACTOR = 1.67
END_MEAN_YEARS = 3
SPIKE_PEAK_FACTOR = 1.5
PEAK_YEAR_TOLERANCE = 3
PEAK_SIZE_FACTOR = 2

data = json.loads(Path('site/names.json').read_text())
counts, totals = collections.defaultdict(dict), {}
for path in sorted(glob.glob('data/raw/ssa/yob*.txt')):
    year = int(re.search(r'yob(\d+)', path)[1])
    if year > LAST:
        continue
    total = 0
    with open(path) as f:
        for name, sex, count in csv.reader(f):
            count = int(count)
            total += count
            counts[name, sex][year] = count
    totals[year] = total
if not all(y in totals for y in range(1880, LAST + 1)):
    raise ValueError('Need SSA files for every year from 1880 to 2025')
peaks = {k: max(c, key=lambda y: (c[y], -y)) for k, c in counts.items()}
sexes = {n['word']: max('FM', key=lambda s: sum(counts.get((n['word'], s), {}).values()))
         for n in data['names']}


def pm(key, year):
    return counts[key].get(year, 0) * 1e6 / totals[year]


def average(key, years):
    return statistics.mean(pm(key, y) for y in years) if years else None


def window(launch, first, last):
    return [y for y in range(launch + first, launch + last + 1) if y in totals]


def window_mean(ratios, years):
    if not years or any(ratios.get(y) is None for y in years):
        return None
    return statistics.mean(ratios[y] for y in years)


def metrics(ratios, before_years, after_years, earlier_years):
    before = window_mean(ratios, before_years)
    after = window_mean(ratios, after_years)
    earlier = window_mean(ratios, earlier_years)
    change = after / before - 1 if before and after is not None else None
    prior = before / earlier - 1 if earlier and before is not None and len(earlier_years) >= MIN_AVAILABLE_YEARS else None
    relative = (1 + change) / (1 + prior) - 1 if change is not None and prior is not None and prior > -1 else None
    return {'before': before, 'after': after, 'earlier': earlier, 'change': change,
            'prior': prior, 'relative_to_prior': relative}


def percentile(value, placebos):
    if value is None or not placebos:
        return None
    direction = -1 if value < 0 else 1
    # As before, compare in the observed direction. Missing placebo ratios stay
    # in the denominator, conservatively counting as not beaten. No gate.
    beaten = sum(p is not None and direction * value > direction * p for p in placebos)
    return 100 * beaten / len(placebos)


def classify(births, index_births, peer_count, views, m, before_years, after_years, earlier_years, early_peak, end_ratio):
    if births is None:
        return None, 'no before data'
    if births < MIN_BASELINE_BIRTHS:
        return None, 'births below 75/year'
    if index_births is None or index_births < MIN_BASELINE_BIRTHS:
        return None, 'births below 75/year in three years before launch'
    if peer_count < MIN_COMPARISONS:
        return None, 'fewer than 10 comparison names'
    if (views or 0) < MIN_BRAND_VIEWS:
        return None, 'brand views below 1000/month'
    if len(before_years) < WINDOW_YEARS:
        return None, 'no complete before window'
    if len(after_years) < MIN_AVAILABLE_YEARS:
        return None, 'fewer than 3 after-years'
    if len(earlier_years) < MIN_AVAILABLE_YEARS or m['prior'] is None:
        return None, 'no earlier data'
    change, prior = m['change'], m['prior']
    if change is None:
        return None, 'no comparison data'
    if 1 + change <= 1 + FALL_THRESHOLD and 1 + change <= 0.8 * (1 + prior):
        return 'worst', None
    if 1 + change >= 1 + LIFT_THRESHOLD and 1 + change >= 1.25 * (1 + prior):
        return 'lift', None
    if end_ratio is not None and end_ratio / m['before'] <= LONG_FALL_FACTOR and prior >= FALL_THRESHOLD:
        return 'worst', None
    if end_ratio is not None and end_ratio / m['before'] >= LONG_LIFT_FACTOR and prior <= LIFT_THRESHOLD:
        return 'lift', None
    # A spike qualifies only after failing both worst and lift checks.
    if early_peak is not None and early_peak >= SPIKE_PEAK_FACTOR * m['before']:
        return 'spike', None
    if 1 + FALL_THRESHOLD < 1 + change < 1 + LIFT_THRESHOLD:
        return None, 'change below fall/lift thresholds; no qualifying spike'
    return None, 'change already under way; no qualifying spike'


def rounded(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [rounded(v) for v in value]
    return value


BRANDS = {'Alexa': 'the Echo', 'Siri': 'the Apple assistant', 'Apollo': 'Apollo Global Management',
          'Elsa': 'Frozen', 'Tab': 'the Coca-Cola soda', 'Barney': 'Barney & Friends',
          'Annabelle': 'the Annabelle film', 'Destiny': 'the Bungie game', 'Trinity': 'The Matrix',
          'Archer': 'the Adam Reed series', 'Leia': 'Star Wars', 'Cleo': 'the Cleo AI app',
          'Barbie': 'the Mattel doll', 'Everest': 'the Everest app', 'Pandora': 'the Pandora music service'}
rows, checks = [], []
for n in data['names']:
    name, launch = n['word'], n['launch_year']
    key = name, sexes[name]
    before_years = window(launch, -WINDOW_YEARS, -1)
    after_years = window(launch, 1, WINDOW_YEARS)
    earlier_years = window(launch, -2 * WINDOW_YEARS, -WINDOW_YEARS - 1)
    births = statistics.mean(counts[key].get(y, 0) for y in before_years) if before_years else None
    # Preserve the existing matching and three-year index construction. The
    # selection statistics below average RATIOS over six-year windows instead.
    index_years = window(launch, -3, -1)
    index_births = statistics.mean(counts[key].get(y, 0) for y in index_years) if index_years else None
    baseline = average(key, index_years)
    peak_year = peaks.get(key)
    peak_count = counts[key].get(peak_year, 0)
    peers = sorted(k for k in peaks if peak_count and k[1] == key[1]
                   and k[0][:4].lower() != name[:4].lower()
                   and abs(peaks[k] - peak_year) <= PEAK_YEAR_TOLERANCE
                   and peak_count / PEAK_SIZE_FACTOR <= counts[k][peaks[k]] <= peak_count * PEAK_SIZE_FACTOR
                   and index_years and all(counts[k].get(y) for y in index_years))
    start, end = max(1880, min(2000, launch - 10)), LAST
    end_to = min(launch + END_YEARS, LAST)
    draw_years = range(start, end + 1)
    end_window = [y for y in range(end_to - END_MEAN_YEARS + 1, end_to + 1) if y in totals]
    needed = sorted(set(draw_years) | set(before_years + after_years + earlier_years + index_years + end_window))
    bases = {k: average(k, index_years) for k in peers}
    indexed = {y: sorted((100 * pm(k, y) / bases[k], k) for k in peers) for y in needed}
    medians = {y: statistics.median(v for v, k in indexed[y]) if peers else None for y in needed}
    scale = statistics.mean(medians[y] for y in index_years) / 100 if peers else None
    comparison = {y: medians[y] / scale if scale else None for y in needed}
    target = {y: 100 * pm(key, y) / baseline if baseline else None for y in needed}
    ratios = {y: target[y] / comparison[y] if comparison[y] and target[y] is not None else None for y in needed}
    m = metrics(ratios, before_years, after_years, earlier_years)
    peak_values = [ratios[y] for y in window(launch, 0, 2) if ratios.get(y) is not None]
    early_peak = max(peak_values) if len(peak_values) == 3 else None
    end_ratio = window_mean(ratios, end_window)
    placebo_ratios = {k: {} for k in peers}
    # Each comparison name is treated as launched in L, against the median of
    # the others. A constant median rebase cancels in after/before.
    for y in before_years + after_years:
        ordered = indexed[y]
        size = len(ordered) - 1
        if size < 1:
            continue
        for i, (own, k) in enumerate(ordered):
            middle = [(size - 1) // 2, size // 2]
            other = statistics.mean(ordered[j + (j >= i)][0] for j in middle)
            placebo_ratios[k][y] = own / other if other else None
    placebo_changes = [metrics(placebo_ratios[k], before_years, after_years, [])['change'] for k in peers]
    pct = percentile(m['change'], placebo_changes)
    views = n.get('brand_views')
    category, failed = classify(births, index_births, len(peers), views, m, before_years, after_years, earlier_years, early_peak, end_ratio)
    check = {'name': name, 'brand': BRANDS.get(name, n['brand']), 'launch': launch,
             'baseline_births': births, 'index_births': index_births, 'brand_views': views, **m, 'placebo_percentile': pct,
             'first_failed': failed or 'pass: ' + category, 'early_peak': early_peak,
             'end_ratio': end_ratio, 'peer_count': len(peers), 'before_years': len(before_years),
             'after_years': len(after_years), 'earlier_years': len(earlier_years)}
    checks.append(check)
    if category:
        six_year = ((category == 'worst' and 1 + m['change'] <= 1 + FALL_THRESHOLD
                     and 1 + m['change'] <= 0.8 * (1 + m['prior']))
                    or (category == 'lift' and 1 + m['change'] >= 1 + LIFT_THRESHOLD
                        and 1 + m['change'] >= 1.25 * (1 + m['prior'])))
        rows.append({**{k: v for k, v in check.items() if k != 'first_failed'},
                     'type': n['type'], 'sex': key[1], 'from': start, 'end': end, 'end_to': end_to,
                     'after_to': after_years[-1], 'category': category,
                     'test': 'spike' if category == 'spike' else 'six_year' if six_year else 'long',
                     'peers': [k[0] for k in peers],
                     # Store only the chart's years; suppressed target counts stay gaps.
                     'name_index': [round(target[y], 2) if target[y] is not None and y in counts[key] else None for y in draw_years],
                     'comparison_index': [round(comparison[y], 2) if comparison[y] is not None else None for y in draw_years]})

worst = sorted((r for r in rows if r['category'] == 'worst'), key=lambda r: (r['name'] != 'Alexa', r['relative_to_prior'], r['name']))
lift = sorted((r for r in rows if r['category'] == 'lift'), key=lambda r: (-r['relative_to_prior'], r['name']))
spike = sorted((r for r in rows if r['category'] == 'spike'), key=lambda r: (r['name'] != 'Elsa', -abs(r['relative_to_prior']), r['name']))
out = {'to': LAST, 'worst': [r['name'] for r in worst], 'lift': [r['name'] for r in lift],
       'spike': [r['name'] for r in spike], 'names': worst + lift + spike,
       'thresholds': {'baseline_births': MIN_BASELINE_BIRTHS, 'comparisons': MIN_COMPARISONS,
                      'brand_views': MIN_BRAND_VIEWS, 'fall': FALL_THRESHOLD, 'lift': LIFT_THRESHOLD,
                      'window_years': WINDOW_YEARS, 'birth_windows': [3, WINDOW_YEARS],
                      'min_after_years': MIN_AVAILABLE_YEARS,
                      'min_earlier_years': MIN_AVAILABLE_YEARS, 'spike_peak_factor': SPIKE_PEAK_FACTOR,
                      'long_fall_factor': LONG_FALL_FACTOR,
                      'long_fall_min_prior': FALL_THRESHOLD, 'long_lift_factor': LONG_LIFT_FACTOR,
                      'long_lift_max_prior': LIFT_THRESHOLD, 'end_years': END_YEARS,
                      'end_mean_years': END_MEAN_YEARS}}
Path('site/name_controls.json').write_text(json.dumps(rounded(out), separators=(',', ':'), allow_nan=False))
columns = ['name', 'brand', 'launch', 'baseline_births', 'index_births', 'brand_views', 'peer_count',
           'before_years', 'after_years', 'earlier_years', 'before', 'after', 'change', 'earlier',
           'prior', 'relative_to_prior', 'placebo_percentile', 'early_peak', 'end_ratio', 'first_failed']
Path('/tmp/fg-lab').mkdir(parents=True, exist_ok=True)
with open('/tmp/fg-lab/name_checks.tsv', 'w') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow(columns)
    for row in checks:
        values = [f'{row[k]:.6f}' if isinstance(row[k], float) else row[k] if row[k] is not None else 'NA' for k in columns]
        writer.writerow(values)
for category in ('worst', 'lift', 'spike'):
    print(f'{category} ({len(out[category])}): ' + ', '.join(out[category]))
print(f'Checks: {len(checks)} names in /tmp/fg-lab/name_checks.tsv')
