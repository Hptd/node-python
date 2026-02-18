import sys
import json
import inspect
from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
                               QGraphicsRectItem, QDockWidget, QTextEdit, QListWidget,
                               QToolBar, QVBoxLayout, QWidget, QLabel, QMessageBox,
                               QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsItem,
                               QMenu, QPushButton, QWidgetAction, QLineEdit, QListWidgetItem)
from PySide6.QtCore import Qt, Signal, QObject, QPointF, QRectF, QMimeData
from PySide6.QtGui import QAction, QColor, QFont, QPen, QBrush, QTextCursor, QPainter, QDrag


# ==========================================
# 1. 模拟本地节点的 Python 函数
# ==========================================
def node_add(a: int, b: int) -> int:
    """
    这是一个加法节点。
    输入两个数字，返回它们的和。
    """
    return a + b


def node_print(data):
    """
    打印输出节点。
    将输入的数据打印到下方的控制台中。
    """
    print(f"执行结果: {data}")


def node_number() -> int:
    """
    数字常量节点。
    返回一个固定数字5。
    """
    return 5


def node_number2() -> int:
    """
    数字常量节点2。
    返回一个固定数字10。
    """
    return 10


# 模拟本地库中扫描到的节点字典
LOCAL_NODE_LIBRARY = {
    "加法节点": node_add,
    "打印节点": node_print,
    "数字5": node_number,
    "数字10": node_number2
}


# ==========================================
# 2. 控制台重定向 (用于底部控制台)
# ==========================================
class EmittingStream(QObject):
    textWritten = Signal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

    def flush(self):
        pass


# ==========================================
# 3. 端口（链接点）
# ==========================================
class PortItem(QGraphicsEllipseItem):
    def __init__(self, parent_node, port_type, port_name, index, total):
        super().__init__(-6, -6, 12, 12)
        self.parent_node = parent_node
        self.port_type = port_type  # 'input' or 'output'
        self.port_name = port_name
        self.index = index
        self.connections = []

        if port_type == 'input':
            self.setBrush(QBrush(QColor("#2196F3")))
        else:
            self.setBrush(QBrush(QColor("#FF9800")))

        self.setPen(QPen(Qt.white, 1))
        self.setParentItem(parent_node)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        # 计算位置
        node_rect = parent_node.rect()
        spacing = node_rect.height() / (total + 1)
        y_pos = spacing * (index + 1)

        if port_type == 'input':
            self.setPos(0, y_pos)
        else:
            self.setPos(node_rect.width(), y_pos)

    def get_center_scene_pos(self):
        return self.scenePos()

    def mousePressEvent(self, event):
        if self.port_type == 'output':
            self.scene().views()[0].start_connection(self)
        elif self.port_type == 'input' and self.connections:
            for conn in self.connections[:]:
                conn.remove_connection()
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()


# ==========================================
# 4. 连接线
# ==========================================
class ConnectionItem(QGraphicsLineItem):
    def __init__(self, start_port, end_port=None):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.setPen(QPen(QColor("#FFFFFF"), 2))
        self.setZValue(-1)
        self.update_position()

    def update_position(self):
        start_pos = self.start_port.get_center_scene_pos()
        if self.end_port:
            end_pos = self.end_port.get_center_scene_pos()
        else:
            end_pos = start_pos
        self.setLine(start_pos.x(), start_pos.y(), end_pos.x(), end_pos.y())

    def set_end_point(self, pos):
        start_pos = self.start_port.get_center_scene_pos()
        self.setLine(start_pos.x(), start_pos.y(), pos.x(), pos.y())

    def finalize_connection(self, end_port):
        self.end_port = end_port
        self.start_port.connections.append(self)
        self.end_port.connections.append(self)
        self.update_position()

    def remove_connection(self):
        if self in self.start_port.connections:
            self.start_port.connections.remove(self)
        if self.end_port and self in self.end_port.connections:
            self.end_port.connections.remove(self)
        if self.scene():
            self.scene().removeItem(self)


