"""Filesystem-backed search quests for grouping housing research."""

import os
import re
import shutil
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_MANIFEST_NAME = "quest.json"
_RAW_DIRECTORY_NAME = "raw"
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PROVIDER_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RECORD_ID_PATTERN = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$")


class SearchQuestError(Exception):
    """Base exception for search quest operations."""


class InvalidSearchQuestError(SearchQuestError, ValueError):
    """Raised when a search quest or its manifest is invalid."""


class SearchQuestAlreadyExistsError(SearchQuestError):
    """Raised when creating a search quest that already exists."""


class SearchQuestNotFoundError(SearchQuestError):
    """Raised when a search quest cannot be found."""


class SearchQuestNotEmptyError(SearchQuestError):
    """Raised when deleting a quest containing research data without force."""


class SearchQuestManifest(BaseModel):
    """Versioned metadata stored in a search quest's ``quest.json`` file."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1] = 1
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("title must not start or end with whitespace")
        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("description must be non-blank without surrounding whitespace")
        return value

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value


class SearchQuestUpdate(BaseModel):
    """Mutable search quest metadata fields."""

    model_config = ConfigDict(extra="forbid", strict=True)

    title: str | None = None
    description: str | None = None


class SearchQuest(BaseModel):
    """Validated handle to a search quest directory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_directory: Path
    manifest: SearchQuestManifest

    @property
    def directory(self) -> Path:
        """Return the quest's directory."""
        return self.data_directory / self.manifest.slug

    @property
    def raw_directory(self) -> Path:
        """Return the quest's raw-data directory."""
        return self.directory / _RAW_DIRECTORY_NAME

    def raw_path(self, provider: str, record_id: str) -> Path:
        """Return a safe, provider-qualified path for one raw JSON record."""
        if _PROVIDER_PATTERN.fullmatch(provider) is None:
            raise InvalidSearchQuestError(f"invalid raw-data provider: {provider}")
        if _RECORD_ID_PATTERN.fullmatch(record_id) is None:
            raise InvalidSearchQuestError(f"invalid raw-data record ID: {record_id}")
        return self.raw_directory / f"{provider}-{record_id}.json"

    @classmethod
    def from_manifest(cls, data_directory: Path, manifest: SearchQuestManifest) -> Self:
        """Construct a handle with a normalized data-directory path."""
        return cls(data_directory=data_directory.resolve(), manifest=manifest)


def create_search_quest(
    title: str,
    *,
    description: str | None = None,
    slug: str | None = None,
    data_directory: str | Path = "data",
) -> SearchQuest:
    """Create and return a new filesystem-backed search quest."""
    resolved_slug = slug if slug is not None else slugify_search_quest_title(title)
    try:
        manifest = SearchQuestManifest(
            slug=resolved_slug,
            title=title,
            description=description,
        )
    except ValidationError as error:
        raise InvalidSearchQuestError("invalid search quest metadata") from error

    root = Path(data_directory).resolve()
    directory = root / manifest.slug
    if directory.exists() or directory.is_symlink():
        raise SearchQuestAlreadyExistsError(f"search quest already exists: {directory}")

    try:
        root.mkdir(parents=True, exist_ok=True)
        directory.mkdir()
        (directory / _RAW_DIRECTORY_NAME).mkdir()
        _write_manifest(directory, manifest)
    except FileExistsError as error:
        raise SearchQuestAlreadyExistsError(f"search quest already exists: {directory}") from error
    except OSError as error:
        raise SearchQuestError(f"could not create search quest: {directory}") from error

    return SearchQuest.from_manifest(root, manifest)


