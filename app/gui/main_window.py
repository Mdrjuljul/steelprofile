"""Fenêtre principale : catalogue, aperçu exact, propriétés et export.

L'interface ne calcule aucune géométrie et n'invente aucune valeur : elle
affiche le résultat du moteur (`app.geometry`) et délègue l'écriture des
fichiers à `app.exports`. Un profilé incomplet reste visible dans le catalogue,
marqué comme tel, avec la liste exacte de ce qui manque — et il est refusé à
l'export, jamais complété.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QFont, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.catalog import (
    CATEGORY_LABELS,
    STATUS_LABELS,
    Catalogue,
    ProfileDetail,
    ProfileRow,
    Series,
)
from app.gui.export_dialog import ExportDialog
from app.gui.preview import SectionPreview

ROLE_KIND = int(Qt.ItemDataRole.UserRole) + 1
ROLE_ID = int(Qt.ItemDataRole.UserRole) + 2


def format_number(value: float | None, digits: int = 6) -> str:
    """Nombre compact, sans zéro inutile ; `None` devient un tiret cadratin.

    Les résidus numériques (produit d'inertie d'une section symétrique, angle
    d'un axe principal) valent quelques 10⁻¹⁴ : ils s'affichent `0`, ce qui est
    la valeur exacte attendue, sans maquiller un chiffre significatif.
    """
    if value is None:
        return "—"
    if abs(value) < 1e-9:
        return "0"
    return f"{value:.{digits}g}"


def format_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "—"
    return f"{ratio:.2f} × tol."


class MainWindow(QMainWindow):
    """Fenêtre unique de SteelProfile."""

    def __init__(self, catalogue: Catalogue, db_path: Path,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._catalogue = catalogue
        self._db_path = Path(db_path)
        self._current_id: str | None = None
        self._current_detail: ProfileDetail | None = None
        self._dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128

        self.setWindowTitle("SteelProfile — profilés européens, géométrie exacte")
        self.resize(1320, 820)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(140)
        self._search_timer.timeout.connect(self._rebuild_tree)

        self._build_ui()
        self._build_actions()
        self._rebuild_tree()
        self._update_status()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_catalog_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.addWidget(self._build_info_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([330, 560, 430])
        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())

    def _build_catalog_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 4, 8)

        header = QLabel("Catalogue")
        font = QFont(header.font())
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Rechercher : IPE 200, HEA, 168.3x6…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search_changed)
        self._search.returnPressed.connect(self._commit_search)
        layout.addWidget(self._search)

        self._category = QComboBox()
        self._category.addItem("Toutes les références", None)
        self._category.addItem("Normalisées seulement", "standard")
        self._category.addItem("Commerciales seulement", "commercial")
        self._category.currentIndexChanged.connect(self._rebuild_tree)
        layout.addWidget(self._category)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setAlternatingRowColors(False)
        self._tree.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self._tree, 1)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 8, 4, 8)

        head = QHBoxLayout()
        self._title = QLabel("Aucune sélection")
        title_font = QFont(self._title.font())
        title_font.setBold(True)
        title_font.setPointSizeF(title_font.pointSizeF() * 1.15)
        self._title.setFont(title_font)
        head.addWidget(self._title, 1)

        self._zoom_out = QPushButton("−")
        self._zoom_out.setFixedWidth(28)
        self._zoom_out.setToolTip("Zoom arrière")
        self._zoom_out.clicked.connect(lambda: self._preview.zoom_out())
        self._zoom_in = QPushButton("+")
        self._zoom_in.setFixedWidth(28)
        self._zoom_in.setToolTip("Zoom avant")
        self._zoom_in.clicked.connect(lambda: self._preview.zoom_in())
        self._fit_button = QPushButton("Ajuster")
        self._fit_button.setToolTip("Ajuster à la fenêtre (Ctrl+0)")
        self._fit_button.clicked.connect(lambda: self._preview.fit())
        head.addWidget(self._zoom_out)
        head.addWidget(self._zoom_in)
        head.addWidget(self._fit_button)
        layout.addLayout(head)

        self._subtitle = QLabel("")
        self._subtitle.setWordWrap(True)
        self._subtitle.setTextFormat(Qt.TextFormat.RichText)
        self._subtitle.setStyleSheet("color: palette(mid);")
        layout.addWidget(self._subtitle)

        self._preview = SectionPreview()
        layout.addWidget(self._preview, 1)

        # Action principale, visible en permanence sous l'aperçu : elle suit
        # exactement l'état de l'action « Exporter » du menu.
        self._export_button = QPushButton("Exporter…")
        self._export_button.setToolTip(
            "Exporter le profilé sélectionné (DXF, STEP, STL, OBJ, GLB) — Ctrl+E")
        button_font = QFont(self._export_button.font())
        button_font.setBold(True)
        self._export_button.setFont(button_font)
        self._export_button.setMinimumHeight(34)
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._export)
        layout.addWidget(self._export_button)
        return panel

    def _build_info_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 8, 8, 8)

        self._badges = QLabel("")
        self._badges.setTextFormat(Qt.TextFormat.RichText)
        self._badges.setWordWrap(True)
        layout.addWidget(self._badges)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_dimensions_tab(), "Dimensions")
        self._tabs.addTab(self._build_properties_tab(), "Propriétés")
        self._tabs.addTab(self._build_notes_tab(), "Notes et réserves")
        layout.addWidget(self._tabs, 1)
        return panel

    def _build_dimensions_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        self._dimension_hint = QLabel("")
        self._dimension_hint.setWordWrap(True)
        self._dimension_hint.setStyleSheet("color: palette(mid);")
        layout.addWidget(self._dimension_hint)
        self._dimension_table = self._make_table(
            ["Symbole", "Désignation", "Valeur", "Origine"])
        layout.addWidget(self._dimension_table, 1)
        return page

    def _build_properties_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        self._property_hint = QLabel("")
        self._property_hint.setWordWrap(True)
        self._property_hint.setStyleSheet("color: palette(mid);")
        layout.addWidget(self._property_hint)
        self._property_table = self._make_table(
            ["Grandeur", "Unité", "Calculé", "Publié", "Écart / tol."])
        layout.addWidget(self._property_table, 1)
        return page

    def _build_notes_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        self._notes = QPlainTextEdit()
        self._notes.setReadOnly(True)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSizeF(9.0)
        self._notes.setFont(font)
        layout.addWidget(self._notes, 1)
        return page

    @staticmethod
    def _make_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.horizontalHeader().setSectionResizeMode(
            len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setHighlightSections(False)
        return table

    # ------------------------------------------------------------- actions
    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&Fichier")
        self._export_action = QAction("&Exporter la sélection…", self)
        self._export_action.setShortcut(QKeySequence("Ctrl+E"))
        self._export_action.triggered.connect(self._export)
        self._export_action.setEnabled(False)
        file_menu.addAction(self._export_action)
        file_menu.addSeparator()
        quit_action = QAction("&Quitter", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = self.menuBar().addMenu("&Édition")
        search_action = QAction("&Rechercher", self)
        search_action.setShortcut(QKeySequence.StandardKey.Find)
        search_action.triggered.connect(self._focus_search)
        edit_menu.addAction(search_action)

        view_menu = self.menuBar().addMenu("&Affichage")
        fit_action = QAction("&Ajuster la vue", self)
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(lambda: self._preview.fit())
        view_menu.addAction(fit_action)
        zoom_in = QAction("Zoom &avant", self)
        zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in.triggered.connect(lambda: self._preview.zoom_in())
        view_menu.addAction(zoom_in)
        zoom_out = QAction("Zoom a&rrière", self)
        zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out.triggered.connect(lambda: self._preview.zoom_out())
        view_menu.addAction(zoom_out)
        view_menu.addSeparator()
        self._grid_action = QAction("&Grille", self)
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(True)
        self._grid_action.toggled.connect(self._preview.set_show_grid)
        view_menu.addAction(self._grid_action)
        self._axes_action = QAction("&Axes principaux", self)
        self._axes_action.setCheckable(True)
        self._axes_action.setChecked(True)
        self._axes_action.toggled.connect(self._preview.set_show_axes)
        view_menu.addAction(self._axes_action)

        help_menu = self.menuBar().addMenu("&Aide")
        docs_action = QAction("&Documentation", self)
        docs_action.triggered.connect(self._open_documentation)
        help_menu.addAction(docs_action)
        about_action = QAction("À &propos", self)
        about_action.triggered.connect(self._about)
        help_menu.addAction(about_action)

        toolbar = QToolBar("Export")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.addAction(self._export_action)
        self.addToolBar(toolbar)

    def _set_export_state(self, enabled: bool, label: str = "Exporter…",
                          tooltip: str | None = None) -> None:
        """Le bouton sous l'aperçu et l'action du menu partagent le même état."""
        self._export_action.setEnabled(enabled)
        self._export_button.setEnabled(enabled)
        self._export_button.setText(label)
        self._export_button.setToolTip(
            tooltip if tooltip is not None
            else "Exporter la sélection (DXF, STEP, STL, OBJ, GLB) — Ctrl+E")

    # ------------------------------------------------------------ catalogue
    def _focus_search(self) -> None:
        self._search.setFocus()
        self._search.selectAll()

    def _on_search_changed(self) -> None:
        self._search_timer.start()

    def _commit_search(self) -> None:
        self._search_timer.stop()
        self._rebuild_tree()
        matches = self._catalogue.find(self._search.text(), limit=1)
        if matches:
            self._select_profile(matches[0].profile_id)

    def _rebuild_tree(self) -> None:
        text = self._search.text().strip()
        category = self._category.currentData()
        rows = self._catalogue.profiles(text=text, category=category)
        grouped: dict[str, dict[str, list[ProfileRow]]] = {}
        for row in rows:
            grouped.setdefault(row.family_id, {}).setdefault(row.series_id, []).append(row)
        series_map = self._catalogue.series_by_id()

        self._tree.blockSignals(True)
        self._tree.clear()
        for family in self._catalogue.families():
            by_series = grouped.get(family.family_id)
            if not by_series:
                continue
            count = sum(len(items) for items in by_series.values())
            label = (f"{family.label} — {count} résultat(s)" if text
                     else family.title)
            family_item = QTreeWidgetItem([label])
            family_item.setData(0, ROLE_KIND, "family")
            family_item.setData(0, ROLE_ID, family.family_id)
            self._tree.addTopLevelItem(family_item)

            for series_id, items in by_series.items():
                series = series_map.get(series_id)
                series_label = f"{series_id} — {len(items)}"
                if series is not None and series.is_commercial:
                    series_label += "  · commercial"
                series_item = QTreeWidgetItem([series_label])
                series_item.setData(0, ROLE_KIND, "series")
                series_item.setData(0, ROLE_ID, series_id)
                if series is not None:
                    series_item.setToolTip(0, series.label)
                    if series.is_commercial:
                        series_item.setForeground(0, QBrush(
                            QColor(190, 120, 40) if not self._dark else QColor(226, 168, 94)))
                family_item.addChild(series_item)

                for row in items:
                    if row.is_complete:
                        leaf = QTreeWidgetItem([row.designation])
                        leaf.setToolTip(0, row.profile_id)
                    else:
                        leaf = QTreeWidgetItem([f"{row.designation} — incomplète"])
                        leaf.setForeground(0, QBrush(
                            QColor(160, 120, 60) if not self._dark else QColor(214, 170, 110)))
                        leaf.setToolTip(0, f"{row.profile_id}\nDonnées manquantes : la "
                                           "géométrie n'est pas construite et le profilé "
                                           "est refusé à l'export.")
                    leaf.setData(0, ROLE_KIND, "profile")
                    leaf.setData(0, ROLE_ID, row.profile_id)
                    series_item.addChild(leaf)
                if text:
                    series_item.setExpanded(True)
            family_item.setExpanded(True)

        self._tree.blockSignals(False)
        if self._current_id:
            self._select_profile(self._current_id, quiet=True)
        self._update_status(len(rows))

    def _select_profile(self, profile_id: str, *, quiet: bool = False) -> bool:
        stack = [self._tree.topLevelItem(i) for i in range(self._tree.topLevelItemCount())]
        while stack:
            item = stack.pop()
            if item is None:
                continue
            if (item.data(0, ROLE_KIND) == "profile"
                    and item.data(0, ROLE_ID) == profile_id):
                self._tree.setCurrentItem(item)
                self._tree.scrollToItem(item)
                return True
            stack.extend(item.child(i) for i in range(item.childCount()))
        if not quiet:
            self._current_id = None
        return False

    def select_profile(self, profile_id: str) -> bool:
        """Sélectionne un profilé par son identifiant (utilisé au démarrage)."""
        if self._select_profile(profile_id, quiet=True):
            return True
        # Le profilé peut être masqué par un filtre en cours : on l'efface.
        self._search.clear()
        self._category.setCurrentIndex(0)
        self._rebuild_tree()
        return self._select_profile(profile_id)

    def _on_current_changed(self, current: QTreeWidgetItem | None,
                            previous: QTreeWidgetItem | None) -> None:
        if current is None:
            return
        kind = current.data(0, ROLE_KIND)
        identifier = current.data(0, ROLE_ID)
        if kind == "profile":
            self._show_profile(str(identifier))
        elif kind == "series":
            self._show_series(str(identifier))
        elif kind == "family":
            self._show_family(str(identifier))

    # --------------------------------------------------------------- détails
    def _show_profile(self, profile_id: str) -> None:
        try:
            detail = self._catalogue.detail(profile_id)
        except Exception as exc:  # noqa: BLE001 - l'interface ne doit pas mourir
            QMessageBox.critical(self, "SteelProfile", f"Lecture impossible : {exc}")
            return
        self._current_id = profile_id
        self._current_detail = detail

        self._title.setText(detail.row.designation)
        series = detail.series
        standard = f" · {series.standard_id}" if series.standard_id else ""
        self._subtitle.setText(f"{series.series_id} — {series.label}{standard}")
        self._badges.setText(self._badge_html(detail))

        self._preview.set_section(detail.section, detail.properties_exact)
        if not detail.is_complete:
            self._preview.set_placeholder(
                "Géométrie non constructible : données manquantes\n"
                "Aucune valeur n'est déduite ni inventée")
        else:
            self._preview.set_placeholder("Sélectionnez un profilé dans le catalogue")
        self._fill_dimensions(detail)
        self._fill_properties(detail)
        self._fill_notes(detail)
        self._set_export_state(
            detail.is_complete,
            "Exporter ce profilé…" if detail.is_complete else "Export refusé",
            None if detail.is_complete else
            "Géométrie incomplète : l'export est refusé, aucune valeur n'est inventée.")
        self._update_status()

    def _show_series(self, series_id: str) -> None:
        series = self._catalogue.series_by_id().get(series_id)
        rows = self._catalogue.profiles(series_id=series_id)
        self._current_id = None
        self._current_detail = None
        self._title.setText(series_id if series is None else series.series_id)
        self._subtitle.setText("" if series is None else series.label)
        self._badges.setText(self._series_badge_html(series, rows))
        self._preview.clear()
        self._dimension_table.setRowCount(0)
        self._dimension_hint.setText("Sélectionnez un profilé pour afficher ses dimensions.")
        self._property_table.setRowCount(0)
        self._property_hint.setText("")
        self._notes.setPlainText(self._series_text(series, rows))
        self._set_export_state(any(row.is_complete for row in rows),
                               "Exporter la série…")
        self._tabs.setCurrentIndex(2)
        self._update_status()

    def _show_family(self, family_id: str) -> None:
        family = next((f for f in self._catalogue.families()
                       if f.family_id == family_id), None)
        self._current_id = None
        self._current_detail = None
        self._title.setText("" if family is None else family.label)
        self._subtitle.setText("")
        self._badges.setText("")
        self._preview.clear()
        self._dimension_table.setRowCount(0)
        self._property_table.setRowCount(0)
        self._notes.setPlainText(self._family_text(family_id))
        self._set_export_state(False, "Exporter…")
        self._tabs.setCurrentIndex(2)
        self._update_status()

    def _badge_html(self, detail: ProfileDetail) -> str:
        ok = "#1f6f43" if not self._dark else "#6cc08a"
        warn = "#8a5a12" if not self._dark else "#e0aa5a"
        muted = "#6b6b6b" if not self._dark else "#a8a8a8"
        if detail.series.is_commercial:
            category = (f"<span style='color:{warn}'><b>COMMERCIAL</b> — dimensions "
                        "commerciales, jamais normalisées</span>")
        else:
            category = f"<span style='color:{ok}'><b>NORMALISÉ</b></span>"
        if detail.is_complete:
            status = f"<span style='color:{ok}'><b>constructible</b></span>"
        else:
            status = f"<span style='color:{warn}'><b>géométrie incomplète</b></span>"
        return (f"{category} &nbsp;·&nbsp; {status} &nbsp;·&nbsp; "
                f"<span style='color:{muted}'>verified : false</span>")

    def _series_badge_html(self, series: Series | None, rows: list[ProfileRow]) -> str:
        if series is None:
            return ""
        ok = "#1f6f43" if not self._dark else "#6cc08a"
        warn = "#8a5a12" if not self._dark else "#e0aa5a"
        muted = "#6b6b6b" if not self._dark else "#a8a8a8"
        complete = sum(1 for row in rows if row.is_complete)
        category = (f"<span style='color:{warn}'><b>COMMERCIAL</b></span>"
                    if series.is_commercial else
                    f"<span style='color:{ok}'><b>NORMALISÉ</b></span>")
        return (f"{category} &nbsp;·&nbsp; "
                f"<span style='color:{ok}'><b>{complete}</b></span> constructible(s) "
                f"sur {len(rows)} &nbsp;·&nbsp; "
                f"<span style='color:{muted}'>forme {series.shape_id}</span>")

    # -- tableaux ----------------------------------------------------------
    def _fill_dimensions(self, detail: ProfileDetail) -> None:
        table = self._dimension_table
        table.setRowCount(len(detail.dimensions))
        for row, dimension in enumerate(detail.dimensions):
            symbol = QTableWidgetItem(dimension.param)
            font = QFont(symbol.font())
            font.setItalic(True)
            symbol.setFont(font)
            table.setItem(row, 0, symbol)

            label = QTableWidgetItem(dimension.label)
            table.setItem(row, 1, label)

            value_text = "—" if dimension.value is None else (
                f"{format_number(dimension.value)} {dimension.unit}")
            value = QTableWidgetItem(value_text)
            value.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                   | Qt.AlignmentFlag.AlignVCenter)
            if dimension.value is None:
                value.setForeground(QBrush(QColor(180, 120, 60)))
            table.setItem(row, 2, value)

            origin = QTableWidgetItem(
                "manquant" if dimension.value is None else dimension.origin_label)
            origin.setForeground(QBrush(self.palette().color(QPalette.ColorRole.Mid)))
            table.setItem(row, 3, origin)

        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        missing = [d.param for d in detail.dimensions if d.value is None]
        if missing:
            self._dimension_hint.setText(
                f"<span style='color:#b03a2e'>Paramètres absents : "
                f"{', '.join(missing)}.</span> Aucune valeur n'est déduite ni inventée : "
                "le profilé est refusé à l'export.")
        else:
            from_rules = sum(1 for d in detail.dimensions if d.origin == "series_rule")
            text = "Dimensions lues dans la source."
            if from_rules:
                text += (f" {from_rules} rayon(s) d'angle déduits d'une règle de série "
                         "(EN 10210-2 / EN 10219-2), pas d'un tableau.")
            self._dimension_hint.setText(text)

    def _fill_properties(self, detail: ProfileDetail) -> None:
        table = self._property_table
        lines = detail.properties
        table.setRowCount(len(lines))
        warn_colour = QColor(255, 236, 179) if not self._dark else QColor(90, 66, 20)
        mute_colour = self.palette().color(QPalette.ColorRole.Mid)
        for row, line in enumerate(lines):
            table.setItem(row, 0, QTableWidgetItem(line.label))

            unit = QTableWidgetItem(line.unit)
            unit.setTextAlignment(Qt.AlignmentFlag.AlignHCenter
                                  | Qt.AlignmentFlag.AlignVCenter)
            unit.setForeground(QBrush(mute_colour))
            table.setItem(row, 1, unit)

            computed = QTableWidgetItem(format_number(line.computed))
            computed.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                      | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, 2, computed)

            published = QTableWidgetItem(format_number(line.published))
            published.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                       | Qt.AlignmentFlag.AlignVCenter)
            if line.published is None:
                published.setForeground(QBrush(mute_colour))
            table.setItem(row, 3, published)

            ratio = line.ratio
            if line.published is None:
                deviation = QTableWidgetItem("non publié")
                deviation.setForeground(QBrush(mute_colour))
            else:
                deviation = QTableWidgetItem(format_ratio(ratio))
                deviation.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                           | Qt.AlignmentFlag.AlignVCenter)
                if ratio is not None and ratio > 1.0:
                    for column in range(5):
                        item = table.item(row, column)
                        if item is not None:
                            item.setBackground(QBrush(warn_colour))
                    deviation.setToolTip(
                        "Écart supérieur à la tolérance de comparaison. La valeur "
                        "publiée reste affichée telle quelle : elle n'est pas corrigée.")
            table.setItem(row, 4, deviation)

        table.resizeColumnsToContents()
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        if not lines:
            self._property_hint.setText(
                "Aucune propriété : la géométrie n'est pas constructible.")
            return
        outside = [line for line in lines if line.ratio is not None and line.ratio > 1.0]
        worst = max((line for line in lines if line.ratio is not None),
                    key=lambda line: line.ratio or 0.0, default=None)
        if outside:
            self._property_hint.setText(
                f"<span style='color:#b03a2e'><b>{len(outside)} grandeur(s) hors "
                f"tolérance</b></span> — valeurs publiées conservées, jamais corrigées. "
                "La tolérance est celle de <code>verify</code> "
                f"({'2 × 10⁻³' if detail.series.is_commercial else '10⁻⁵'} relatif).")
        else:
            text = "Valeurs calculées par intégration exacte des contours."
            if worst is not None:
                text += (f" Écart maximal aux valeurs publiées : "
                         f"{worst.ratio:.2f} × tolérance ({worst.label}).")
            text += " Les valeurs publiées ne sont pas indépendantes : elles servent de contrôle."
            self._property_hint.setText(text)

    def _fill_notes(self, detail: ProfileDetail) -> None:
        lines: list[str] = []
        series = detail.series
        lines.append(f"Profilé      : {detail.row.profile_id}")
        lines.append(f"Désignation  : {detail.row.designation}")
        lines.append(f"Série        : {series.series_id} — {series.label}")
        if series.standard_id:
            lines.append(f"Norme citée  : {series.standard_id}")
        if series.commercial_ref:
            lines.append(f"Programme    : {series.commercial_ref}")
        lines.append(f"Catégorie    : {CATEGORY_LABELS.get(series.category, series.category)}")
        lines.append(f"Statut       : {STATUS_LABELS.get(detail.row.status, detail.row.status)}"
                     f" ({detail.row.status})")
        lines.append("Vérifié      : non — aucune copie licite de la norme n'est enregistrée")
        if series.process:
            lines.append(f"Procédé      : {series.process}")
        if series.rule_radii_count:
            lines.append(f"Rayons       : règle de série pour {series.rule_radii_count} "
                         "référence(s) de la série (pas un tableau)")
        if detail.aliases:
            lines.append("Alias        : " + ", ".join(detail.aliases))
        if detail.notes:
            lines.append("")
            lines.append("Notes de catalogue")
            lines.append("------------------")
            for note in detail.notes:
                lines.extend(_wrap(note))
        if detail.issues:
            lines.append("")
            lines.append("Réserves et informations")
            lines.append("-----------------------")
            for issue in detail.issues:
                marker = {"blocking": "[!]", "warning": "[~]", "info": "[i]"}.get(
                    issue.severity, "[-]")
                lines.append(f"{marker} {issue.severity_label} · {issue.code} "
                             f"({issue.scope}: {issue.ref})")
                lines.extend("    " + part for part in _wrap(issue.message))
        if detail.error:
            lines.append("")
            lines.append("Refus de construction")
            lines.append("--------------------")
            lines.extend(_wrap(detail.error))
        self._notes.setPlainText("\n".join(lines))

    def _series_text(self, series: Series | None, rows: list[ProfileRow]) -> str:
        if series is None:
            return ""
        lines = [
            f"Série        : {series.series_id}",
            f"Libellé      : {series.label}",
            f"Famille      : {series.family_id}",
            f"Forme        : {series.shape_id}",
            f"Catégorie    : {CATEGORY_LABELS.get(series.category, series.category)}",
        ]
        if series.standard_id:
            lines.append(f"Norme citée  : {series.standard_id}")
        if series.commercial_ref:
            lines.append(f"Programme    : {series.commercial_ref}")
        if series.process:
            lines.append(f"Procédé      : {series.process}")
        complete = sum(1 for row in rows if row.is_complete)
        lines.append(f"Références   : {len(rows)} dont {complete} constructibles")
        if series.notes:
            lines.append("")
            lines.append("Notes")
            lines.append("-----")
            lines.extend(_wrap(series.notes))
        lines.append("")
        lines.append("Sélectionnez un profilé pour voir ses dimensions, ses propriétés")
        lines.append("calculées et ses réserves.")
        return "\n".join(lines)

    def _family_text(self, family_id: str) -> str:
        family = next((f for f in self._catalogue.families()
                       if f.family_id == family_id), None)
        if family is None:
            return ""
        lines = [
            f"Famille      : {family.label}",
            f"Section §    : {family.spec_section or '—'} du cahier des charges",
            f"Séries       : {family.series_count}",
            f"Références   : {family.profile_count} "
            f"({family.complete_count} constructibles, {family.incomplete_count} incomplètes)",
        ]
        if family.incomplete_count:
            lines.append("")
            lines.append("Les références incomplètes restent visibles et sont refusées à")
            lines.append("l'export : aucune dimension n'est interpolée.")
        return "\n".join(lines)

    # -------------------------------------------------------------- export
    def _export(self) -> None:
        profile_ids, title = self._export_scope()
        if not profile_ids:
            QMessageBox.information(
                self, "Exporter",
                "Sélectionnez un profilé (ou une série) dans le catalogue.")
            return
        dialog = ExportDialog(db_path=self._db_path, profile_ids=profile_ids,
                              title=title, parent=self)
        dialog.exec()

    def _export_scope(self) -> tuple[list[str], str]:
        item = self._tree.currentItem()
        if item is None:
            return [], ""
        kind = item.data(0, ROLE_KIND)
        identifier = item.data(0, ROLE_ID)
        if kind == "profile":
            if self._current_detail is not None and not self._current_detail.is_complete:
                return [str(identifier)], f"Profilé {identifier} — refus attendu"
            return [str(identifier)], f"Profilé {identifier}"
        if kind == "series":
            rows = self._catalogue.profiles(series_id=str(identifier))
            complete = sum(1 for row in rows if row.is_complete)
            title = f"Série {identifier} — {len(rows)} référence(s), {complete} constructible(s)"
            return [row.profile_id for row in rows], title
        return [], ""

    # --------------------------------------------------------------- divers
    def _update_status(self, shown: int | None = None) -> None:
        totals = self._catalogue.totals()
        text = (f"{_count(totals['profiles'])} références · "
                f"{_count(totals['complete'])} constructibles · "
                f"{_count(totals['incomplete'])} incomplètes")
        if shown is not None:
            text += f" · {_count(shown)} affichée(s)"
        if self._current_detail is not None:
            text += f" · {self._current_detail.row.profile_id}"
        self.statusBar().showMessage(text)

    def _open_documentation(self) -> None:
        root = Path(__file__).resolve().parents[2]
        for candidate in (root / "docs" / "gui.md", root / "README.md"):
            if candidate.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(candidate)))
                return
        QMessageBox.information(self, "Documentation",
                                "Aucun fichier de documentation n'a été trouvé.")

    def _about(self) -> None:
        totals = self._catalogue.totals()
        QMessageBox.about(
            self, "À propos de SteelProfile",
            "<h3>SteelProfile</h3>"
            "<p>Géométrie exacte des profilés sidérurgiques européens :<br>"
            "contours fermés de segments et d'arcs de cercle, sans corde ni chanfrein.</p>"
            f"<p>{_count(totals['profiles'])} références, dont "
            f"{_count(totals['complete'])} constructibles.<br>Aucune dimension n'est "
            "interpolée : une donnée absente reste absente et le profilé est refusé.</p>"
            "<p>Exports : DXF et STEP exacts, STL, OBJ, GLB.<br>"
            "Le statut <code>verified</code> reste <code>false</code> : aucune copie "
            "licite des normes n'est enregistrée.</p>"
            "<p>Code sous licence MIT. Données normalisées : Steel Section Database "
            "(MIT). Données commerciales : usage local seulement.</p>"
        )

    # ------------------------------------------------------------ cycle de vie
    def closeEvent(self, event) -> None:  # noqa: N802 - API Qt
        try:
            self._catalogue.close()
        finally:
            super().closeEvent(event)


def _wrap(text: str, width: int = 78) -> list[str]:
    """Découpe un texte de catalogue en lignes lisibles, sans le modifier."""
    return textwrap.wrap(text, width=width, break_long_words=False,
                         break_on_hyphens=False) or [""]


def _count(value: int) -> str:
    """Entier avec séparateur de milliers insécable, à la française (2 238)."""
    return f"{value:,}".replace(",", "\u202f")
