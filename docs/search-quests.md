# Search quests

A search quest is a directory containing a versioned `quest.json` manifest and a
`raw/` directory for manually collected source data:

```text
data/
└── vinohrady-rentals/
    ├── quest.json
    └── raw/
        └── bezrealitky-432912.json
```

## Create and read

```python
from openflat.search_quests import (
    create_search_quest,
    list_search_quests,
    open_search_quest,
)

quest = create_search_quest(
    "Vinohrady rentals",
    description="Manually reviewed long-term rentals",
)

same_quest = open_search_quest("vinohrady-rentals")
all_quests = list_search_quests()
```

The directory slug is generated from the title, so `Vinohrady rentals` becomes
`vinohrady-rentals`. Diacritics are normalized, punctuation becomes a hyphen, and
the result contains lowercase ASCII letters and numbers. Programmatic callers can
pass an explicit `slug=` when a generated slug would be ambiguous. Slugs remain
stable after creation; titles and descriptions are user-facing metadata.

## Update

```python
from openflat.search_quests import SearchQuestUpdate, update_search_quest

quest = update_search_quest(
    quest,
    SearchQuestUpdate(title="Vinohrady and Žižkov rentals"),
)

# Explicitly clear an existing description.
quest = update_search_quest(
    quest,
    SearchQuestUpdate(description=None),
)
```

The slug and creation time are immutable. Manifest updates use an atomic file
replacement.

## Delete

```python
from openflat.search_quests import delete_search_quest

delete_search_quest(quest)
```

Deleting an empty quest removes its directory. A quest containing raw data or
other files is protected; deleting it requires an explicit destructive request:

```python
delete_search_quest(quest, force=True)
```