# ==========================================
# 5. 框选矩形
# ==========================================
class SelectionRectItem(QGraphicsRectItem):
    def __init__(self):
        super().__init__()
        self.setPen(QPen(QColor("#00BFFF"), 1, Qt.DashLine))
        self.setBrush(QBrush(QColor(0, 191, 255, 40)))
        self.setZValue(1000)


# ==========================================
# 6. 自定义图形节点
# ==========================================
class SimpleNodeItem(QGraphicsRectItem):
    def __init__(self, name, func, x=0, y=0):
        super().__init__(0, 0, 120, 50)
        self.setPos(x, y)
        self.setBrush(QColor("#4CAF50"))
        self.setFlags(
            QGraphicsRectItem.ItemIsMovable |
            QGraphicsRectItem.ItemIsSelectable |
            QGraphicsRectItem.ItemSendsGeometryChanges
        )

        self.name = name
        self.func = func
        self.node_id = id(self)

        self.input_ports = []
        self.output_ports = []
        self.result = None

    def setup_ports(self):
        sig = inspect.signature(self.func)
        params = list(sig.parameters.keys())

        for i, param in enumerate(params):
            port = PortItem(self, 'input', param, i, len(params))
            self.input_ports.append(port)

        return_annotation = sig.return_annotation
        if return_annotation != inspect.Parameter.empty or self.name in ["数字5", "数字10", "加法节点"]:
            port = PortItem(self, 'output', 'output', 0, 1)
            self.output_ports.append(port)

    def remove_all_connections(self):
        for port in self.input_ports + self.output_ports:
            for conn in port.connections[:]:
                conn.remove_connection()

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, self.name)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for port in self.input_ports + self.output_ports:
                for conn in port.connections:
                    conn.update_position()
        return super().itemChange(change, value)


# ==========================================
# 6.5 支持拖拽的节点列表
# ==========================================
class DraggableNodeListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
                if item:
                    drag = QDrag(self)
                    mime_data = QMimeData()
                    mime_data.setText(item.text())
                    drag.setMimeData(mime_data)
                    drag.exec(Qt.CopyAction)
                    return
        super().mouseMoveEvent(event)


