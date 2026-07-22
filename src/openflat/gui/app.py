"""NiceGUI application for local openflat workflows."""

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

from nicegui import run, ui

from openflat.bezrealitky import BezrealitkyError, save_listing_page_json
from openflat.gui.presenters import ListingSummary, load_listing_summaries
from openflat.search_quests import (
    SearchQuest,
    SearchQuestError,
    SearchQuestNotFoundError,
    create_search_quest,
    delete_search_quest,
    list_search_quests,
    open_search_quest,
)

_APP_TITLE = "openflat"
_SLUG_HELP = "Lowercase letters, numbers, and single hyphens"

ui.add_css(
    """
    body { background: #f7f7f5; color: #252522; }
    .openflat-shell { width: min(1100px, calc(100vw - 2rem)); margin: 0 auto; }
    .openflat-card { border: 1px solid #e2e2dc; box-shadow: none; }
    """,
    shared=True,
)


def _data_directory() -> Path:
    return Path(os.environ.get("OPENFLAT_DATA_DIRECTORY", "data")).resolve()


@contextmanager
def _page_shell() -> Iterator[None]:
    with ui.header().classes("bg-white text-stone-900 border-b border-stone-200"):
        with ui.row().classes("openflat-shell items-center py-2"):
            ui.link(_APP_TITLE, "/").classes("text-xl font-semibold no-underline")
            ui.space()
            ui.label("Apartment search workspace").classes("text-sm text-stone-500")
    with ui.column().classes("openflat-shell gap-5 py-8"):
        yield


def _notify_error(error: Exception) -> None:
    ui.notify(str(error), type="negative", close_button=True, multi_line=True)


@ui.page("/")
def quest_index_page() -> None:
    """Render search quest discovery and creation."""
    ui.page_title(f"Search quests · {_APP_TITLE}")
    data_directory = _data_directory()

    with _page_shell():
        with ui.row().classes("w-full items-start"):
            with ui.column().classes("gap-1"):
                ui.label("Search quests").classes("text-3xl font-semibold")
                ui.label("Create a workspace or continue reviewing listings.").classes(
                    "text-stone-600"
                )
            ui.space()

            create_dialog = ui.dialog()
            with create_dialog, ui.card().classes("w-[32rem] max-w-full"):
                ui.label("Create search quest").classes("text-xl font-semibold")
                slug_input = ui.input("Slug", placeholder="vinohrady-rentals").classes("w-full")
                ui.label(_SLUG_HELP).classes("text-xs text-stone-500 -mt-3")
                title_input = ui.input("Title", placeholder="Vinohrady rentals").classes("w-full")
                description_input = ui.textarea(
                    "Description", placeholder="What are you looking for?"
                ).classes("w-full")

                async def create_quest() -> None:
                    create_button.disable()
                    notification = ui.notification(
                        "Creating search quest…", spinner=True, timeout=None
                    )
                    try:
                        quest = await run.io_bound(
                            partial(
                                create_search_quest,
                                (slug_input.value or "").strip(),
                                title=(title_input.value or "").strip(),
                                description=(description_input.value or "").strip() or None,
                                data_directory=data_directory,
                            )
                        )
                    except SearchQuestError as error:
                        notification.dismiss()
                        _notify_error(error)
                        create_button.enable()
                        return

                    notification.dismiss()
                    assert quest is not None
                    ui.notify("Search quest created", type="positive")
                    ui.navigate.to(f"/quests/{quest.manifest.slug}")

                with ui.row().classes("w-full justify-end"):
                    ui.button("Cancel", on_click=create_dialog.close).props("flat")
                    create_button = ui.button("Create", on_click=create_quest)

            ui.button("New quest", icon="add", on_click=create_dialog.open)

        @ui.refreshable
        def quest_cards() -> None:
            try:
                quests = list_search_quests(data_directory=data_directory)
            except SearchQuestError as error:
                _notify_error(error)
                return

            if not quests:
                with ui.card().classes("openflat-card w-full items-center p-10"):
                    ui.icon("travel_explore", size="3rem").classes("text-stone-400")
                    ui.label("No search quests yet").classes("text-lg font-medium")
                    ui.label("Create one to start collecting listings.").classes("text-stone-500")
                return

            with ui.grid(columns=2).classes("w-full gap-4 max-md:grid-cols-1"):
                for quest in quests:
                    _quest_card(quest, quest_cards.refresh)

        quest_cards()


def _quest_card(search_quest: SearchQuest, refresh: Callable[[], object]) -> None:
    collection = load_listing_summaries(search_quest)
    with ui.card().classes("openflat-card w-full"):
        with ui.row().classes("w-full items-start"):
            with ui.column().classes("gap-1"):
                ui.link(
                    search_quest.manifest.title,
                    f"/quests/{search_quest.manifest.slug}",
                ).classes("text-xl font-semibold no-underline")
                ui.label(search_quest.manifest.slug).classes("font-mono text-xs text-stone-500")
            ui.space()
            ui.badge(f"{len(collection.listings)} listings").props("outline")

        if search_quest.manifest.description:
            ui.label(search_quest.manifest.description).classes("text-stone-600")

        with ui.row().classes("w-full items-center"):
            ui.label(f"Created {search_quest.manifest.created_at:%Y-%m-%d}").classes(
                "text-xs text-stone-500"
            )
            ui.space()
            ui.button(
                "Delete",
                icon="delete_outline",
                on_click=lambda: _show_delete_dialog(search_quest, refresh),
            ).props("flat color=negative")


