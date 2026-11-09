"""English check: Hunspell en_US/en_GB/en_AU/en_CA (lowercase entries = common words, Capitalised = English
proper nouns), with simple suffix stripping because Hunspell stores stems (teams -> team, dishonored -> dishonor)."""
import glob
LOWER, PROPER = set(), set()
for f in ('en_US', 'en_GB', 'en_AU', 'en_CA'):
    for l in open(f'/usr/share/hunspell/{f}.dic', encoding='utf-8', errors='ignore').read().split('\n')[1:]:
        w = l.split('/')[0].strip()
        if not w.isalpha(): continue
        if w.islower(): LOWER.add(w)
        elif w[0].isupper() and w[1:].islower(): PROPER.add(w.lower())
def stems(w):
    yield w
    for suf, rep in (('ies', 'y'), ('es', ''), ('s', ''), ('ed', ''), ('ed', 'e'), ('ing', ''), ('ing', 'e'), ('ly', '')):
        if w.endswith(suf) and len(w) - len(suf) >= 3: yield w[:-len(suf)] + rep
def in_dictionary(word):
    w = word.lower()
    return any(s in LOWER for s in stems(w)) or w in PROPER
