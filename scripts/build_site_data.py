"""Build site/data.json from data/judged.json and the unified name counts."""
import collections, csv, json
OVERRIDES = {'meta': 'contested', 'docker': 'taken', 'twitter': 'taken', 'git': 'contested', 'yahoo': 'contested'}  # owner's call + 2026-11-09 review
# Field fixes from review (pageviews: median monthly 2024-11..2026-10).
FIX = {
    'rockstar': dict(brand='Rockstar Games', owner='Take-Two Interactive', launch_year=1998, brand_views=97501.5, original_views=608.0,
                     source_url='https://en.wikipedia.org/wiki/Rockstar_Games', winner='original',
                     reason='Gamers mean the studio; everyone else still means a famous musician or a star performer.'),
    'git': dict(original_views=3744.0, winner='brand', reason='Programmers mean the software; in Britain the insult is still everyday speech.'),
    'yahoo': dict(original_meaning='A brutish person, after the Yahoos in Gulliver\'s Travels; also "yahoo!", a cry of delight.', winner='brand',
                  reason='The company leads online, but the cheer is still in everyday use.'),
    'docker': dict(winner=None, reason='The software gets 82% of the Wikipedia traffic; "docker" for a dock worker is now rare.'),
}
# Not an attempt on the word: the product is not called by the bare word (Alaska Airlines is "Alaska Airlines", not "Alaska").
NOT_BARE = set('answers navigator core aspire predator circle mantis titanium fly orchid panda julie frankly spruce cash monday oscar lucent alaska american hawaiian united southwest frontier spirit allegiant qatar etihad fiji garuda silver eos peach pegasus breeze zip crew boost calumet ceres gorilla honest hypnos ichiban liberty life mint naked oregon orion persephone president sothys tula venus vision meet fire executive'.split()) | {'photoshop', 'sylvanian'}  # last two: coinages (Sonnet check)
LAUNCH = {'alexa': 2015}  # Echo reached general US sale on 14 July 2015
ABANDONED = {'bard', 'cortana', 'stadia', 'hangouts'}
rows = json.load(open('data/judged.json'))
# English = the word was in English use before the brand: a dictionary word (lowercase entry
# in /usr/share/dict/words), a given name with births in the US/UK/NSW/Ontario files, or a
# hand-checked English proper noun/compound. Hand-checked foreign words override.
import sys; sys.path.insert(0, 'scripts'); from english import LOWER, stems  # Hunspell en_US/GB/AU/CA common words
DICT = None
ENGLISH = set('beeper bing detour discord dishonored fisheye galactica houseparty oculus odeon overwatch pythia shazam solvate tatler terraria transformers amazon bandcamp basecamp burlington firefox inbox houseparty meetup mega macintosh oregon patagonia fiji qatar kathmandu tahoe telluride robinhood rockstar starburst photoshop pegasus kafka vivaldi sibelius godot bacchus aztec hypnos eos pythia galactica grok fortnite uber dodgeball digg wizz terraform midjourney chipotle greggs silverado wotsits nerf uno butterfinger tums'.split())
FOREIGN = set('nokia subaru cortina torino voss carrefour dacia diablo evian glenlivet hulu macallan macan pret prius reebok sephora wawa creta prado akamai altezza doxa gladius zo aya ghibli'.split())  # hand-checked: not English before the brand
ngrams = json.load(open('data/raw/ngrams.json'))
def prefreq(r):
    s = ngrams.get(r['word'].capitalize() if r['kind'] == 'name' else r['word'].lower())
    y = min(r['launch_year'], 2022) - 1980
    p = s[max(0, y-5):max(1, y)] if s else None
    return round(sum(p)/len(p)*1e6, 4) if p else None
names = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
for r in csv.DictReader(open('data/raw/names_unified.csv')):
    names[r['name']][r['source']][int(r['year'])] += int(r['count'])
def drops(series, launch):
    pre = [series.get(y, 0) for y in range(launch-3, launch)]
    base = sum(pre)/3
    if base < 20:
        return None
    return {'baseline': round(base), 'after': {k: round(100*(series.get(launch+k, 0)/base-1)) for k in (1, 3, 5, 10) if launch+k <= 2025}}
out = []
import re
def by_data(r):
    # Same thresholds as classify.py: brand under 4,000 monthly views = failed; 70%+ brand share = taken.
    b, o = r.get('brand_views'), r.get('original_views')
    if b is None or not o or r.get('no_brand_article'): return None, None
    sh = b/(b+o)
    if b < 4000: return 'failed', 'original'
    if sh >= .7: return 'taken', 'brand'
    return 'contested', 'brand' if sh > .55 else 'original' if sh < .45 else 'even'
# Original-meaning traffic for words whose first mapping found no article: accept Terra's pick only if the
# article is about the word itself (its title contains the word), never a synonym concept (ask -> Question).
FILL = {w: v for w, v in json.load(open('data/raw/orig_fill/views.json')).items()
        if v[1] and any(x in re.findall(r'[a-z]+', v[0].lower()) for x in stems(w))}
