"""Settings dialog: rebind the OS-global hotkey."""

from __future__ import annotations

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QKeySequenceEdit,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from config.settings_store import SettingsStore, normalize_chord
from core.hotkey_manager import HotkeyManager


class SettingsDialog(QDialog):
    """Lets the user rebind the global hotkey; persists and applies it immediately."""

    def __init__(
        self,
        store: SettingsStore,
        hotkey_manager: HotkeyManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("FastCommandCenter Settings")
        self._store = store
        self._hotkey_manager = hotkey_manager

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Global shortcut to open the command palette:"))

        self._chord_edit = QKeySequenceEdit(QKeySequence(_to_qt_chord(store.get_chord())))
        layout.addWidget(self._chord_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        sequence = self._chord_edit.keySequence()
        if not sequence.isEmpty():
            chord = normalize_chord(sequence.toString())
            self._store.set_chord(chord)
            self._hotkey_manager.update_hotkey(chord)
        self.accept()


def _to_qt_chord(winhotkeys_chord: str) -> str:
    """winhotkeys format ("ctrl+alt+space") -> Qt display format ("Ctrl+Alt+Space")."""
    parts = [part.strip() for part in winhotkeys_chord.split("+") if part.strip()]
    parts = ["Meta" if part == "win" else part.capitalize() for part in parts]
    return "+".join(parts)
