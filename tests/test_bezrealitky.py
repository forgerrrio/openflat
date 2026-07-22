import json
from pathlib import Path

import httpx
import pytest

from openflat.bezrealitky import (
    BezrealitkyPage,
    InvalidListingUrlError,
    ListingDataError,
    ListingFetchError,
    ListingSaveError,
    extract_listing_page_json,
    fetch_listing_page_json,
    save_listing_page_json,
)
from openflat.search_quests import (
    SearchQuestNotFoundError,
    create_search_quest,
    delete_search_quest,
)

LISTING_URL = (
    "https://www.bezrealitky.cz/nemovitosti-byty-domy/432912-nabidka-pronajem-bytu-premyslovska"
)


def listing_html(*, advert: object | None = None) -> str:
    if advert is None:
        advert = {
            "id": "432912",
            "address": "Přemyslovská, Praha - Vinohrady",
            "description": "Příjemný byt",
        }
    data = {"props": {"pageProps": {"origAdvert": advert}}, "page": "/detail/[slug]"}
    return (
        "<!doctype html><html><body>"
        '<script type="application/json" id="__NEXT_DATA__">'
        f"{json.dumps(data, ensure_ascii=False)}"
        "</script></body></html>"
    )


def test_extracts_raw_next_data() -> None:
    page = extract_listing_page_json(listing_html())

    assert isinstance(page, BezrealitkyPage)
    assert page.page == "/detail/[slug]"
    assert page.props.page_props.orig_advert.description == "Příjemný byt"


def test_preserves_unknown_raw_fields() -> None:
    html = listing_html(advert={"id": "432912", "newAdvertField": {"value": 1}})

    page = extract_listing_page_json(html)
    raw = page.model_dump(by_alias=True)

    assert raw["props"]["pageProps"]["origAdvert"]["newAdvertField"] == {"value": 1}


@pytest.mark.parametrize(
    "html",
    [
        "<html></html>",
        '<script id="__NEXT_DATA__" type="application/json">{</script>',
        '<script id="__NEXT_DATA__" type="application/json">[]</script>',
        ('<script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{}}}</script>'),
        listing_html() + listing_html(),
    ],
)
def test_rejects_missing_or_invalid_page_data(html: str) -> None:
    with pytest.raises(ListingDataError):
        extract_listing_page_json(html)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.bezrealitky.cz/nemovitosti-byty-domy/432912-example",
        "https://example.com/nemovitosti-byty-domy/432912-example",
        "https://www.bezrealitky.cz/vyhledat",
        "https://user@www.bezrealitky.cz/nemovitosti-byty-domy/432912-example",
    ],
)
def test_rejects_unsupported_listing_urls(url: str) -> None:
    with pytest.raises(InvalidListingUrlError):
        fetch_listing_page_json(url)


def test_fetches_and_extracts_listing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("openflat")
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=listing_html(),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        page = fetch_listing_page_json(LISTING_URL, client=client)

    assert page.page == "/detail/[slug]"
    assert page.props.page_props.orig_advert.id == "432912"


def test_rejects_non_html_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"unexpected": True},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ListingFetchError, match="non-HTML"):
            fetch_listing_page_json(LISTING_URL, client=client)


def test_rejects_redirect_away_from_bezrealitky() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.bezrealitky.cz":
            return httpx.Response(302, headers={"location": "https://example.com"})
        return httpx.Response(200, text=listing_html())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(InvalidListingUrlError):
            fetch_listing_page_json(LISTING_URL, client=client)


def test_fetches_and_saves_listing_under_search_quest(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=listing_html(),
        )

    quest = create_search_quest(
        "vinohrady-rentals",
        title="Vinohrady rentals",
        data_directory=tmp_path,
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        destination = save_listing_page_json(
            LISTING_URL,
            quest,
            client=client,
        )

    assert destination == (tmp_path / "vinohrady-rentals" / "raw" / "bezrealitky-432912.json")
    saved = json.loads(destination.read_text(encoding="utf-8"))
    assert saved["props"]["pageProps"]["origAdvert"]["id"] == "432912"
    assert "uri" not in saved["props"]["pageProps"]["origAdvert"]
    assert "Příjemný byt" in destination.read_text(encoding="utf-8")


def test_does_not_overwrite_raw_listing_by_default(tmp_path: Path) -> None:
    quest = create_search_quest("quest", title="Quest", data_directory=tmp_path)
    destination = quest.raw_path("bezrealitky", "432912")
    destination.write_text("original", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text=listing_html())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ListingSaveError, match="overwrite=True"):
            save_listing_page_json(
                LISTING_URL,
                quest,
                client=client,
            )

    assert destination.read_text(encoding="utf-8") == "original"


def test_rejects_listing_without_numeric_id(tmp_path: Path) -> None:
    quest = create_search_quest("quest", title="Quest", data_directory=tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=listing_html(advert={"id": "not-an-id"}),
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ListingDataError, match="expected Bezrealitky"):
            save_listing_page_json(
                LISTING_URL,
                quest,
                client=client,
            )


def test_does_not_save_through_stale_search_quest_handle(tmp_path: Path) -> None:
    quest = create_search_quest("quest", title="Quest", data_directory=tmp_path)
    delete_search_quest(quest)

    with pytest.raises(SearchQuestNotFoundError):
        save_listing_page_json(LISTING_URL, quest)

    assert not quest.directory.exists()
