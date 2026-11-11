#!/bin/bash
# Runs merge -> histories -> Wikipedia map -> traffic -> classify -> review for new candidates. Usage: pipeline.sh JUDGE_PREFIX
set -u; cd /home/lasu/coding/forgotten; PY=/tmp/fg-venv/bin/python
if [ ! -x "$PY" ]; then echo "Missing $PY; create it with: python3 -m venv /tmp/fg-venv && /tmp/fg-venv/bin/pip install requests" >&2; exit 1; fi
case ${1-} in '') echo 'Supply a batch prefix.' >&2; exit 1;; *[0-9]) set -- "${1}_"; echo "Using unambiguous batch prefix $1" >&2;; esac
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
cd data/raw/wiki_map; for f in "$1"*.txt; do [ -f "$f" ] || continue; n=${f#"$1"}; case ${n%.txt} in ''|*[!0-9]*) continue;; esac; printf '%s\0' "${f%.txt}"; done | xargs -0 -r -P6 -I{} sh -c '[ -s "$1.jsonl" ] && [ "$1.jsonl" -nt "$1.txt" ] || { terra -e low < "$1.txt" > "$1.tmp" 2> "$1.err" && mv "$1.tmp" "$1.jsonl"; echo "$1 $?"; }' _ {}; cd ../../..
for i in 1 2 3 4 5; do $PY -I scripts/fetch_pageviews.py 2>&1 | tail -1 | cut -c1-120; python3 -I -c "
import json,sys
t=json.load(open('data/raw/wiki_titles.json'));v=json.load(open('data/raw/pageviews.json'))
sys.exit(0 if {x for x in t.values() if x}<=set(v) else 1)" && break; sleep 30; done
python3 -I scripts/classify.py | head -1; python3 -I scripts/make_judge_prompts.py "$1"
cd data/raw/judge; for f in "$1"*.txt; do [ -f "$f" ] || continue; n=${f#"$1"}; case ${n%.txt} in ''|*[!0-9]*) continue;; esac; printf '%s\0' "${f%.txt}"; done | xargs -0 -r -P6 -I{} sh -c '[ -s "$1.jsonl" ] && [ "$1.jsonl" -nt "$1.txt" ] || { terra -e medium < "$1.txt" > "$1.tmp" 2> "$1.err" && mv "$1.tmp" "$1.jsonl"; echo "$1 $?"; }' _ {}; cd ../../..
python3 -I scripts/merge_judged.py | cut -c1-1800
