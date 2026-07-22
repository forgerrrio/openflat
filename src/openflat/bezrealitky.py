"""Extract and validate raw listing data embedded in Bezrealitky pages."""

import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from openflat.search_quests import SearchQuest, open_search_quest

_ALLOWED_HOSTS = frozenset({"bezrealitky.cz", "www.bezrealitky.cz"})
_LISTING_PATH = re.compile(r"^/nemovitosti-byty-domy/\d+(?:-[^/]+)?/?$")
_MAX_PAGE_BYTES = 5 * 1024 * 1024
_HEADERS = {
    "User-Agent": "openflat (manual listing import)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "cs,en;q=0.8",
}


class BezrealitkyError(Exception):
    """Base exception for Bezrealitky listing operations."""


class InvalidListingUrlError(BezrealitkyError, ValueError):
    """Raised when a URL is not a supported Bezrealitky listing URL."""


class ListingFetchError(BezrealitkyError):
    """Raised when a Bezrealitky listing page cannot be fetched."""


class ListingDataError(BezrealitkyError):
    """Raised when embedded listing JSON cannot be extracted from a page."""


class ListingSaveError(BezrealitkyError):
    """Raised when extracted listing JSON cannot be saved."""


class _RawBezrealitkyModel(BaseModel):
    """Keep fields Bezrealitky adds beyond the explicitly typed contract."""

    model_config = ConfigDict(
        extra="allow",
        strict=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class BezrealitkyAdvert(_RawBezrealitkyModel):
    """Stable, useful subset of a raw Bezrealitky advert."""

    id: str = Field(pattern=r"^\d+$")
    uri: str | None = None
    address: str | None = None
    description: str | None = None
    estate_type: str | None = Field(default=None, alias="estateType")
    offer_type: str | None = Field(default=None, alias="offerType")
    disposition: str | None = None
    surface: int | float | None = None
    price: int | float | None = None
    currency: str | None = None
    active: bool | None = None
    archived: bool | None = None


class BezrealitkyPageProps(_RawBezrealitkyModel):
    """Raw Next.js page properties containing the advert."""

    orig_advert: BezrealitkyAdvert = Field(alias="origAdvert")


class BezrealitkyProps(_RawBezrealitkyModel):
    """Raw Next.js properties envelope."""

    page_props: BezrealitkyPageProps = Field(alias="pageProps")


class BezrealitkyPage(_RawBezrealitkyModel):
    """Validated ``__NEXT_DATA__`` from a Bezrealitky listing page."""

    props: BezrealitkyProps
    page: str | None = None


def extract_listing_page_json(html: str) -> BezrealitkyPage:
    """Return validated ``__NEXT_DATA__`` embedded in listing HTML."""
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.select('script#__NEXT_DATA__[type="application/json"]')

    if len(scripts) != 1 or scripts[0].string is None:
        raise ListingDataError("expected exactly one __NEXT_DATA__ application/json script")

    try:
        return BezrealitkyPage.model_validate_json(str(scripts[0].string))
    except ValidationError as error:
        raise ListingDataError(
            "__NEXT_DATA__ does not match the expected Bezrealitky page structure"
        ) from error


def fetch_listing_page_json(
    url: str,
    *,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> BezrealitkyPage:
    """Fetch a listing URL and return its validated ``__NEXT_DATA__`` model.

    ``client`` can be supplied to reuse an existing HTTPX client or substitute a
    mock transport in tests. The caller retains ownership of a supplied client.
    """
    _validate_listing_url(url)

    if client is not None:
        return _fetch_listing_page_json(client, url, timeout)

    with httpx.Client(headers=_HEADERS, follow_redirects=True) as owned_client:
        return _fetch_listing_page_json(owned_client, url, timeout)


def save_listing_page_json(
    url: str,
    search_quest: SearchQuest,
    *,
    timeout: float = 15.0,
    overwrite: bool = False,
    client: httpx.Client | None = None,
) -> Path:
    """Fetch and save raw listing JSON under a search quest's data directory.

    The destination is provider-qualified inside the quest's ``raw`` directory.
    Existing raw data is preserved unless ``overwrite`` is true.
    """
    search_quest = open_search_quest(
        search_quest.manifest.slug,
        data_directory=search_quest.data_directory,
    )
    page = fetch_listing_page_json(url, timeout=timeout, client=client)
    listing_id = page.props.page_props.orig_advert.id
    destination = search_quest.raw_path("bezrealitky", listing_id)

    try:
        mode = "w" if overwrite else "x"
        with destination.open(mode, encoding="utf-8") as output:
            output.write(page.model_dump_json(by_alias=True, exclude_unset=True, indent=2))
            output.write("\n")
    except FileExistsError as error:
        raise ListingSaveError(
            f"raw listing already exists: {destination}; pass overwrite=True to replace it"
        ) from error
    except OSError as error:
        raise ListingSaveError(f"could not save raw listing: {destination}") from error

    return destination


def _fetch_listing_page_json(client: httpx.Client, url: str, timeout: float) -> BezrealitkyPage:
    try:
        response = client.get(
            url,
            headers=_HEADERS,
            follow_redirects=True,
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise ListingFetchError(f"could not fetch Bezrealitky listing: {url}") from error

    _validate_listing_url(str(response.url))

    content_type = response.headers.get("content-type", "")
    if content_type and "text/html" not in content_type.lower():
        raise ListingFetchError(f"Bezrealitky listing returned non-HTML content: {content_type}")
    if len(response.content) > _MAX_PAGE_BYTES:
        raise ListingFetchError("Bezrealitky listing page exceeds the 5 MiB limit")

    return extract_listing_page_json(response.text)


def _validate_listing_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise InvalidListingUrlError(f"invalid listing URL: {url}") from error

    if (
        parsed.scheme != "https"
        or parsed.hostname not in _ALLOWED_HOSTS
        or port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or _LISTING_PATH.fullmatch(parsed.path) is None
    ):
        raise InvalidListingUrlError(f"not a supported Bezrealitky listing URL: {url}")


__all__ = [
    "BezrealitkyAdvert",
    "BezrealitkyError",
    "BezrealitkyPage",
    "BezrealitkyPageProps",
    "BezrealitkyProps",
    "InvalidListingUrlError",
    "ListingDataError",
    "ListingFetchError",
    "ListingSaveError",
    "extract_listing_page_json",
    "fetch_listing_page_json",
    "save_listing_page_json",
]
