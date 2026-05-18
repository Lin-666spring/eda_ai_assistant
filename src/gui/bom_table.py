"""
BOM 表格视图组件
显示和编辑 BOM 数据
"""

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class BOMTableView(QWidget):
    """BOM 数据表格视图"""

    COLUMNS = ["位号", "参数值", "封装", "型号", "描述", "数量", "制造商"]
    COLUMN_KEYS = ["reference", "value", "package", "part_number", "description", "quantity", "manufacturer"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)

        # 表格属性
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)

        # 表头样式
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # 位号列自适应
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)  # 描述列自适应
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        # 垂直表头显示行号
        self.table.verticalHeader().setVisible(True)

        # 样式
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                background-color: #ffffff;
                alternate-background-color: #f8f9fa;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #d4e6f1;
                color: #2c3e50;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #2c3e50;
            }
        """)

        layout.addWidget(self.table)

    def load_items(self, items: list):
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            for col, key in enumerate(self.COLUMN_KEYS):
                value = getattr(item, key, "")
                if key == "quantity":
                    self._set_cell(row, col, str(int(value)) if value else "1", align=Qt.AlignCenter)
                else:
                    self._set_cell(row, col, str(value))

        self.table.resizeRowsToContents()

    def _set_cell(
        self, row: int, col: int, text: str, align: int = Qt.AlignLeft | Qt.AlignVCenter
    ):
        """设置单元格内容"""
        item = QTableWidgetItem(text)
        item.setTextAlignment(align)
        self.table.setItem(row, col, item)

    def get_selected_items(self) -> list[int]:
        """获取当前选中的行索引列表"""
        rows = set()
        for index in self.table.selectedIndexes():
            rows.add(index.row())
        return sorted(rows)

    def clear(self):
        """清空表格"""
        self.table.setRowCount(0)
