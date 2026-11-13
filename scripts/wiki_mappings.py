"""Latest mapping per pair; ties use the filename, never filesystem glob order."""
import glob, json, os, re
def mappings():
    out = {}
    for p in sorted(glob.glob('data/raw/wiki_map/*.jsonl'), key=lambda p: (os.stat(p).st_mtime_ns, p)):
        for l in open(p):
            if l.startswith('{'):
                r = json.loads(l)
                k = (r['word'].lower(), re.sub(r' \(\d{4}\)$', '', r['brand']).lower())
                merged = out.setdefault(k, {})
                for f, v in r.items():
                    if f in ('brand_article', 'original_article') and v == '-': merged.pop(f, None)
                    elif v not in ('', None): merged[f] = v  # empty re-maps keep older values
    return out
