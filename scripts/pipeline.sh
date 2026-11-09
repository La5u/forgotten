#!/bin/bash
# Runs merge -> histories -> Wikipedia map -> traffic -> classify -> review for new candidates. Usage: pipeline.sh JUDGE_PREFIX
set -u; cd /home/lasu/coding/forgotten; PY=/tmp/fg-venv/bin/python
python3 -I scripts/merge_candidates.py; python3 -I scripts/fetch_ngrams.py | tail -1; python3 -I scripts/fetch_caps.py | tail -1
python3 -I - "$1" <<'E'
import json,glob,re,sys
done=set()
for p in glob.glob('data/raw/wiki_map/*.jsonl'):
    for l in open(p):
        if l.startswith('{'):
            r=json.loads(l); done.add((r['word'].lower(),re.sub(r' \(\d{4}\)$','',r['brand']).lower()))
c=json.load(open('data/candidates.json'))
todo=[r for r in c if (r['word'].lower(),r['brand'].lower()) not in done]
print('map todo',len(todo))
P=open('data/raw/wiki_map/p0.txt').read().split('\n\n')[0]+'\n\n'
for i in range(0,len(todo),80):
    open(f'data/raw/wiki_map/{sys.argv[1]}{i//80}.txt','w').write(P+'\n'.join(f"{r['word']} | {r['brand']} ({r['owner']}, {r['launch_year']}) | original: {r['original_meaning']}" for r in todo[i:i+80]))
E
cd data/raw/wiki_map; ls "$1"*.txt 2>/dev/null | sed 's/.txt//' | xargs -r -P6 -I{} sh -c '[ -s {}.jsonl ] || { terra -e low < {}.txt > {}.tmp 2> {}.err && mv {}.tmp {}.jsonl; echo {} $?; }'; cd ../../..
for i in 1 2 3 4 5; do $PY -I scripts/fetch_pageviews.py 2>&1 | tail -1 | cut -c1-120; python3 -I -c "
import json,sys
t=json.load(open('data/raw/wiki_titles.json'));v=json.load(open('data/raw/pageviews.json'))
sys.exit(0 if {x for x in t.values() if x}<=set(v) else 1)" && break; sleep 30; done
python3 -I scripts/classify.py | head -1; python3 -I scripts/make_judge_prompts.py "$1"
cd data/raw/judge; ls "$1"*.txt 2>/dev/null | sed 's/.txt//' | xargs -r -P6 -I{} sh -c '[ -s {}.jsonl ] || { terra -e medium < {}.txt > {}.tmp 2> {}.err && mv {}.tmp {}.jsonl; echo {} $?; }'; cd ../../..
python3 -I scripts/merge_judged.py | cut -c1-1800
