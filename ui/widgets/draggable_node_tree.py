"""支持拖拽的节点树"""

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QApplication
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QDrag
from PySide6.QtCore import QMimeData


class DraggableNodeTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self._start_pos = None

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