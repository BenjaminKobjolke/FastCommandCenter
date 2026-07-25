# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Coding rules source: `D:\GIT\BenjaminKobjolke\claude-code\coding-rules`

## Commands

### Setup & Installation
```bash
# Install dependencies with uv
uv sync --group dev

# Or use the batch file
install.bat
```

### Running the Application
```bash
# Run in the background, no console (recommended)
start.bat

# Or run directly with uv (keeps a console for debugging)
uv run python fastcommandcenter.py
```

### Building Executable
```bash
uv run --group dev pyinstaller --name FastCommandCenter --onefile --windowed fastcommandcenter.py
```

### Tests
```bash
tools\run_tests.bat
# or
uv run pytest tests/ -v
```

## Architecture

FastCommandCenter is a background Windows app with **no main window**. A
system-wide global hotkey (OS-level, fires even when another app is focused)
opens a PySide6 command palette; a system tray icon and the palette's own
"Settings"/"Quit" entries are the only other way to reach the app.

### Key Components

- **`fastcommandcenter.py`**: entry point — builds `QApplication`, wires the
  hotkey manager, palette, tray, and settings dialog, runs `app.exec()`.
- **`core/hotkey_manager.py`**: thin wrapper over `winhotkeys.HotkeyHandler`
  (OS-level `RegisterHotKey`). `start()`/`stop()`/`update_hotkey()`.
- **`core/hotkey_bridge.py`**: a `QObject` with a `Signal`. `winhotkeys`
  invokes its callback on its own background thread; a Qt dialog can only be
  shown on the GUI thread. The bridge's `emit()` crosses that boundary via
  Qt's automatic queued connection.
- **`core/single_instance.py`**: named Win32 mutex guard — a duplicate
  instance would double-register the hotkey and show two tray icons, so a
  second launch just exits.
- **`config/settings_store.py`**: persists the global hotkey chord via the
  palette library's own `JsonStore` (`%APPDATA%\FastCommandCenter\command-palette\state.json`,
  key `global_hotkey`) — separate from the palette's own internal keys
  (`history`, `key_bindings`). Also owns `normalize_chord()`, which converts a
  Qt chord string (`"Ctrl+Alt+P"`) to the lowercase `+`-joined format
  `winhotkeys` expects (`"ctrl+alt+p"`; `Meta` → `win`).
- **`gui/tray.py`**: `QSystemTrayIcon` with Open palette / Settings / Quit.
- **`gui/settings_dialog.py`**: `QKeySequenceEdit`-based dialog to rebind the
  global chord; on save, persists via `SettingsStore` and calls
  `hotkey_manager.update_hotkey()` so the new chord is live immediately.
- **`palette/commands.py`**: `build_commands()` — the palette's command list
  (`settings`, `quit` in v1; more commands land here later).

### Important: the palette library does not do OS-global hotkeys

`python-command-palette`'s own shortcuts (`install_shortcut()`,
`PaletteConfig.open_chord`) are Qt `ApplicationShortcut`s — they only fire
while one of this app's own windows is active. This app never keeps a window
open, so that mechanism is unused here. The actual system-wide hotkey is
`winhotkeys` (`core/hotkey_manager.py`), wired to `palette.open()` through
`core/hotkey_bridge.py`.

## AI Workflow Rules (all languages, always apply)

### Feature / Change Workflow

After a plan is proposed and approved, follow this chain. The DRY gate is a
precondition for implementing, not just an earlier step:

```
plan approved
  → /plan:dry            check approved plan for DRY/consolidation BEFORE code
  → /plan:dry-checked    reload + review the DRY-adjusted plan
  → /convention:check    scan for existing patterns/components to reuse
  ─────────────────────  DRY GATE — must be cleared to proceed
  → restate Definition-of-Done aloud
  → implement
  → /dry:check           post-implementation DRY audit
  → /verify:after-change run tests + code analysis
```

**DRY gate** (do not write a single line until all are true; restate aloud when
starting implementation):
- [ ] `/plan:dry` ran and plan adjusted for any duplication found
- [ ] `/plan:dry-checked` reloaded and confirmed the adjusted plan
- [ ] `/convention:check` found existing utilities/patterns to reuse

The gate survives the implement step: adding a new helper/type/pattern mid-implementation
means stopping and re-clearing the gate.

**Definition of Done** — restate before the first edit:
- [ ] Scope: what changes, what does not
- [ ] Reuse: existing function/component this builds on, with path
- [ ] DRY gate cleared
- [ ] `/dry:check` clean
- [ ] `/verify:after-change` green (tests + analysis)

### Bug-Fix Workflow

Shorter variant, no plan-DRY phase:

```
bugs:fix
  → /verify:after-change
```

### Optional Addons

Addons under `ai_rules_addons/` (e.g. graphify) are opt-in per project — ask the user
before wiring one in. None are wired into this project.

## Common Rules (all languages)

- **Use objects for related values** — bundle multiple related values passed between
  classes/methods into a DTO/Settings/Config object instead of many parameters.