# ==========================================
# 7. 自定义视图（处理连接拖拽、缩放、平移、框选、拖放）
# ==========================================
class NodeGraphicsView(QGraphicsView):
    node_added = Signal(str)

    def __init__(self, scene):
        super().__init__(scene)
        self.temp_connection = None
        self.start_port = None
        self._panning = False
        self._pan_start = QPointF()

        # 框选相关
        self._selecting = False
        self._select_start = QPointF()
        self._selection_rect_item = None

        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setRenderHint(QPainter.Antialiasing)

        # 禁用滚动条，使用translate实现平移
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 设置足够大的场景范围
        self.setSceneRect(-10000, -10000, 20000, 20000)

        # 启用拖放接收
        self.setAcceptDrops(True)

        # 自适应按钮
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

    # --- 拖放支持 ---
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
        # 中键平移
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # 左键：判断是否点在空白处，用于框选
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(scene_pos, self.transform())
            # 跳过端口，检查是否点在节点上
            if isinstance(item, PortItem):
                item = item.parent_node
            if not isinstance(item, SimpleNodeItem):
                # 空白处：开始框选
                self._selecting = True
                self._select_start = scene_pos
                self._selection_rect_item = SelectionRectItem()
                self.scene().addItem(self._selection_rect_item)
                # 清除之前的选择
                self.scene().clearSelection()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 中键平移：用translate实现无滚动条平移
        if self._panning:
            delta = self.mapToScene(event.position().toPoint()) - self.mapToScene(self._pan_start.toPoint())
            self._pan_start = event.position()
            self.translate(delta.x(), delta.y())
            event.accept()
            return

        # 框选拖动
        if self._selecting and self._selection_rect_item:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self._select_start, current_pos).normalized()
            self._selection_rect_item.setRect(rect)
            # 实时更新选中状态
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

        # 框选结束
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
        rect = QRectF()
        for node in nodes:
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
        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, self.transform())
        if isinstance(item, PortItem):
            item = item.parent_node

        selected_nodes = [i for i in self.scene().selectedItems() if isinstance(i, SimpleNodeItem)]

        if isinstance(item, SimpleNodeItem):
            # 节点上右键
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
            # 空白处右键：弹出节点创建菜单（带搜索）
            self._show_node_create_menu(event.globalPos(), scene_pos)

    def _show_node_create_menu(self, global_pos, scene_pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2b2b2b; color: white; padding: 5px; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background: #4CAF50; }
        """)

        # 搜索框 - 使用独立弹窗方式避免QMenu吞掉输入法事件
        search_widget = QWidget()
        search_layout = QVBoxLayout(search_widget)
        search_layout.setContentsMargins(5, 5, 5, 5)
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索节点...")
        search_edit.setStyleSheet("background: #3c3c3c; color: white; border: 1px solid #555; padding: 4px; border-radius: 3px;")
        # 关键：设置输入法属性，允许中文输入
        search_edit.setAttribute(Qt.WA_InputMethodEnabled, True)
        search_edit.setFocusPolicy(Qt.StrongFocus)
        search_layout.addWidget(search_edit)
        search_action = QWidgetAction(menu)
        search_action.setDefaultWidget(search_widget)
        menu.addAction(search_action)
        menu.addSeparator()

        # 节点列表动作
        node_actions = {}
        for name in LOCAL_NODE_LIBRARY:
            a = menu.addAction(name)
            node_actions[a] = name

        # 搜索过滤
        def filter_nodes(text):
            text = text.lower()
            for act, name in node_actions.items():
                act.setVisible(text == "" or text in name.lower())

        search_edit.textChanged.connect(filter_nodes)

        # 显示菜单后立即让搜索框获取焦点
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


# ==========================================
# 8. 主窗口 UI
# ==========================================
class SimplePyFlowWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("简易中文节点编辑器")
        self.resize(1000, 700)

        self.setup_bottom_dock()

        self.scene = QGraphicsScene()
        self.view = NodeGraphicsView(self.scene)
        self.setCentralWidget(self.view)

        self.scene.selectionChanged.connect(self.on_selection_changed)

        self.setup_toolbar()
        self.setup_left_dock()
        self.setup_right_dock()

    def setup_toolbar(self):
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)

        run_action = QAction("▶ 运行", self)
        run_action.triggered.connect(self.run_graph)
        toolbar.addAction(run_action)

        stop_action = QAction("⏹ 停止", self)
        stop_action.triggered.connect(self.stop_graph)
        toolbar.addAction(stop_action)

        toolbar.addSeparator()

        save_action = QAction("💾 保存为 JSON", self)
        save_action.triggered.connect(self.save_to_json)
        toolbar.addAction(save_action)

    def setup_left_dock(self):
        dock = QDockWidget("📦 本地节点库", self)
        self.node_list = DraggableNodeListWidget()
        for name in LOCAL_NODE_LIBRARY.keys():
            self.node_list.addItem(name)
        self.node_list.itemDoubleClicked.connect(self.add_node_to_scene)
        dock.setWidget(self.node_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def setup_right_dock(self):
        dock = QDockWidget("📝 节点属性", self)
        panel = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(QLabel("节点文档注释:"))
        self.doc_text = QTextEdit()
        self.doc_text.setReadOnly(True)
        layout.addWidget(self.doc_text)

        layout.addWidget(QLabel("节点源代码:"))
        self.source_text = QTextEdit()
        self.source_text.setReadOnly(True)
        self.source_text.setStyleSheet("background-color: #2b2b2b; color: #a9b7c6; font-family: Consolas;")
        layout.addWidget(self.source_text)

        panel.setLayout(layout)
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def setup_bottom_dock(self):
        dock = QDockWidget("💻 运行控制台", self)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #1e1e1e; color: #00FF00; font-family: Consolas;")
        dock.setWidget(self.console)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        self._stream = EmittingStream()
        self._stream.textWritten.connect(self.normal_output)
        sys.stdout = self._stream

    def normal_output(self, text):
        self.console.moveCursor(QTextCursor.End)
        self.console.insertPlainText(text)
        self.console.ensureCursorVisible()

    def add_node_to_scene(self, item):
        name = item.text()
        func = LOCAL_NODE_LIBRARY[name]
        node = SimpleNodeItem(name, func, x=0, y=0)
        self.scene.addItem(node)
        node.setup_ports()
        print(f"已添加节点: {name}")

    def on_selection_changed(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            self.doc_text.clear()
            self.source_text.clear()
            return

        item = selected_items[0]
        if isinstance(item, SimpleNodeItem):
            func = item.func
            doc = inspect.getdoc(func) or "该节点无注释。"
            try:
                source = inspect.getsource(func)
            except Exception:
                source = "无法获取源代码。"

            self.doc_text.setText(doc)
            self.source_text.setText(source)

    def get_all_nodes(self):
        return [item for item in self.scene.items() if isinstance(item, SimpleNodeItem)]

    def topological_sort(self, nodes):
        in_degree = {node: 0 for node in nodes}

        for node in nodes:
            for port in node.input_ports:
                if port.connections:
                    in_degree[node] += 1

        queue = [node for node in nodes if in_degree[node] == 0]
        sorted_nodes = []

        while queue:
            node = queue.pop(0)
            sorted_nodes.append(node)

            for port in node.output_ports:
                for conn in port.connections:
                    if conn.end_port:
                        target_node = conn.end_port.parent_node
                        in_degree[target_node] -= 1
                        if in_degree[target_node] == 0:
                            queue.append(target_node)

        return sorted_nodes

    def run_graph(self):
        print("=" * 40)
        print("开始运行图表...")
        nodes = self.get_all_nodes()

        if not nodes:
            print("没有节点可执行。")
            return

        for node in nodes:
            node.result = None

        sorted_nodes = self.topological_sort(nodes)
        print(f"执行顺序: {[n.name for n in sorted_nodes]}")

        try:
            for node in sorted_nodes:
                args = []
                for port in node.input_ports:
                    if port.connections:
                        conn = port.connections[0]
                        source_node = conn.start_port.parent_node
                        args.append(source_node.result)
                    else:
                        args.append(None)

                if args:
                    node.result = node.func(*args)
                else:
                    node.result = node.func()

            print("运行完成！")
            print("=" * 40)
        except Exception as e:
            print(f"运行出错: {e}")
            import traceback
            traceback.print_exc()

    def stop_graph(self):
        print("已发送停止信号。")

    def save_to_json(self):
        graph_data = {"nodes": [], "connections": []}

        for item in self.scene.items():
            if isinstance(item, SimpleNodeItem):
                graph_data["nodes"].append({
                    "id": item.node_id,
                    "type": item.name,
                    "x": item.x(),
                    "y": item.y()
                })
            elif isinstance(item, ConnectionItem) and item.end_port:
                graph_data["connections"].append({
                    "from_node": item.start_port.parent_node.node_id,
                    "from_port": item.start_port.port_name,
                    "to_node": item.end_port.parent_node.node_id,
                    "to_port": item.end_port.port_name
                })

        json_str = json.dumps(graph_data, ensure_ascii=False, indent=4)
        print(f"图表已另存为 JSON:\n{json_str}")
        QMessageBox.information(self, "保存成功", "节点数据已序列化！(请查看控制台输出)")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimplePyFlowWindow()
    window.show()
    sys.exit(app.exec())