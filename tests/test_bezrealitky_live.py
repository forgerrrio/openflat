"""Opt-in integration tests against manually selected Bezrealitky listings."""

import os

import pytest

from openflat.bezrealitky import fetch_listing_page_json

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("OPENFLAT_LIVE_TESTS") != "1",
        reason="set OPENFLAT_LIVE_TESTS=1 to access live Bezrealitky listings",
    ),
]

LIVE_LISTINGS = [
    (
        "923060",
        "https://www.bezrealitky.cz/nemovitosti-byty-domy/"
        "923060-nabidka-pronajem-bytu-budecska-praha",
    ),
    (
        "1029954",
        "https://www.bezrealitky.cz/nemovitosti-byty-domy/"
        "1029954-nabidka-pronajem-bytu-luzicka-praha",
    ),
]


@pytest.mark.parametrize(("expected_id", "url"), LIVE_LISTINGS)
def test_fetches_selected_listing(expected_id: str, url: str) -> None:
    page = fetch_listing_page_json(url)
    advert = page.props.page_props.orig_advert

    assert advert.id == expected_id
    assert advert.address
    assert advert.offer_type == "PRONAJEM"
