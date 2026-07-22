import json
from pathlib import Path

import pytest

from openflat.search_quests import (
    InvalidSearchQuestError,
    SearchQuestAlreadyExistsError,
    SearchQuestNotEmptyError,
    SearchQuestNotFoundError,
    SearchQuestUpdate,
    create_search_quest,
    delete_search_quest,
    list_search_quests,
    open_search_quest,
    slugify_search_quest_title,
    update_search_quest,
)


def test_creates_and_opens_search_quest(tmp_path: Path) -> None:
    quest = create_search_quest(
        "Vinohrady rentals",
        description="Long-term rentals",
        data_directory=tmp_path,
    )

    assert quest.directory == tmp_path / "vinohrady-rentals"
    assert quest.raw_directory.is_dir()
    manifest_data = json.loads((quest.directory / "quest.json").read_text(encoding="utf-8"))
    assert manifest_data["schema_version"] == 1
    assert manifest_data["slug"] == "vinohrady-rentals"
    assert manifest_data["created_at"].endswith("Z")

    opened = open_search_quest("vinohrady-rentals", data_directory=tmp_path)
    assert opened == quest


@pytest.mark.parametrize(
    "slug",
    ["", ".", "..", "Vinohrady", "one_two", "one/two", "one--two"],
)
def test_rejects_invalid_slugs(slug: str, tmp_path: Path) -> None:
    with pytest.raises(InvalidSearchQuestError):
        create_search_quest("A quest", slug=slug, data_directory=tmp_path)


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Vinohrady rentals", "vinohrady-rentals"),
        ("Pronájem: Vinohrady + Žižkov", "pronajem-vinohrady-zizkov"),
        ("2+kk under 30 000 Kč", "2-kk-under-30-000-kc"),
    ],
)
def test_generates_slug_from_title(title: str, slug: str) -> None:
    assert slugify_search_quest_title(title) == slug


def test_rejects_title_that_cannot_generate_slug(tmp_path: Path) -> None:
    with pytest.raises(InvalidSearchQuestError, match="ASCII"):
        create_search_quest("東京", data_directory=tmp_path)


def test_rejects_duplicate_search_quest(tmp_path: Path) -> None:
    create_search_quest("Quest", data_directory=tmp_path)

    with pytest.raises(SearchQuestAlreadyExistsError):
        create_search_quest("Quest", data_directory=tmp_path)


def test_opens_only_complete_valid_search_quests(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "quest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(InvalidSearchQuestError):
        open_search_quest("incomplete", data_directory=tmp_path)
    with pytest.raises(SearchQuestNotFoundError):
        open_search_quest("missing", data_directory=tmp_path)


def test_lists_search_quests_in_slug_order(tmp_path: Path) -> None:
    second = create_search_quest("Žižkov", data_directory=tmp_path)
    first = create_search_quest("Vinohrady", data_directory=tmp_path)
    (tmp_path / "not-a-quest").mkdir()

    assert list_search_quests(data_directory=tmp_path) == [first, second]


def test_updates_search_quest_metadata(tmp_path: Path) -> None:
    quest = create_search_quest(
        "Original",
        slug="quest",
        description="Temporary",
        data_directory=tmp_path,
    )

    updated = update_search_quest(
        quest,
        SearchQuestUpdate(title="Updated", description=None),
    )

    assert updated.manifest.title == "Updated"
    assert updated.manifest.description is None
    assert updated.manifest.slug == quest.manifest.slug
    assert updated.manifest.created_at == quest.manifest.created_at
    assert open_search_quest("quest", data_directory=tmp_path) == updated


def test_rejects_invalid_search_quest_update(tmp_path: Path) -> None:
    quest = create_search_quest("Original", slug="quest", data_directory=tmp_path)

    with pytest.raises(InvalidSearchQuestError):
        update_search_quest(quest, SearchQuestUpdate(title=""))


def test_deletes_empty_search_quest(tmp_path: Path) -> None:
    quest = create_search_quest("Quest", data_directory=tmp_path)

    delete_search_quest(quest)

    assert not quest.directory.exists()


def test_requires_force_to_delete_search_quest_data(tmp_path: Path) -> None:
    quest = create_search_quest("Quest", data_directory=tmp_path)
    quest.raw_path("bezrealitky", "432912").write_text("{}", encoding="utf-8")

    with pytest.raises(SearchQuestNotEmptyError, match="force=True"):
        delete_search_quest(quest)
    assert quest.directory.exists()

    delete_search_quest(quest, force=True)
    assert not quest.directory.exists()


@pytest.mark.parametrize(
    ("provider", "record_id"),
    [("../other", "1"), ("bezrealitky", "../1"), ("Bezrealitky", "1")],
)
def test_rejects_unsafe_raw_paths(provider: str, record_id: str, tmp_path: Path) -> None:
    quest = create_search_quest("Quest", data_directory=tmp_path)

    with pytest.raises(InvalidSearchQuestError):
        quest.raw_path(provider, record_id)
