# Command palette ordering

How the palette's root list is ordered, what counts as "using" a command, and
where the mechanism lives. User-facing behavior of the list itself:
`docs/COMMAND_PALETTE.md`.

## The rule

Rows are ordered **most-used first**; ties are broken by **recency**
(most-recently-used first among equal counts). Commands never used at all
keep their `build_commands()` definition order, after all used ones.

Typing a filter narrows the list but never re-ranks it — matching rows stay
in most-used order (`FilterListDialog._compute_visible` only removes
non-matching rows, preserving entry order).

The top-ranked enabled row is bolded and preselected when the palette opens.

## What counts as a use

Recorded (each bumps the command's count and moves it to the recency front):

- Choosing a **terminal** command in the palette (it runs and the palette
  closes) — e.g. `quit`.
- Picking a value inside a **submenu** command — counts as a use of the
  *parent* (e.g. picking "18 pt" counts for `Appearance: font size`).
- **Drilling into** an `on_navigate` command — `settings`, every external
  text provider ("Favorite Folders", FastTextSuggester providers),
  `tool.<id>.settings`. Recorded at drill-in, because the pushed level is
  host-owned and the library never learns whether a result was picked;
  backing out with Esc still counts.

Not recorded:

- **Global-hotkey fires.** A hotkey dispatches `Command.run()` directly
  (`fastcommandcenter.py`'s `dispatch`), bypassing the palette — no history.
  Applies to all commands, including text providers opened via
  `navigate_to=`. Deliberate: the ranking reflects what you *pick from the
  list*, which is exactly where ranking helps; a hotkey user doesn't need
  the row near the top.

## Where it lives (repo split)

All ordering mechanics are in the `python-command-palette` library
(`D:\GIT\BenjaminKobjolke\python-command-palette`); this app only consumes
them:

- `command_palette/state.py` — `HistoryState`: persists usage, returns ids
  sorted count-desc / recency-tiebreak from `load()`.
- `command_palette/palette.py` — `root_on_choose` / `_push_submenu` decide
  what records (the three "counts as a use" cases above).
- `command_palette/entries.py` — `order_ids()` + `build_palette_entries()`
  turn the ranked ids into rows, bolding the top enabled one.

FCC contributes nothing but the shared `Store` (one `JsonStore` passed to
`CommandPalette` in `fastcommandcenter.py`), so history persists across
restarts in the same state file as everything else
(`docs/SETTINGS_STORAGE.md`).

## Persisted shape

Under the store's `history` key:

```json
{
  "ids":    ["paste_behaviour", "settings", "quit"],
  "counts": {"paste_behaviour": 12, "settings": 3, "quit": 3}
}
```

- `ids` — recency order, most-recent first, capped at 50 (`MAX_HISTORY`).
  An id evicted by the cap also loses its count (counts stay bounded).
- `counts` — total uses per id. An id present in `ids` with no `counts`
  entry has an implied count of 1.

That implied-1 rule is the migration: pre-counts payloads (`{"ids": [...]}`
only, the old pure-MRU shape) load fine and behave like the old
recency ordering until new uses accumulate real counts. Nothing rewrites the
payload until the next use. Consequence right after upgrading: everything
ties at 1, so the list still looks recency-ordered (quit possibly on top)
until a few picks build up counts.

## Hidden commands

`open_palette` is defined with `is_enabled=lambda: False`
(`palette/commands.py`) — the dialog drops disabled entries from the root
list entirely, so it never appears (or ranks) there, while the shortcut
editor and hotkey dispatch ignore `is_enabled`, keeping it bindable.
