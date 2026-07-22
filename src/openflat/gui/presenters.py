"""Presentation models derived from persisted listing data."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from openflat.bezrealitky import BezrealitkyPage
from openflat.search_quests import SearchQuest

_BEZREALITKY_BASE_URL = "https://www.bezrealitky.cz/nemovitosti-byty-domy"


class ListingSummary(BaseModel):
    """Small listing projection used by the GUI."""

    model_config = ConfigDict(frozen=True)

    id: str
    address: str
    disposition: str | None
    surface: int | float | None
    price: int | float | None
    currency: str | None
    active: bool | None
    archived: bool | None
    source_url: str | None
    raw_path: Path

    @property
    def price_label(self) -> str:
        """Return a compact display value for the provider's raw price."""
        if self.price is None:
            return "Price unavailable"
        amount = f"{self.price:,.0f}".replace(",", " ")
        return f"{amount} {self.currency or ''}".rstrip()

    @property
    def surface_label(self) -> str:
        """Return a compact display value for surface area."""
        if self.surface is None:
            return "Area unavailable"
        return f"{self.surface:g} m²"

    @property
    def status_label(self) -> str:
        """Return a conservative status based on raw provider flags."""
        if self.archived is True or self.active is False:
            return "Inactive"
        if self.active is True:
            return "Active"
        return "Unknown"


class ListingCollection(BaseModel):
    """Listing summaries and non-fatal raw-file loading warnings."""

    model_config = ConfigDict(frozen=True)

    listings: tuple[ListingSummary, ...]
    warnings: tuple[str, ...]


def load_listing_summaries(search_quest: SearchQuest) -> ListingCollection:
    """Load all supported raw listings without failing on one malformed file."""
    listings = []
    warnings = []
    for raw_path in sorted(search_quest.raw_directory.glob("bezrealitky-*.json")):
        try:
            page = BezrealitkyPage.model_validate_json(raw_path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            warnings.append(f"Could not read {raw_path.name}: {error}")
            continue

        advert = page.props.page_props.orig_advert
        source_url = f"{_BEZREALITKY_BASE_URL}/{advert.uri}" if advert.uri is not None else None
        listings.append(
            ListingSummary(
                id=advert.id,
                address=advert.address or "Address unavailable",
                disposition=advert.disposition,
                surface=advert.surface,
                price=advert.price,
                currency=advert.currency,
                active=advert.active,
                archived=advert.archived,
                source_url=source_url,
                raw_path=raw_path,
            )
        )

    listings.sort(key=lambda listing: int(listing.id), reverse=True)
    return ListingCollection(listings=tuple(listings), warnings=tuple(warnings))


__all__ = ["ListingCollection", "ListingSummary", "load_listing_summaries"]
