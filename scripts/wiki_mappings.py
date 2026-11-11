"""Latest mapping per pair; ties use the filename, never filesystem glob order."""
import glob, json, os, re
def mappings():
    out = {}
    for p in sorted(glob.glob('data/raw/wiki_map/*.jsonl'), key=lambda p: (os.stat(p).st_mtime_ns, p)):
        for l in open(p):
            if l.startswith('{'):
                r = json.loads(l)
                k = (r['word'].lower(), re.sub(r' \(\d{4}\)$', '', r['brand']).lower())
                out[k] = {**out.get(k, {}), **{f: v for f, v in r.items() if v not in ('', None)}}  # an empty re-map never erases an older article
    return out
