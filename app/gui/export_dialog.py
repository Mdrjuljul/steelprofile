"""Boîte de dialogue d'export, avec tâche d'arrière-plan.

L'export réutilise exactement `app.exports.cli.export_selection` : l'interface
n'écrit aucun fichier elle-même et n'a pas de règle de nommage à elle. Le
traitement tourne dans un `QThread` qui ouvre sa **propre** connexion SQLite
(une connexion ne traverse pas les threads) ; l'interface reste réactive même
pour une série complète de maillages.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.exports.cli import DEFAULT_LENGTH, DEFAULT_TOLERANCE, FORMATS
from app.exports.cli import build_manifest, export_selection, write_manifest
from app.geometry.build import connect

FORMAT_LABELS: dict[str, str] = {
    "dxf": "DXF — section exacte (polylignes et arcs, R12)",
    "step": "STEP — solide exact (B-REP AP214, plans et cylindres)",
    "stl": "STL — maillage triangulaire fermé",
    "obj": "OBJ - maillage triangulaire (Blender, SketchUp)",
    "glb": "GLB — glTF 2.0 binaire",
}


class ExportWorker(QThread):
    """Exporte une sélection hors du fil d'interface."""

    progressed = Signal(int, int, str)
    succeeded = Signal(list, list, str)
    failed = Signal(str)

    def __init__(self, *, db_path: Path, profile_ids: list[str], out_dir: Path,
                 formats: tuple[str, ...], length: float, tolerance: float,
                 manifest: bool) -> None:
        super().__init__()
        self._db_path = Path(db_path)
        self._profile_ids = list(profile_ids)
        self._out_dir = Path(out_dir)
        self._formats = tuple(formats)
        self._length = length
        self._tolerance = tolerance
        self._manifest = manifest

    def run(self) -> None:  # noqa: D401 - contrat QThread
        try:
            con = connect(self._db_path)
            try:
                entries, failures = export_selection(
                    con=con,
                    profile_ids=self._profile_ids,
                    out_dir=self._out_dir,
                    formats=self._formats,
                    length=self._length,
                    tolerance=self._tolerance,
                    progress=lambda index, total, profile_id: self.progressed.emit(
                        index, total, profile_id),
                )
            finally:
                con.close()
            manifest_path = ""
            if self._manifest:
                manifest = build_manifest(
                    formats=self._formats, length=self._length,
                    tolerance=self._tolerance, entries=entries, failures=failures)
                manifest_path = str(write_manifest(self._out_dir, manifest))
            self.succeeded.emit(entries, failures, manifest_path)
        except Exception as exc:  # noqa: BLE001 - toute erreur doit remonter à l'UI
            self.failed.emit(f"{type(exc).__name__} : {exc}")