REVIEW = json.load(open('data/review_fixes.json'))  # Sonnet check 2026-11-09, reviewed by Opus
for k, v in REVIEW['fix'].items(): FIX[k] = {**FIX.get(k, {}), **v}
NOT_BARE |= set(REVIEW['reject']) | set(REVIEW.get('reject_strict_bare_word', []))  # strict: only products the public calls by the bare word
import os, statistics
# Traffic: median monthly views over the last 12 months (2025-11..2026-10), with page moves merged back in.
VIEWS = json.load(open('data/raw/pageviews_merged.json' if os.path.exists('data/raw/pageviews_merged.json') else 'data/raw/pageviews.json'))
VIEWS.update(json.load(open('data/raw/extra_views.json')) if os.path.exists('data/raw/extra_views.json') else {})
LAST12 = [f'{y}{m:02d}' for y in (2025, 2026) for m in range(1, 13) if '202511' <= f'{y}{m:02d}' <= '202610']
def med12(t):
    v = VIEWS.get(t)
    return statistics.median(v.get(k, 0) for k in LAST12) if v else None
for r in rows:
    if r['word'].lower() in NOT_BARE: continue
    r.update(FIX.get(r['word'].lower(), {}))
    for side in ('brand', 'original'):
        if r.get(side + '_article') and med12(r[side + '_article']) is not None: r[side + '_views'] = med12(r[side + '_article'])
    for t in r.get('extra_brand_articles', []): r['brand_views'] = (r.get('brand_views') or 0) + (med12(t) or 0)  # brand split over several articles
    if r['word'].lower() in FIX and 'group' in FIX[r['word'].lower()]: OVERRIDES[r['word'].lower()] = FIX[r['word'].lower()]['group']
    if not r.get('original_views') and r['word'].lower() in FILL: r['original_views'] = FILL[r['word'].lower()][1]; r['original_article'] = FILL[r['word'].lower()][0]
    if not r.get('brand_views') and r.get('original_views'): r['brand_views'] = 0; r['no_brand_article'] = True  # brand never got a Wikipedia article
    if 'original_views' in FIX.get(r['word'].lower(), {}) and FIX[r['word'].lower()]['original_views'] is None: r['brand_share'] = None
    if r.get('brand_views') is not None and r.get('original_views'): r['brand_share'] = r['brand_views']/(r['brand_views']+r['original_views'])
    if r['group'] in ('watching', 'data'):  # Watching only when traffic is missing on one side; recency alone is not doubt
        g2, w2 = by_data(r)
        if g2: r['group'], r['winner'] = g2, w2
        elif r['group'] == 'data': r['group'] = 'contested'
    if r.get('no_plot'): r['brand_share'] = None  # traffic is shared with a parent article, or the comparison article is a bad match
    if (r.get('brand_views') or 0) + (r.get('original_views') or 0) < 300: continue  # owner, 2026-11-09: too little evidence either way
    g = 'failed' if r['word'].lower() in ABANDONED else r['group']
    g = OVERRIDES.get(r['word'].lower(), g)
    e = {k: r.get(k) for k in ('word', 'kind', 'brand', 'owner', 'launch_year', 'original_meaning', 'winner', 'confidence', 'reason', 'source_url', 'brand_views', 'original_views', 'brand_share', 'no_brand_article', 'cap_pre', 'cap_2022', 'pre_launch_per_million')}
    e.update(pre_launch_per_million=prefreq(r), group=g, abandoned=r['word'].lower() in ABANDONED)
    r['launch_year'] = LAUNCH.get(r['word'].lower(), r['launch_year']); e['launch_year'] = r['launch_year']
    n = names.get(r['word'].capitalize())
    if n and 'us' in n:
        e['us_drop'] = drops(n['us'], r['launch_year'])
        e['name_series'] = {s: {str(y): c for y, c in sorted(v.items()) if y >= 2000} for s, v in n.items()}
    w = r['word'].lower()
    e['english'] = w not in FOREIGN and (any(x in LOWER for x in stems(w)) or w in ENGLISH or ('name_series' in e and r['kind'] == 'name'))
    e['word'] = w.capitalize() if r['kind'] in ('name', 'place') else w  # headwords lowercase, proper names capitalised (owner, 2026-11-09)
    out.append(e)
ssa = {}
for y in range(1970, 2026):
    for l in open(f'data/raw/ssa/yob{y}.txt'):
        n, sx, c = l.strip().split(',')
        if n == 'Alexa': ssa[str(y)] = ssa.get(str(y), 0) + int(c)
alexa_long = {'us': ssa, 'uk': {str(y): c for y, c in sorted(names['Alexa']['uk'].items())}}
json.dump({'entries': out, 'alexa_long': alexa_long}, open('site/data.json', 'w'), separators=(',', ':'))
print(len(out), collections.Counter(e['group'] for e in out))
print([(e['word'], e['us_drop']) for e in out if e['word'] in ('Alexa', 'Siri', 'Tesla')])
