"""Build compact dictionary book histories, 1900-2022 in three-year bins. No network."""
import collections, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
raw = json.loads((ROOT / 'data/raw/ngrams_1800.json').read_text())
entries = json.loads((ROOT / 'site/data.json').read_text())['entries']

def series(form):
    v = raw.get(form)
    if not v: return None, 0
    assert len(v) == 223, form
    # Per million words, three significant figures; bin centres are 1901, 1904, ..., 2021.
    b = [sum(v[i:i+3]) / 3 * 1e6 for i in range(100, 223, 3)]
    # A power-of-ten scale keeps most three-digit values integral without losing precision.
    exponent = math.floor(math.log10(max(b))) - 2 if max(b) else 0
    b = [float(f'{x / 10**exponent:.3g}') for x in b]
    return [int(x) if x.is_integer() else x for x in b], exponent

out, counts = {}, collections.Counter()
for e in entries:
    w = e['word']
    lo, le = series(w.lower()); cap, ce = series(w.capitalize())
    pair = [lo, cap]
    n = sum(v is not None for v in pair)
    # [lowercase bins, Capitalized bins, their base-10 exponents]; decode to per million.
    if n: out[w] = pair + [le, ce]; counts[n] += 1
path = ROOT / 'site/sparks.json'
path.write_text(json.dumps({'from': 1900, 'to': 2022, 'step': 3, 'entries': out}, separators=(',', ':')) + '\n')
print(f'{counts[1]} entries with one series, {counts[2]} with two; {len(out)}/{len(entries)} covered; {path.stat().st_size:,} bytes')