def _show_delete_dialog(search_quest: SearchQuest, refresh: Callable[[], object]) -> None:
    dialog = ui.dialog()
    with dialog, ui.card().classes("w-[30rem] max-w-full"):
        ui.label("Delete search quest?").classes("text-xl font-semibold")
        ui.label(
            f"This permanently deletes “{search_quest.manifest.title}” and all raw listings."
        ).classes("text-stone-600")

        async def remove_quest() -> None:
            delete_button.disable()
            try:
                await run.io_bound(partial(delete_search_quest, search_quest, force=True))
            except SearchQuestError as error:
                _notify_error(error)
                delete_button.enable()
                return
            dialog.close()
            ui.notify("Search quest deleted", type="positive")
            refresh()

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            delete_button = ui.button("Delete", on_click=remove_quest).props("color=negative")
    dialog.open()


@ui.page("/quests/{slug}")
def quest_detail_page(slug: str) -> None:
    """Render one search quest and its collected listings."""
    try:
        search_quest = open_search_quest(slug, data_directory=_data_directory())
    except SearchQuestNotFoundError:
        with _page_shell():
            ui.label("Search quest not found").classes("text-3xl font-semibold")
            ui.link("Back to search quests", "/")
        return
    except SearchQuestError as error:
        with _page_shell():
            ui.label("Could not open search quest").classes("text-3xl font-semibold")
            ui.label(str(error)).classes("text-negative")
            ui.link("Back to search quests", "/")
        return

    ui.page_title(f"{search_quest.manifest.title} · {_APP_TITLE}")
    with _page_shell():
        ui.link("← Search quests", "/").classes("text-sm no-underline")
        with ui.row().classes("w-full items-start"):
            with ui.column().classes("gap-1"):
                ui.label(search_quest.manifest.title).classes("text-3xl font-semibold")
                ui.label(search_quest.manifest.slug).classes("font-mono text-xs text-stone-500")
                if search_quest.manifest.description:
                    ui.label(search_quest.manifest.description).classes("text-stone-600")

        with ui.card().classes("openflat-card w-full"):
            ui.label("Add Bezrealitky listing").classes("text-xl font-semibold")
            ui.label("Paste a manually selected apartment listing URL.").classes(
                "text-sm text-stone-500"
            )
            url_input = ui.input(
                "Listing URL",
                placeholder="https://www.bezrealitky.cz/nemovitosti-byty-domy/…",
            ).classes("w-full")

            async def add_listing() -> None:
                add_button.disable()
                notification = ui.notification("Fetching listing…", spinner=True, timeout=None)
                try:
                    destination = await run.io_bound(
                        save_listing_page_json,
                        (url_input.value or "").strip(),
                        search_quest,
                    )
                except (BezrealitkyError, SearchQuestError) as error:
                    notification.dismiss()
                    _notify_error(error)
                    add_button.enable()
                    return

                notification.dismiss()
                assert destination is not None
                url_input.value = ""
                ui.notify(f"Saved {destination.name}", type="positive")
                listing_cards.refresh()
                add_button.enable()

            with ui.row().classes("w-full justify-end"):
                add_button = ui.button("Add listing", icon="add", on_click=add_listing)

        @ui.refreshable
        def listing_cards() -> None:
            collection = load_listing_summaries(search_quest)
            with ui.row().classes("w-full items-center"):
                ui.label("Listings").classes("text-2xl font-semibold")
                ui.badge(str(len(collection.listings))).props("outline")

            for warning in collection.warnings:
                ui.label(warning).classes("text-sm text-negative")

            if not collection.listings:
                with ui.card().classes("openflat-card w-full items-center p-8"):
                    ui.label("No listings collected yet").classes("text-stone-500")
                return

            with ui.column().classes("w-full gap-3"):
                for listing in collection.listings:
                    _listing_card(listing)

        listing_cards()


def _listing_card(listing: ListingSummary) -> None:
    with ui.card().classes("openflat-card w-full"):
        with ui.row().classes("w-full items-center gap-4"):
            with ui.column().classes("gap-1 grow"):
                ui.label(listing.address).classes("text-lg font-medium")
                details = [
                    value
                    for value in (
                        listing.disposition,
                        listing.surface_label,
                        listing.price_label,
                    )
                    if value
                ]
                ui.label(" · ".join(details)).classes("text-sm text-stone-600")
                ui.label(f"Bezrealitky #{listing.id}").classes("font-mono text-xs text-stone-500")
            ui.badge(listing.status_label).props(
                "outline color=positive"
                if listing.status_label == "Active"
                else "outline color=grey"
            )
            if listing.source_url is not None:
                ui.link("Open source ↗", listing.source_url, new_tab=True).classes("no-underline")


def main() -> None:
    """Run the local-only openflat GUI server."""
    port = int(os.environ.get("OPENFLAT_GUI_PORT", "8080"))
    ui.run(
        title=_APP_TITLE,
        host="127.0.0.1",
        port=port,
        reload=False,
        show=False,
    )


__all__ = ["main"]
