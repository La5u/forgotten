"""Write mapping batches for judged entries with missing traffic. Usage: remap_missing.py PREFIX"""
import json, sys
rows = json.load(open('data/judged.json'))
site = {r['word'].lower(): r for r in json.load(open('site/data.json'))['entries']}
todo = []
for r in rows:
    e = site.get(r['word'].lower())
    missing = not r.get('brand_views') and not r.get('original_views')
    if missing or (e and e.get('no_brand_article')):
        todo.append(r)
P = open('data/raw/wiki_map/p0.txt').read().split('\n\n')[0] + '\nPrevious mapping found no article or no traffic; look for renamed or moved titles.\n\n'
for r in todo: print(r['word'], '|', r['brand'])
for i in range(0, len(todo), 80):
    b = todo[i:i+80]
    open(f'data/raw/wiki_map/{sys.argv[1]}{i//80}.txt', 'w').write(P + '\n'.join(f"{r['word']} | {r['brand']} ({r['owner']}, {r['launch_year']}) | original: {r['original_meaning']}" for r in b))
print('total', len(todo))
