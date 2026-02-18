"""自定义视图"""

from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QPushButton, QMenu, 
                               QWidgetAction, QLineEdit, QWidget, QApplication)
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QDrag
from PySide6.QtCore import QMimeData

from .simple_node_item import SimpleNodeItem
from .port_item import PortItem
from .connection_item import ConnectionItem
from ..nodes.node_library import LOCAL_NODE_LIBRARY


class SelectionRectItem:
    """框选矩形"""
    def __init__(self):
        from PySide6.QtWidgets import QGraphicsRectItem
        from PySide6.QtGui import QPen, QBrush, QColor
        
        self.item = QGraphicsRectItem()
        self.item.setPen(QPen(QColor("#00BFFF"), 1, Qt.DashLine))
        self.item.setBrush(QBrush(QColor(0, 191, 255, 40)))
        self.item.setZValue(1000)


class NodeGraphicsView(QGraphicsView):
    node_added = Signal(str)

    def __init__(self, scene):
        super().__init__(scene)
        self.temp_connection = None
        self.start_port = None
        self._panning = False
        self._pan_start = QPointF()

        self._selecting = False
        self._select_start = QPointF()
        self._selection_rect_item = None

        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setRenderHint(QPainter.Antialiasing)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSceneRect(-10000, -10000, 20000, 20000)
        self.setAcceptDrops(True)

        self.fit_btn = QPushButton("自适应", self)
        self.fit_btn.setFixedSize(70, 28)
        self.fit_btn.setStyleSheet(
            "QPushButton { background: #4CAF50; color: white; border: none; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #388E3C; }"
        )
        self.fit_btn.clicked.connect(self.fit_all_nodes)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_btn.move(self.width() - self.fit_btn.width() - 10, 10)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() in LOCAL_NODE_LIBRARY:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() in LOCAL_NODE_LIBRARY:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        name = event.mimeData().text()
        if name in LOCAL_NODE_LIBRARY:
            scene_pos = self.mapToScene(event.position().toPoint())
            func = LOCAL_NODE_LIBRARY[name]
            node = SimpleNodeItem(name, func, scene_pos.x(), scene_pos.y())
            self.scene().addItem(node)
            node.setup_ports()
            self.node_added.emit(name)
            print(f"已添加节点: {name}")
            event.acceptProposedAction()
        else:
            event.ignore()

    def wheelEvent(self, event):
        zoom_factor = 1.15
        old_pos = self.mapToScene(event.position().toPoint())
        if event.angleDelta().y() > 0:
            self.scale(zoom_factor, zoom_factor)
        else:
            self.scale(1 / zoom_factor, 1 / zoom_factor)
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(scene_pos, self.transform())
            if isinstance(item, PortItem):
                item = item.parent_node
            if not isinstance(item, SimpleNodeItem):
                self._selecting = True
                self._select_start = scene_pos
                self._selection_rect_item = SelectionRectItem().item
                self.scene().addItem(self._selection_rect_item)
                self.scene().clearSelection()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = self.mapToScene(event.position().toPoint()) - self.mapToScene(self._pan_start.toPoint())
            self._pan_start = event.position()
            self.translate(delta.x(), delta.y())
            event.accept()
            return

        if self._selecting and self._selection_rect_item:
            current_pos = self.mapToScene(event.pos())
            rect = self._selection_rect_item.rect()
            rect.setTopLeft(self._select_start)
            rect.setBottomRight(current_pos)
            rect = rect.normalized()
            self._selection_rect_item.setRect(rect)
            for item in self.scene().items():
                if isinstance(item, SimpleNodeItem):
                    item.setSelected(rect.intersects(item.sceneBoundingRect()))
            event.accept()
            return

        if self.temp_connection:
            scene_pos = self.mapToScene(event.pos())
            self.temp_connection.set_end_point(scene_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton and self._selecting:
            self._selecting = False
            if self._selection_rect_item:
                self.scene().removeItem(self._selection_rect_item)
                self._selection_rect_item = None
            event.accept()
            return

        if self.temp_connection:
            scene_pos = self.mapToScene(event.pos())
            items = self.scene().items(scene_pos)
            end_port = None
            for item in items:
                if isinstance(item, PortItem) and item.port_type == 'input':
                    if item.parent_node != self.start_port.parent_node:
                        end_port = item
                        break
            if end_port and not end_port.connections:
                self.temp_connection.finalize_connection(end_port)
                print(f"已连接: {self.start_port.parent_node.name} -> {end_port.parent_node.name}")
            else:
                self.scene().removeItem(self.temp_connection)
            self.temp_connection = None
            self.start_port = None
        super().mouseReleaseEvent(event)

    def start_connection(self, port):
        self.start_port = port
        self.temp_connection = ConnectionItem(port)
        self.scene().addItem(self.temp_connection)

    def fit_all_nodes(self):
        nodes = [item for item in self.scene().items() if isinstance(item, SimpleNodeItem)]
        if not nodes:
            return
        rect = nodes[0].sceneBoundingRect()
        for node in nodes[1:]:
            rect = rect.united(node.sceneBoundingRect())
        margin = 50
        rect.adjust(-margin, -margin, margin, margin)
        self.fitInView(rect, Qt.KeepAspectRatio)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_nodes()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu, QVBoxLayout, QLabel
        
        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, self.transform())
        if isinstance(item, PortItem):
            item = item.parent_node

        selected_nodes = [i for i in self.scene().selectedItems() if isinstance(i, SimpleNodeItem)]

        if isinstance(item, SimpleNodeItem):
            menu = QMenu(self)
            if len(selected_nodes) > 1 and item.isSelected():
                delete_action = menu.addAction(f"删除 ({len(selected_nodes)}个节点)")
                action = menu.exec(event.globalPos())
                if action == delete_action:
                    for node in selected_nodes:
                        self.delete_node(node)
            else:
                delete_action = menu.addAction("删除")
                action = menu.exec(event.globalPos())
                if action == delete_action:
                    self.delete_node(item)
        else:
            self._show_node_create_menu(event.globalPos(), scene_pos)

    def _show_node_create_menu(self, global_pos, scene_pos):
        from PySide6.QtWidgets import QMenu, QWidget, QVBoxLayout, QLineEdit
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2b2b2b; color: white; padding: 5px; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background: #4CAF50; }
        """)

        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        search_layout.setContentsMargins(5, 5, 5, 5)
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索节点...")
        search_edit.setStyleSheet("background: #3c3c3c; color: white; border: 1px solid #555; padding: 4px; border-radius: 3px;")
        search_edit.setAttribute(Qt.WA_InputMethodEnabled, True)
        search_edit.setFocusPolicy(Qt.StrongFocus)
        search_layout.addWidget(search_edit)
        search_action = QWidgetAction(menu)
        search_action.setDefaultWidget(search_widget)
        menu.addAction(search_action)
        menu.addSeparator()

        node_actions = {}
        for name in LOCAL_NODE_LIBRARY:
            a = menu.addAction(name)
            node_actions[a] = name

        def filter_nodes(text):
            text = text.lower()
            for act, name in node_actions.items():
                act.setVisible(text == "" or text in name.lower())

        search_edit.textChanged.connect(filter_nodes)
        menu.aboutToShow.connect(lambda: search_edit.setFocus(Qt.PopupFocusReason))

        action = menu.exec(global_pos)
        if action in node_actions:
            name = node_actions[action]
            func = LOCAL_NODE_LIBRARY[name]
            node = SimpleNodeItem(name, func, scene_pos.x(), scene_pos.y())
            self.scene().addItem(node)
            node.setup_ports()
            self.node_added.emit(name)
            print(f"已添加节点: {name}")

    def delete_selected_nodes(self):
        selected = [item for item in self.scene().selectedItems() if isinstance(item, SimpleNodeItem)]
        for node in selected:
            self.delete_node(node)

    def delete_node(self, node):
        node.remove_all_connections()
        self.scene().removeItem(node)
        print(f"已删除节点: {node.name}")