class ExportDialog(QDialog):
    """Choix des formats, de la longueur, de la tolérance et du répertoire."""

    def __init__(self, *, db_path: Path, profile_ids: list[str], title: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exporter")
        self.setModal(True)
        self.resize(620, 460)
        self._db_path = Path(db_path)
        self._profile_ids = list(profile_ids)
        self._worker: ExportWorker | None = None
        self._last_directory: Path | None = None
        # `finished` peut être émis alors que le QThread est encore marqué
        # « running ». Détruire l'objet à cet instant fait avorter Qt
        # (`QThread: Destroyed while thread is still running`). On attend donc
        # que le thread soit réellement arrêté avant de relâcher la référence.
        self._release_timer = QTimer(self)
        self._release_timer.setSingleShot(True)
        self._release_timer.timeout.connect(self._release_worker)

        layout = QVBoxLayout(self)
        heading = QLabel(f"<b>{title}</b>")
        heading.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(heading)
        self._scope = QLabel()
        self._scope.setWordWrap(True)
        layout.addWidget(self._scope)

        formats_box = QGroupBox("Formats")
        formats_layout = QVBoxLayout(formats_box)
        self._format_boxes: dict[str, QCheckBox] = {}
        for fmt in FORMATS:
            box = QCheckBox(FORMAT_LABELS[fmt])
            box.setChecked(True)
            box.toggled.connect(self._refresh_state)
            self._format_boxes[fmt] = box
            formats_layout.addWidget(box)
        layout.addWidget(formats_box)

        options = QGroupBox("Géométrie")
        form = QFormLayout(options)
        self._length = QDoubleSpinBox()
        self._length.setRange(1.0, 100_000.0)
        self._length.setDecimals(1)
        self._length.setSuffix(" mm")
        self._length.setValue(DEFAULT_LENGTH)

        self._tolerance = QDoubleSpinBox()
        self._tolerance.setRange(0.001, 10.0)
        self._tolerance.setDecimals(3)
        self._tolerance.setSingleStep(0.01)
        self._tolerance.setSuffix(" mm")
        self._tolerance.setValue(DEFAULT_TOLERANCE)
        self._tolerance.setToolTip(
            "Flèche maximale entre un arc et ses cordes, pour les maillages "
            "uniquement. Le DXF et le STEP restent exacts.")

        form.addRow("Longueur d'extrusion", self._length)
        form.addRow("Tolérance de corde", self._tolerance)
        layout.addWidget(options)

        destination = QGroupBox("Destination")
        destination_layout = QVBoxLayout(destination)
        directory_row = QHBoxLayout()
        self._directory = QLineEdit(str(self._default_directory()))
        self._directory.textChanged.connect(self._refresh_state)
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse)
        directory_row.addWidget(self._directory, 1)
        directory_row.addWidget(browse)
        destination_layout.addLayout(directory_row)
        self._manifest = QCheckBox("Écrire manifest.json (aire, longueur, empreintes SHA-256)")
        self._manifest.setChecked(True)
        destination_layout.addWidget(self._manifest)
        layout.addWidget(destination)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)
        self._result = QLabel()
        self._result.setWordWrap(True)
        self._result.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(self._result)
        layout.addStretch(1)

        self._buttons = QDialogButtonBox()
        self._export_button = QPushButton("Exporter")
        self._export_button.setDefault(True)
        self._export_button.clicked.connect(self._start)
        self._close_button = QPushButton("Fermer")
        self._close_button.clicked.connect(self.reject)
        self._open_button = QPushButton("Ouvrir le dossier")
        self._open_button.clicked.connect(self._open_folder)
        self._open_button.setVisible(False)
        self._buttons.addButton(self._export_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self._buttons.addButton(self._close_button, QDialogButtonBox.ButtonRole.RejectRole)
        self._buttons.addButton(self._open_button, QDialogButtonBox.ButtonRole.ActionRole)
        layout.addWidget(self._buttons)

        self._refresh_state()
        self._update_scope()

    # -- état --------------------------------------------------------------
    def _default_directory(self) -> Path:
        return Path.cwd() / "exports"

    def selected_formats(self) -> tuple[str, ...]:
        return tuple(fmt for fmt, box in self._format_boxes.items() if box.isChecked())

    def _update_scope(self) -> None:
        count = len(self._profile_ids)
        if count == 1:
            text = f"1 profilé : <code>{self._profile_ids[0]}</code>"
        else:
            text = f"{count} profilés sélectionnés"
        self._scope.setText(text)

    def _refresh_state(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        ready = bool(self.selected_formats()) and bool(self._directory.text().strip())
        self._export_button.setEnabled(ready)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Répertoire de destination", self._directory.text() or str(Path.cwd()))
        if chosen:
            self._directory.setText(chosen)

    # -- exécution ---------------------------------------------------------
    def _start(self) -> None:
        formats = self.selected_formats()
        out_dir = Path(self._directory.text().strip())
        if not formats:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        # Un export précédent est terminé : sa référence peut être relâchée.
        self._worker = None
        self._release_timer.stop()
        self._result.clear()
        self._open_button.setVisible(False)
        for widget in (self._length, self._tolerance, self._directory,
                       self._manifest, *self._format_boxes.values()):
            widget.setEnabled(False)
        self._export_button.setEnabled(False)
        self._close_button.setEnabled(False)
        # Ne jamais appeler setWindowFlag() ici : sur une boîte de dialogue
        # modale, cela la masque et fait sortir exec() avant la fin du thread.
        self.show()
        self._progress.setRange(0, max(len(self._profile_ids), 1))
        self._progress.setValue(0)
        self._progress.setVisible(True)

        self._worker = ExportWorker(
            db_path=self._db_path,
            profile_ids=self._profile_ids,
            out_dir=out_dir,
            formats=formats,
            length=self._length.value(),
            tolerance=self._tolerance.value(),
            manifest=self._manifest.isChecked(),
        )
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, index: int, total: int, profile_id: str) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(index - 1)
        self._progress.setFormat(f"%v / %m — {profile_id}")

    def _on_succeeded(self, entries: list, failures: list, manifest_path: str) -> None:
        self._progress.setValue(self._progress.maximum())
        files = sum(len(entry["files"]) for entry in entries)
        parts = [f"<b>{len(entries)} profilé(s)</b> exporté(s), {files} fichier(s) écrit(s)."]
        if manifest_path:
            parts.append(f"Manifeste : <code>{Path(manifest_path).name}</code>")
        if failures:
            parts.append(
                f"<span style='color:#b6772a'><b>{len(failures)} refusé(s)</b> — "
                "aucune valeur n'a été inventée :</span>")
            for profile_id, message in failures[:8]:
                parts.append(f"<br>· <code>{profile_id}</code> — {message}")
            if len(failures) > 8:
                parts.append(f"<br>· … {len(failures) - 8} autre(s)")
        else:
            parts.append("<br>Le catalogue n'a rien inventé : chaque profilé exporté "
                         "est construit depuis ses dimensions documentées.")
        self._result.setText("<br>".join(parts))
        self._open_button.setVisible(True)
        if entries:
            self._last_directory = Path(manifest_path).parent if manifest_path else None

    def _on_failed(self, message: str) -> None:
        self._result.setText(
            f"<span style='color:#b03a2e'><b>Export interrompu</b></span><br>{message}")

    def _on_finished(self) -> None:
        # Ne pas relâcher `self._worker` ici : voir `_release_worker`.
        self._release_timer.start(0)
        self._progress.setVisible(False)
        for widget in (self._length, self._tolerance, self._directory,
                       self._manifest, *self._format_boxes.values()):
            widget.setEnabled(True)
        self._close_button.setEnabled(True)
        self.show()
        self._refresh_state()

    def _release_worker(self) -> None:
        """Relâche le QThread une fois qu'il n'est plus en cours d'exécution."""
        worker = self._worker
        if worker is None:
            return
        if worker.isRunning():
            self._release_timer.start(50)
            return
        self._worker = None
        self._refresh_state()

    def _open_folder(self) -> None:
        directory = self._last_directory or Path(self._directory.text().strip())
        if directory.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    # -- fermeture ---------------------------------------------------------
    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802 - API Qt
        """Empêche la destruction de la fenêtre pendant un export."""
        if self._worker is not None and self._worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)
