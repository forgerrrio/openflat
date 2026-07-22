# Bezrealitky listing data

`openflat.bezrealitky` extracts the raw JSON embedded in a manually selected
Bezrealitky listing page. It does not crawl search results or normalize the
provider's fields.

```python
from openflat.bezrealitky import fetch_listing_page_json

page = fetch_listing_page_json(
    "https://www.bezrealitky.cz/nemovitosti-byty-domy/"
    "432912-nabidka-pronajem-bytu-premyslovska"
)
advert = page.props.page_props.orig_advert

print(advert.address)
print(advert.description)
```

The return value is a `BezrealitkyPage` Pydantic model. It validates the stable
`props.pageProps.origAdvert` envelope and commonly used advert fields. Unknown
fields remain available and are included by `model_dump(by_alias=True)`, so new
provider fields do not disappear when the model is saved again. Use
`exclude_unset=True` when dumping manually to avoid adding absent optional fields.

HTML that has already been downloaded can be processed without another request:

```python
from openflat.bezrealitky import extract_listing_page_json

page = extract_listing_page_json(html)
```

Only HTTPS listing links on `bezrealitky.cz` are accepted. Fetching is synchronous
and performs one request for each explicit function call; the package does not
provide crawling, retries, or browser automation.

## Saving raw listing data

Fetch and save a manually selected listing into a search quest:

```python
from openflat.bezrealitky import save_listing_page_json
from openflat.search_quests import create_search_quest

quest = create_search_quest(
    "Vinohrady rentals",
)
destination = save_listing_page_json(
    "https://www.bezrealitky.cz/nemovitosti-byty-domy/"
    "432912-nabidka-pronajem-bytu-premyslovska",
    quest,
)
```

This creates `data/vinohrady-rentals/raw/bezrealitky-432912.json` and returns that
path. Existing files are preserved by default; pass `overwrite=True` when
intentionally refreshing a raw listing.

## Live integration tests

The normal test suite uses mocked HTTP responses. Manually selected listings can
also be checked against the live provider:

```console
OPENFLAT_LIVE_TESTS=1 uv run pytest -m live
```

These tests are opt-in so routine development and CI do not depend on external
website availability.