- **No bag-of-keys returns at module boundaries** — public methods crossing a module
  boundary return a typed object (DTO/value object/domain model), never a raw
  string-indexed array. Distinguish "zero or one" (`Thing | None`) from "list"
  (`list[Thing]`), and "not found" (`None`) from "found but empty" (`[]`).
- **Reuse existing models before inventing array shapes** — grep for an existing class
  that already owns the data before creating a new DTO.
- **Tests pin the shape before the refactor** — write a characterization test against
  current behavior before converting a bag-of-keys return to a typed object.
- **Test-Driven Development** — write tests first, confirm they fail, implement, confirm
  they pass. Applies to features and bug fixes.
- **Integration tests** — every project needs integration tests in addition to unit
  tests.
- **Test runner scripts** — `tools/run_tests.bat` (unit) and
  `tools/run_integration_tests.bat` (integration) must exist.
- **Prefer type-safe values** — typed DTOs, enums, generics over stringly-typed values.
- **String constants** — centralize string constants in a dedicated module/class.
- **Reusable tooling** — before building project-specific infra scripts, check the
  matching `*_setup_files/` folder under `coding-rules` for an existing equivalent; if
  none exists, build it in-project, prove it, then contribute it back.
- **README.md is mandatory** — name/description, install/setup, usage examples,
  dependencies.
- **DRY** — extract duplicated logic into reusable functions/classes/modules; use
  constants for repeated values.
- **Derive, don't duplicate** — when one value strictly determines another, pass only
  the determinant and derive the rest instead of threading both through call sites.
- **KISS / YAGNI** — simplest solution that works; no interface for one implementation,
  no factory for one product, no config for a value that never changes; boring over
  clever; deletion over addition.
- **Confirm dependency versions** — ask the user before adding a new package; don't
  assume a version.
- **Centralized error handling** — one error handler, not scattered try/catch; structured
  logging with levels (debug/info/warning/error) and context.
- **Centralized logger, single off switch** — route all logging through one `AppLogger`
  class (`app_logger.py`). Never call `print()` directly for logging. Levels and
  enable/disable live in the logger, not at call sites.
- **Input validation at boundaries** — validate API inputs, user input, file uploads,
  external responses; fail fast with clear messages.
- **Maximum file length — 300 lines** — split files that exceed it (except generated/
  config/test files with many similar cases).
- **Naming conventions** — files `snake_case`; classes `PascalCase`; functions/
  variables `snake_case` (Python); constants `UPPER_SNAKE_CASE`.
- **Comments explain why, not what** — no redundant comments; document non-obvious
  reasoning, workarounds, constraints; keep comments in sync with code.
- **Security baseline** — never commit secrets; escape output; parameterized
  queries/ORM only; validate/sanitize input at boundaries; keep dependencies updated.
- **No hardcoded environment values** — paths, hostnames, ports, URLs come from central
  config with a committed `.example` template, not literals in code.
- **No god classes** — more than 5 public methods, more than 4 constructor
  dependencies, or unrelated responsibilities in one class is a warning sign; split by
  responsibility.
- **Self-describing classes** — when behavior depends on a class's fields (search,
  serialization, display, validation), the class declares those fields itself via a
  contract; never hardcode field lists in consuming code.
- **Inject collaborators, don't fold dependencies in** — prefer constructor-injected
  collaborators over mixins/traits that drag in their own dependency graphs; never
  `new` a service inside a method; collapse config-callback swarms into one value
  object.

## Python Rules (applicable subset — see also `PYTHON_RULES.md` for the full set)

This is a PySide6 desktop app with no web layer, database, or REST API, so the
Jinja2/localization/ORM/API-validation sections of `PYTHON_RULES.md` do not apply here.

- **GUI framework: PySide6** — no deviation; this project follows the rule directly
  (unlike sibling FastLauncher, which is Tkinter for historical reasons).
- **`pyproject.toml` is the single source of truth** — no scattered config files;
  Python version pinned; dependencies via `uv add`; commit `uv.lock`.
- **Lint/format/type-check**: `uv add --dev ruff mypy`; run `ruff check`,
  `ruff format --check`, `mypy`.
- **Type hints on public APIs** — typed parameters and return types on all public
  functions/classes/methods; avoid `Any` except at true I/O boundaries.
- **Tests: pytest, fast and isolated** — unit tests for core logic; no network in unit
  tests; use `MemoryStore()` instead of the real `JsonStore` in tests.
- **`MagicMock(spec=ClassName)`** — always pass `spec=` so mocks validate against the
  real interface instead of silently accepting typos/nonexistent attributes.
- **Structured logging via `AppLogger`** — route all logging through `app_logger.py`;
  never call `print()` directly in application code.
- **Required batch files** — `start.bat` (root, starts the app) and
  `tools/run_tests.bat` (test suite). Both present.
- **Release workflow** — set up via `/release:setup` when releases are needed;
  label format `<version>_<build>`, version from `pyproject.toml`, build counter in
  `build_version.txt`. Not set up yet in v1.

Not applicable to this project (skip): Jinja2 template engine, `python-localization`
i18n, SQLAlchemy ORM, Pydantic API-boundary validation.
