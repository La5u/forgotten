"""Read yearly Google Books series, including a partially fetched 1800 cache."""
import json, os

old = json.load(open('data/raw/ngrams.json'))
new = json.load(open('data/raw/ngrams_1800.json')) if os.path.exists('data/raw/ngrams_1800.json') else {}

def window(word, start, end):
    series, year = (new[word], 1800) if word in new else (old.get(word), 1980)
    return series[max(0, start-year):max(0, end-year)] if series else []

def prefreq(r):
    word = r['word'].capitalize() if r['kind'] == 'name' else r['word'].lower()
    year = min(r['launch_year'], 2022)
    p = window(word, year-5, year)
    return round(sum(p)/len(p)*1e6, 4) if p else None

def cap(word, start, end):
    # Compare the same years when only one casing has been fetched in the new cache.
    lo, up = word.lower(), word.capitalize()
    year = max(1800 if lo in new else 1980, 1800 if up in new else 1980, start)
    a, b = window(lo, year, end), window(up, year, end)
    if not a or not b: return None
    s, t = sum(a), sum(b)
    return round(t/(s+t), 2) if s+t else None
