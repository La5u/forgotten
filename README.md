# lowercase

What happens to a word when a brand takes it, and to a brand when it becomes a word. Measured by how often each is written with a capital letter in books.

Site: [lowercase.lasu.dev](https://lowercase.lasu.dev)

## The three pages

| Page | File | What it shows |
| --- | --- | --- |
| **forgotten**: words brands took | `site/index.html` | 954 English words (1,304 in all languages) that a company, product or fictional character now shares: *twitter*, *kindle*, *tinder*, *slack*. Each is sorted into Taken, Contested, Kept or Watching by whether the original meaning still comes first. |
| **generic**: brands that became words | `site/generic.html` | 167 brand names used as the ordinary word for the thing: *escalator*, *zipper*, *kleenex*, *lego*. Sorted into Lost (legally generic), Slipping (losing its capitals) and Held (still capitalised nine times in ten). |
| **namesake**: baby names | `site/names.html` | Whether US parents drop a name after a brand or character takes it. Alexa and Siri fell sharply; most names did not. |

## Data

- **Google Books Ngram** (English): lowercase and capitalised uses per year, 1900–2022.
- **Wikipedia**: monthly page views for the brand and the original meaning, disambiguation pages to find candidates, and the [list of generic and genericized trademarks](https://en.wikipedia.org/wiki/List_of_generic_and_genericized_trademarks).
- **Wiktionary**: monthly English Wiktionary page views of the plain word where the old meaning has no Wikipedia article, scaled by how much smaller Wiktionary traffic is for words of similar frequency; the result is shown as an estimate (`scripts/fetch_wiktionary_views.py`).
- **US Social Security Administration**: births per name and year.

Candidate words were proposed and judged with language models, then reviewed by hand. Launch years and owners can be wrong; corrections are welcome.

## Run it

The site is static, with no build step:

```sh
python3 -m http.server -d site
```

## Rebuild the data

Scripts are in `scripts/`; most need only the Python standard library, a few need `requests`. Downloads are cached in `data/raw/`, which is not in the repository, so a full rebuild fetches everything again.

- `scripts/pipeline.sh` runs the main chain for new candidate words: merge, book histories, Wikipedia mapping, page views, classification, review.
- `scripts/build_site_data.py` writes `site/data.json`.
- `scripts/build_generic.py` writes `site/generic.json`.
- `scripts/build_names.py` and `scripts/build_name_controls.py` write the baby-name files.
- `scripts/reddit_generic.py OUT.svg` draws the generic chart as a static image.

## Contributing

Open an issue or pull request with a word and the brand that took it, or a brand that became a word. A source for the launch year helps.

## Licence

[MIT](LICENSE)
