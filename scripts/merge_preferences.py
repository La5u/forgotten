"""Judged bare-word alternatives to ineligible higher-traffic brands."""
import json
SWAPS = json.load(open('data/brand_swaps.json'))
PREFERRED = {'explorer': 'Internet Explorer', 'spark': 'Apache Spark', 'pilot': 'PalmPilot', 'boost': 'Boost',
             'thunderbird': 'Mozilla Thunderbird', 'malibu': 'Malibu', 'polo': 'Polo Ralph Lauren', 'mint': 'Mint', 'life': 'Life'}
PREFERRED.update({w: s['row']['brand'] for w, s in SWAPS.items()})
