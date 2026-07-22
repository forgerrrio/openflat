import json
from pathlib import Path

from openflat.gui.presenters import load_listing_summaries
from openflat.search_quests import create_search_quest


def write_listing(
    raw_directory: Path,
    listing_id: str,
    *,
    address: str,
    price: int | None,
    active: bool | None = True,
) -> None:
    advert = {
        "id": listing_id,
        "uri": f"{listing_id}-nabidka-pronajem-bytu-example",
        "address": address,
        "disposition": "2+kk",
        "surface": 53,
        "price": price,
        "currency": "CZK",
        "active": active,
        "archived": False,
    }
    page = {"props": {"pageProps": {"origAdvert": advert}}}
    (raw_directory / f"bezrealitky-{listing_id}.json").write_text(
        json.dumps(page),
        encoding="utf-8",
    )


def test_loads_listing_summaries_for_gui(tmp_path: Path) -> None:
    quest = create_search_quest("quest", title="Quest", data_directory=tmp_path)
    write_listing(
        quest.raw_directory,
        "923060",
        address="Budečská, Praha - Vinohrady",
        price=30_500,
    )
    write_listing(
        quest.raw_directory,
        "1029954",
        address="Lužická, Praha - Vinohrady",
        price=None,
        active=False,
    )

    collection = load_listing_summaries(quest)

    assert [listing.id for listing in collection.listings] == ["1029954", "923060"]
    assert collection.warnings == ()
    newer, older = collection.listings
    assert newer.status_label == "Inactive"
    assert newer.price_label == "Price unavailable"
    assert older.price_label == "30 500 CZK"
    assert older.surface_label == "53 m²"
    assert older.source_url == (
        "https://www.bezrealitky.cz/nemovitosti-byty-domy/923060-nabidka-pronajem-bytu-example"
    )


def test_reports_malformed_raw_listing_without_hiding_valid_ones(tmp_path: Path) -> None:
    quest = create_search_quest("quest", title="Quest", data_directory=tmp_path)
    write_listing(
        quest.raw_directory,
        "923060",
        address="Budečská, Praha - Vinohrady",
        price=30_500,
    )
    (quest.raw_directory / "bezrealitky-broken.json").write_text(
        "not JSON",
        encoding="utf-8",
    )

    collection = load_listing_summaries(quest)

    assert [listing.id for listing in collection.listings] == ["923060"]
    assert len(collection.warnings) == 1
    assert "bezrealitky-broken.json" in collection.warnings[0]
