"""
BOM 表格视图组件 — EDA 工业级表格，4主题动态适配。

列结构:  #(行号) | 位号 | 参数值 | 封装 | 型号 | 描述 | 数量 | 制造商
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QHeaderView, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .eda_theme import current_theme, FONT_FAMILY, FONT_SIZE_SM


class BOMTableView(QWidget):
    """BOM 数据表格 — 专业 EDA 工业风格，含行号列."""

    COLUMNS = ["#", "位号", "参数值", "封装", "型号", "描述", "数量", "制造商"]
    COLUMN_KEYS = [
        None, "reference", "value", "package", "part_number",
        "description", "quantity", "manufacturer",
    ]
    # Alignment per column: 0=left, 1=center
    COL_ALIGN = [1, 0, 0, 1, 0, 0, 1, 0]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)

        # Behaviour
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(False)  # disable sort — row# would break
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)

        # Header
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)       # #
        header.setSectionResizeMode(1, QHeaderView.Stretch)     # 位号
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 参数值
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 封装
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 型号
        header.setSectionResizeMode(5, QHeaderView.Stretch)     # 描述
        header.setSectionResizeMode(6, QHeaderView.Fixed)       # 数量
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # 制造商
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setMinimumSectionSize(52)
        header.resizeSection(0, 44)   # row number column
        header.resizeSection(6, 56)   # quantity column
        self.table.setTextElideMode(Qt.ElideNone)

        self._apply_style()
        layout.addWidget(self.table)

    def _apply_style(self):
        t = current_theme()
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: transparent;
                alternate-background-color: {t['table_alt_bg']};
                gridline-color: transparent;
                font-size: {FONT_SIZE_SM};
                border: none; border-radius: 0;
                font-family: {FONT_FAMILY};
            }}
            QTableWidget::item {{
                padding: 7px 12px;
                color: {t['text_primary']};
                border-bottom: 1px solid {t['border']};
            }}
            QTableWidget::item:selected {{
                background-color: {t['primary']};
                color: {t['text_white']};
                border-bottom: 1px solid {t['primary']};
            }}
            QTableWidget::item:hover:!selected {{
                background-color: {t['bg_card_hover']};
            }}
            QHeaderView::section {{
                background-color: {t['bg_card']};
                color: {t['text_secondary']};
                padding: 9px 12px;
                font-weight: 600; font-size: 11px;
                border: none;
                border-right: 1px solid {t['border']};
                border-bottom: 2px solid {t['border']};
            }}
            QHeaderView::section:hover {{
                background-color: {t['bg_card_hover']};
                color: {t['text_primary']};
            }}
            QTableCornerButton::section {{
                background-color: {t['bg_card']};
                border-bottom: 2px solid {t['border']};
            }}
        """)

    def load_items(self, items: list):
        """Load BOM items with auto row numbering."""
        n = len(items)
        self.table.setRowCount(n)

        for row, item in enumerate(items):
            # Column 0: row number
            self._set_cell(row, 0, str(row + 1), Qt.AlignCenter)
            # Columns 1-7: data fields
            for col, key in enumerate(self.COLUMN_KEYS):
                if key is None:
                    continue
                value = getattr(item, key, "")
                if key == "quantity":
                    try:
                        text = str(int(value)) if value is not None and value != "" else "1"
                    except (ValueError, TypeError):
                        text = str(value) if value else "1"
                else:
                    text = str(value) if value else "-"
                align = Qt.AlignCenter if self.COL_ALIGN[col] else (Qt.AlignLeft | Qt.AlignVCenter)
                self._set_cell(row, col, text, align)

        self.table.resizeRowsToContents()

    def _set_cell(self, row: int, col: int, text: str, align: int = Qt.AlignLeft | Qt.AlignVCenter):
        item = QTableWidgetItem(text)
        item.setTextAlignment(align)
        if col == 0:
            item.setForeground(QColor(current_theme()["text_muted"]))
        self.table.setItem(row, col, item)

    def get_selected_items(self) -> list[int]:
        rows = set()
        for index in self.table.selectedIndexes():
            rows.add(index.row())
        return sorted(rows)

    def clear(self):
        self.table.setRowCount(0)

    def refresh_theme(self):
        self._apply_style()
