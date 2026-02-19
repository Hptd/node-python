"""支持拖拽的节点树"""

from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QApplication,
                               QMenu)
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QDrag, QAction
from PySide6.QtCore import QMimeData


class DraggableNodeTree(QTreeWidget):
    # 信号：右键点击自定义节点时发射
    node_right_clicked = Signal(str, QPoint)  # 节点名称, 全局位置
    # 信号：请求删除节点
    node_delete_requested = Signal(str)  # 节点名称

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self._start_pos = None
        self._custom_categories = set()  # 存储自定义分类名称

    def set_custom_categories(self, categories):
        """设置自定义分类列表，用于判断哪些节点可以编辑/删除"""
        self._custom_categories = set(categories)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._start_pos:
            if (event.pos() - self._start_pos).manhattanLength() > QApplication.startDragDistance():
                item = self.currentItem()
                if item and item.data(0, Qt.UserRole):  # 只有叶子节点可拖拽
                    drag = QDrag(self)
                    mime_data = QMimeData()
                    mime_data.setText(item.data(0, Qt.UserRole))
                    drag.setMimeData(mime_data)
                    drag.exec(Qt.CopyAction)
                    return
        super().mouseMoveEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单事件"""
        item = self.itemAt(event.pos())
        if not item:
            return

        # 获取节点名称和父分类
        node_name = item.data(0, Qt.UserRole)
        parent_item = item.parent()

        # 只有叶子节点（有节点名的）才显示菜单
        if node_name and parent_item:
            # 发射信号，让主窗口处理菜单显示
            global_pos = self.mapToGlobal(event.pos())
            self.node_right_clicked.emit(node_name, global_pos)
            return

        super().contextMenuEvent(event)