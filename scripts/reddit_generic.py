#!/usr/bin/env python3
"""Make a phone-friendly, self-contained SVG from site/generic.json."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET


GROUPS = {
    'lost': ('Lost', '#d0342c', 'legally generic or lapsed'),
    'slipping': ('Slipping', '#b98700', 'still a trademark, losing its capitals'),
    'held': ('Held', '#0e8a5f', 'still a trademark, capitalised 9 times in 10'),
}
FAMILIAR = (
    'google lego kleenex xerox velcro frisbee jacuzzi band-aid tupperware '
    'post-it photoshop taser jeep popsicle styrofoam teflon vaseline q-tip '
    'sharpie roomba pyrex ziploc zamboni hoover walkman powerpoint jell-o play-doh'
).split()
BOTTOM_BRANDS = (
    'xerox', 'tupperware', 'photoshop', 'q-tip', 'sharpie', 'ziploc',
    'zamboni', 'powerpoint', 'jell-o', 'play-doh', 'polaroid', 'kool-aid',
    'scotch tape', 'epipen',
)
# Arial advances in units per 1000 em, with separate regular and bold metrics.
ARIAL_ADVANCES = tuple(
    {char: advance for advance, chars in groups for char in chars}
    for groups in (
        ((222, 'ijl'), (278, 'ft .,:;!|'), (333, 'r-()'), (500, 'cksvxyz'),
         (556, 'abdeghnopqu0123456789'), (833, 'm'), (722, 'w'), (191, "'"),
         (667, 'ABEKPSVXY'), (722, 'CDHNRU'), (611, 'FTZ'), (778, 'GOQ'),
         (278, 'I'), (500, 'J'), (556, 'L'), (833, 'M'), (944, 'W')),
        ((278, 'ijl .,:;!|'), (333, 'ft-()'), (389, 'r'), (556, 'aceksvxy0123456789'),
         (500, 'z'), (611, 'bdghnopqu'), (889, 'm'), (778, 'w'), (238, "'"),
         (722, 'ABCDHNRUVXY'), (667, 'EKPS'), (611, 'LFTZ'), (778, 'GOQ'),
         (278, 'I'), (556, 'J'), (833, 'M'), (944, 'W')),
    )
)
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)


def text_width(content, size, bold=False):
    advances = ARIAL_ADVANCES[bold]
    return sum(advances.get(char, 1000) for char in content) * size / 1000 * 1.04


def intersects(a, b):
    """Boxes are (left, top, right, bottom); touching edges are allowed."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def hits_dot(box, dot):
    _, x, y = dot
    dx = x - min(max(x, box[0]), box[2])
    dy = y - min(max(y, box[1]), box[3])
    return dx * dx + dy * dy < 10 ** 2  # Include the white stroke.


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, metavar='OUT.svg')
    parser.add_argument('--url')
    parser.add_argument('--width', type=int, default=2000)
    parser.add_argument('--height', type=int, default=2400)
    parser.add_argument('--check', action='store_true', help='assert collision-free labels')
    args = parser.parse_args()
    if args.width <= 0 or args.height <= args.width:
        parser.error('width must be positive and height must exceed width (portrait)')

    # Work in 2000-wide units so type stays readable at every output width.
    width, height = 2000, args.height * 2000 / args.width
    entries = json.loads((Path(__file__).resolve().parents[1] /
                          'site/generic.json').read_text(encoding='utf-8'))['entries']
    counts = Counter(e['group'] for e in entries)
    svg = ET.Element(f'{{{NS}}}svg', {
        'width': str(args.width), 'height': str(args.height),
        'viewBox': f'0 0 {width} {height:g}', 'role': 'img',
        'font-family': 'Liberation Sans, Arial, Helvetica, sans-serif',
        'aria-label': 'Brand launch year versus lowercase share in books of the 2010s',
    })

    def add(tag, **attrs):
        return ET.SubElement(svg, f'{{{NS}}}{tag}',
                             {k.replace('_', '-'): str(v) for k, v in attrs.items()})

    def text(x, y, content, size=30, fill='#666', **attrs):
        node = add('text', x=x, y=y, font_size=size, fill=fill, **attrs)
        node.text = content
        return node

    add('rect', width=width, height=height, fill='white')
    text(80, 130, 'Brand names that became ordinary words', 76, '#16130f',
         font_family='Georgia, serif')
    text(80, 220, 'Each dot is a brand name. Higher = written in lowercase', 40)
    text(80, 270, 'more often in books of the 2010s, like any other word.', 40)
    for i, (group, (name, color, note)) in enumerate(GROUPS.items()):
        y = 350 + i * 55
        add('circle', cx=96, cy=y - 11, r=11, fill=color)
        text(125, y, f'{name} ({counts[group]}): {note}', 34, '#444')

    left, right, top, bottom = 180, 1920, 650, height - 250
    X = lambda year: left + (max(1850, year) - 1850) / 175 * (right - left)
    Y = lambda share: bottom - share * (bottom - top)
    text(left, top - 40, 'Share written in lowercase, 2010s', 34, '#444')
    for percent in (0, 25, 50, 75, 100):
        y = Y(percent / 100)
        add('line', x1=left, x2=right, y1=y, y2=y,
            stroke='#999' if percent == 50 else '#ddd', stroke_width=2,
            stroke_dasharray='10 10' if percent == 50 else 'none')
        text(left - 25, y + 10, f'{percent}%', text_anchor='end')
    half_width = text_width('half lowercase', 30)
    half_box = (right - half_width - 8, Y(.5) - 48, right - 8, Y(.5) - 12)
    text(half_box[0], half_box[1] + 27, 'half lowercase')
    for year in range(1850, 2026, 25):
        x = X(year)
        add('line', x1=x, x2=x, y1=bottom, y2=bottom + 10, stroke='#888', stroke_width=2)
        text(x, bottom + 55, str(year), text_anchor='middle')
    text((left + right) / 2, bottom + 105, 'Year the brand launched', 34,
         '#444', text_anchor='middle')

    points = [(e, X(e['launch_year']), Y(e['lower_share_recent'])) for e in entries
              if finite(e.get('launch_year')) and finite(e.get('lower_share_recent'))
              and 0 <= e['lower_share_recent'] <= 1]
    for e, x, y in sorted(points, key=lambda p: {'held': 0, 'slipping': 1, 'lost': 2}[p[0]['group']]):
        add('circle', cx=x, cy=y, r=9, fill=GROUPS[e['group']][1],
            stroke='white', stroke_width=2)

    def priority(point):
        e = point[0]
        word = e['word'].lower()
        tier = 0 if e['group'] == 'lost' else 1 if word in FAMILIAR else 2
        rank = FAMILIAR.index(word) if tier == 1 else -e['lower_share_recent']
        return tier, rank, -(e.get('total_recent_per_million') or 0), word

    labels, unlabelled = [], []
    for e, x, y in sorted(points, key=priority):
        word, bold, fs = e['word'].lower(), e['group'] == 'lost', 32
        w, h, gap = text_width(word, fs, bold), fs * 1.2, 16
        candidates = ((x + gap, y - h / 2), (x - gap - w, y - h / 2),
                      (x - w / 2, y - gap - h), (x - w / 2, y + gap),
                      (x + gap, y - gap - h), (x + gap, y + gap),
                      (x - gap - w, y - gap - h), (x - gap - w, y + gap))
        for lx, ly in candidates:
            box = (lx, ly, lx + w, ly + h)
            if (lx < left or ly < top or box[2] > right or box[3] > bottom
                    or any(intersects(box, b) for b in [half_box, *labels])
                    or any(hits_dot(box, p) for p in points)):
                continue
            labels.append(box)
            text(lx, ly + fs * .9, word, fs, '#16130f' if bold else '#444',
                 font_weight=700 if bold else 400)
            break
        else:
            unlabelled.append(word)

    bottom_line = 'Unlabelled near the bottom include: '
    bottom_names = []
    for word in BOTTOM_BRANDS:
        if word not in unlabelled:
            continue
        candidate = bottom_line + ', '.join([*bottom_names, word])
        if text_width(candidate, 30) > width - 160:
            break
        bottom_names.append(word)
    if bottom_names:
        text(80, 510, bottom_line + ', '.join(bottom_names), 30, '#666')

    if args.check:
        for i, box in enumerate(labels):
            assert left <= box[0] <= box[2] <= right and top <= box[1] <= box[3] <= bottom
            assert not any(intersects(box, other) for other in labels[i + 1:])
            assert not any(hits_dot(box, p) for p in points)
            assert not intersects(box, half_box)

    text(80, height - 115, 'Data: Google Books Ngram (English, 2010-2019),')
    brand_count = f'{len(entries)} brands'
    if len(entries) != len(points):
        brand_count += f', {len(points)} plotted'
    text(80, height - 65,
         f"Wikipedia's list of generic and genericized trademarks. {brand_count}.")
    if args.url is not None:
        text(1920, height - 115, args.url, fill='#16130f', text_anchor='end')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(svg).write(args.output, encoding='utf-8', xml_declaration=True)
    if args.check:
        ET.parse(args.output)
    print(f'Dots plotted: {len(points)}')
    print(f'Labelled: {len(labels)}')
    print('Unlabelled words: ' + ', '.join(unlabelled))


if __name__ == '__main__':
    main()
