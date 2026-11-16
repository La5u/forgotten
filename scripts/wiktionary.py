"""English Wiktionary as the stand-in for the original meaning (cache from scripts/fetch_wiktionary_views.py).
views(word): median monthly views over the given months, None if the page is missing.
page(word): 'ok', 'stub' (English section only has form-of definitions such as "plural of") or 'no_english'."""
import json, os, re, statistics
D = 'data/raw/wiktionary'
load = lambda p: json.load(open(p)) if os.path.exists(p) else {}
T, V, X = load(f'{D}/titles.json'), load(f'{D}/views.json'), load(f'{D}/wikitext.json')
def views(w, months): return statistics.median(V[w].get(k, 0) for k in months) if T.get(w) and w in V else None
LABEL = re.compile(r'\{\{(lb|lbl|label|q|qualifier|i|gloss|sense)\|[^{}]*\}\}')
NOT_FORM = {'synonym of'}  # a synonym is a definition in its own right
def form_only(d):
    """True if the definition is one form-of template ({{plural of|en|snicker}}, {{alternative case form of|en|Pampers|t=...}})
    and nothing else but punctuation; nested templates inside it are allowed."""
    m = re.match(r'\{\{([^|{}]+)\|', d)
    if not m or not m.group(1).strip().lower().endswith(' of') or m.group(1).strip().lower() in NOT_FORM: return False
    depth, i = 0, 0
    while i < len(d):
        if d.startswith('{{', i): depth += 1; i += 2
        elif d.startswith('}}', i):
            depth -= 1; i += 2
            if depth == 0: return not d[i:].strip(' .,;:')
        else: i += 1
    return False
def page(w):
    t = X.get(w)
    if t is None: return None
    m = re.search(r'^==\s*English\s*==\s*$(.*?)(?=^==[^=]|\Z)', t, re.M | re.S)
    if not m: return 'no_english'
    defs = [LABEL.sub('', re.sub(r'^#+', '', l)).strip() for l in m.group(1).splitlines() if re.match(r'#+(?![:*])', l)]
    return 'ok' if any(d and not form_only(d) for d in defs) else 'stub'
