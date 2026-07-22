# Local graphical interface

openflat includes a NiceGUI application for managing search quests and manually
collecting Bezrealitky listings.

Start it from the repository root:

```console
uv sync
uv run openflat-gui
```

Then open <http://127.0.0.1:8080/>. The server deliberately binds only to the
local machine and has no authentication.

The interface supports:

- creating search quests;
- browsing existing quests;
- adding a Bezrealitky listing from its URL;
- viewing compact listing summaries; and
- deleting a quest after explicit confirmation.

Quest creation asks only for a name and optional description. The filesystem slug
is generated automatically, including normalization of common diacritics.

By default, the application reads and writes the repository's `data/` directory.
Set `OPENFLAT_DATA_DIRECTORY` to use another location, or `OPENFLAT_GUI_PORT` to
change the listening port:

```console
OPENFLAT_DATA_DIRECTORY=/path/to/data OPENFLAT_GUI_PORT=8081 uv run openflat-gui
```

Listing downloads run outside the GUI event loop, keeping the page responsive
while the provider request is in progress. The filesystem remains authoritative;
the GUI does not maintain a separate database or copy of search quest state.