def slugify_search_quest_title(title: str) -> str:
    """Generate a stable ASCII directory slug from a human-facing title."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", errors="ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
    slug = slug[:100].rstrip("-")
    if not slug:
        raise InvalidSearchQuestError(
            "search quest title must contain at least one ASCII letter or number"
        )
    return slug


def open_search_quest(
    slug: str,
    *,
    data_directory: str | Path = "data",
) -> SearchQuest:
    """Open and validate an existing search quest."""
    _validate_slug(slug)
    root = Path(data_directory).resolve()
    directory = root / slug
    manifest_path = directory / _MANIFEST_NAME

    if directory.is_symlink():
        raise InvalidSearchQuestError(f"search quest cannot be a symlink: {directory}")
    if not directory.is_dir() or not manifest_path.is_file():
        raise SearchQuestNotFoundError(f"search quest not found: {directory}")
    raw_directory = directory / _RAW_DIRECTORY_NAME
    if raw_directory.is_symlink() or not raw_directory.is_dir():
        raise InvalidSearchQuestError(f"search quest is missing its raw directory: {directory}")

    try:
        manifest = SearchQuestManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as error:
        raise InvalidSearchQuestError(f"invalid search quest manifest: {manifest_path}") from error

    if manifest.slug != slug:
        raise InvalidSearchQuestError(
            f"manifest slug {manifest.slug!r} does not match directory {slug!r}"
        )
    return SearchQuest.from_manifest(root, manifest)


def list_search_quests(*, data_directory: str | Path = "data") -> list[SearchQuest]:
    """Return all valid search quests ordered by slug."""
    root = Path(data_directory).resolve()
    if not root.exists():
        return []
    if not root.is_dir():
        raise InvalidSearchQuestError(f"data directory is not a directory: {root}")

    quests = []
    for directory in sorted(root.iterdir(), key=lambda path: path.name):
        if directory.is_dir() and (directory / _MANIFEST_NAME).is_file():
            quests.append(open_search_quest(directory.name, data_directory=root))
    return quests


def update_search_quest(
    search_quest: SearchQuest,
    update: SearchQuestUpdate,
) -> SearchQuest:
    """Update mutable metadata and return a refreshed search quest handle."""
    current = open_search_quest(
        search_quest.manifest.slug,
        data_directory=search_quest.data_directory,
    )
    values = current.manifest.model_dump()
    values.update(update.model_dump(exclude_unset=True))

    try:
        manifest = SearchQuestManifest.model_validate(values)
    except ValidationError as error:
        raise InvalidSearchQuestError("invalid search quest update") from error

    try:
        _write_manifest(current.directory, manifest)
    except OSError as error:
        raise SearchQuestError(f"could not update search quest: {current.directory}") from error
    return SearchQuest.from_manifest(current.data_directory, manifest)


def delete_search_quest(search_quest: SearchQuest, *, force: bool = False) -> None:
    """Delete a quest, requiring ``force`` when it contains research data."""
    current = open_search_quest(
        search_quest.manifest.slug,
        data_directory=search_quest.data_directory,
    )
    directory = current.directory
    raw_directory = current.raw_directory
    extra_entries = [
        entry
        for entry in directory.iterdir()
        if entry.name not in {_MANIFEST_NAME, _RAW_DIRECTORY_NAME}
    ]
    has_raw_data = next(raw_directory.iterdir(), None) is not None

    if (has_raw_data or extra_entries) and not force:
        raise SearchQuestNotEmptyError(
            f"search quest contains data: {directory}; pass force=True to delete it"
        )

    try:
        if force:
            shutil.rmtree(directory)
        else:
            raw_directory.rmdir()
            (directory / _MANIFEST_NAME).unlink()
            directory.rmdir()
    except OSError as error:
        raise SearchQuestError(f"could not delete search quest: {directory}") from error


def _write_manifest(directory: Path, manifest: SearchQuestManifest) -> None:
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=directory,
            prefix=".quest-",
            suffix=".json.tmp",
            text=True,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(manifest.model_dump_json(indent=2))
            output.write("\n")
        temporary_path.replace(directory / _MANIFEST_NAME)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _validate_slug(slug: str) -> None:
    if len(slug) > 100 or _SLUG_PATTERN.fullmatch(slug) is None:
        raise InvalidSearchQuestError(f"invalid search quest slug: {slug}")


__all__ = [
    "InvalidSearchQuestError",
    "SearchQuest",
    "SearchQuestAlreadyExistsError",
    "SearchQuestError",
    "SearchQuestManifest",
    "SearchQuestNotEmptyError",
    "SearchQuestNotFoundError",
    "SearchQuestUpdate",
    "create_search_quest",
    "delete_search_quest",
    "list_search_quests",
    "open_search_quest",
    "slugify_search_quest_title",
    "update_search_quest",
]
