"""Combine SSA, ONS, NSW and Ontario name counts: data/raw/names_unified.csv (source,name,sex,year,count), 1990 on.
Absent rows mean below the source's publishing threshold, never a true zero."""
import csv, glob, re, openpyxl
out = csv.writer(open('data/raw/names_unified.csv', 'w', newline=''))
out.writerow(['source', 'name', 'sex', 'year', 'count'])
for p in glob.glob('data/raw/ssa/yob*.txt'):
    y = int(re.search(r'yob(\d+)', p)[1])
    if y >= 1990:
        for n, s, c in csv.reader(open(p)):
            out.writerow(['us', n, s, y, c])
wb = openpyxl.load_workbook('data/raw/ons/babynames1996to2025.xlsx', read_only=True, data_only=True)
for t in ('Table_1', 'Table_2'):
    ws = wb[t]; head = None
    title = None
    for r in ws.iter_rows(values_only=True):
        if title is None:
            title = r[0]; sex = 'F' if 'girl' in title.lower() else 'M'; print(title)
        if r[0] == 'Name':
            head = {i: int(h[:4]) for i, h in enumerate(r) if h and h.endswith('Count')}; continue
        if head and r[0]:
            for i, y in head.items():
                if isinstance(r[i], (int, float)):
                    out.writerow(['uk', str(r[0]).capitalize(), sex, y, int(r[i])])
for r in csv.DictReader(open('data/raw/nsw/names.csv', encoding='utf-8-sig')):
    if int(r['Year']) >= 1990:
        out.writerow(['nsw', r['Name'].capitalize(), r['Gender'][0], r['Year'], r['Number']])
for f, s in (('female', 'F'), ('male', 'M')):
    rows = csv.reader(open(f'data/raw/ontario/{f}.csv', encoding='utf-8-sig')); h = next(rows); print(h)
    for y, n, c in (x[:3] for x in rows):
        if y.isdigit() and int(y) >= 1990 and c.isdigit():
            out.writerow(['ontario', n.capitalize(), s, y, c])
