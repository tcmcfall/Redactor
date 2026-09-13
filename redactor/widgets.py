# SPDX-License-Identifier: GPL-3.0-or-later
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap
from PySide6.QtWidgets import QWidget, QMenu, QDialog, QVBoxLayout, QTextBrowser, QPushButton, QStyledItemDelegate, QComboBox, QSizePolicy


class Brand(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        from importlib.resources import files
        self.logo = QPixmap()
        self.logo.loadFromData(files('redactor').joinpath('resources/redactor_logo.png').read_bytes())
        self.setMinimumSize(64, 64)
        self.setMaximumHeight(144)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setAccessibleName('Redactor logo')

    def sizeHint(self):
        return QSize(144, 144)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        size = self.logo.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        painter.drawPixmap((self.width()-size.width())//2, (self.height()-size.height())//2,
                           size.width(), size.height(), self.logo)


class TypeDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        from .engine import KINDS
        editor = QComboBox(parent); editor.setEditable(True)
        editor.addItems(list(dict.fromkeys([*KINDS, index.data()])))
        editor.setToolTip('Choose a type or enter a custom type. Applies to selected values.')
        return editor

    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data())

    def setModelData(self, editor, model, index):
        value = editor.currentText().strip()
        if value: model.setData(index, value, Qt.ItemDataRole.EditRole)


class ColumnFilters:
    """Header right-click menus filter values independently; selection stays explicit."""
    def __init__(self, table, extra_actions=None, sorter=None):
        self.table, self.allowed = table, {}
        self.extra_actions, self.sorter = extra_actions, sorter or table.sortItems
        header = table.horizontalHeader()
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.menu)
        header.setToolTip('Click to sort where enabled. Right-click a column header to filter its values.')

    def apply(self):
        for row in range(self.table.rowCount()):
            hidden = any(self.table.item(row, col) and self.table.item(row, col).text() not in choices
                         for col, choices in self.allowed.items())
            self.table.setRowHidden(row, hidden)
            if hidden:
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item: item.setSelected(False)

    def menu(self, pos):
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        if col < 0: return
        menu = QMenu(self.table)
        menu.addAction("Sort ascending", lambda: self.sorter(col, Qt.SortOrder.AscendingOrder))
        menu.addAction("Sort descending", lambda: self.sorter(col, Qt.SortOrder.DescendingOrder))
        if self.extra_actions: self.extra_actions(menu, col)
        menu.addSeparator()
        menu.addAction('Clear all filters', self.clear)
        menu.addAction('Show all in this column', lambda: self.set_values(col, None))
        menu.addAction('Hide all in this column', lambda: self.set_values(col, set()))
        menu.addSeparator()
        values = sorted({self.table.item(row, col).text() for row in range(self.table.rowCount()) if self.table.item(row, col)})
        for value in values:
            action = menu.addAction(value.replace('&', '&&')[:160])
            action.setCheckable(True)
            action.setChecked(col not in self.allowed or value in self.allowed[col])
            action.toggled.connect(lambda checked, v=value: self.toggle(col, v, checked, values))
        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def toggle(self, col, value, checked, values):
        allowed = self.allowed.setdefault(col, set(values))
        allowed.add(value) if checked else allowed.discard(value)
        self.apply()

    def set_values(self, col, values):
        if values is None: self.allowed.pop(col, None)
        else: self.allowed[col] = values
        self.apply()

    def clear(self):
        self.allowed.clear(); self.apply()


def document(parent, filename, title=None):
    from importlib.resources import files
    dialog = QDialog(parent)
    dialog.setWindowTitle(title or filename)
    dialog.resize(940, 760)
    layout = QVBoxLayout(dialog)
    viewer = QTextBrowser()
    viewer.setOpenExternalLinks(False)
    viewer.setOpenLinks(False)
    viewer.setMarkdown(files('redactor').joinpath('resources/' + filename).read_text(encoding='utf-8'))
    layout.addWidget(viewer)
    close = QPushButton('Close'); close.setToolTip('Close this guide.'); close.clicked.connect(dialog.accept); layout.addWidget(close)
    dialog.exec()
