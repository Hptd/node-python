import sys
import json
import inspect
import textwrap
import ast
from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
                               QGraphicsRectItem, QDockWidget, QTextEdit, QListWidget,
                               QToolBar, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QMessageBox,
                               QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsItem,
                               QMenu, QPushButton, QWidgetAction, QLineEdit, QListWidgetItem,
                               QTreeWidget, QTreeWidgetItem, QDialog, QComboBox, QInputDialog,
                               QPlainTextEdit)
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


# ==========================================
# 节点库：分类 -> {节点名: 函数}
# ==========================================
NODE_LIBRARY_CATEGORIZED = {
    "基础运算": {
        "加法节点": node_add,
    },
    "输出": {
        "打印节点": node_print,
    },
    "常量": {
        "数字5": node_number,
        "数字10": node_number2,
    },
}

# 扁平索引，方便查找
LOCAL_NODE_LIBRARY = {}
for cat, nodes in NODE_LIBRARY_CATEGORIZED.items():
    LOCAL_NODE_LIBRARY.update(nodes)

# 用户自定义分类列表
CUSTOM_CATEGORIES = []


def add_node_to_library(name, func, category):
    """将节点添加到分类库和扁平索引"""
    if category not in NODE_LIBRARY_CATEGORIZED:
        NODE_LIBRARY_CATEGORIZED[category] = {}
        if category not in CUSTOM_CATEGORIES:
            CUSTOM_CATEGORIES.append(category)
    NODE_LIBRARY_CATEGORIZED[category][name] = func
    LOCAL_NODE_LIBRARY[name] = func


# ==========================================
# 节点代码验证标准示例
# ==========================================
NODE_CODE_EXAMPLE = '''\
def my_node(a: int, b: int) -> int:
    """
    节点说明文档。
    """
    return a + b

# 规则：
# 1. 必须定义且仅定义一个顶层函数（def）
# 2. 函数名即为节点名
# 3. 参数即为输入端口，带返回类型注解则有输出端口
# 4. 代码必须是合法的 Python 语法
'''


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
        self.port_type = port_type
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
        end_pos = self.end_port.get_center_scene_pos() if self.end_port else start_pos
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
        if return_annotation != inspect.Parameter.empty:
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
# 6.5 支持拖拽的节点树（替代原来的列表）
# ==========================================
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


# ==========================================
# 自定义节点代码编辑对话框
# ==========================================
class CustomNodeCodeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义节点 - 代码编辑器")
        self.resize(600, 500)
        self.generated_func = None
        self.generated_name = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("请输入 Python 节点函数代码："))

        self.code_edit = QPlainTextEdit()
        self.code_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; font-family: Consolas; font-size: 13px;"
        )
        self.code_edit.setPlaceholderText(NODE_CODE_EXAMPLE)
        layout.addWidget(self.code_edit)

        btn_layout = QHBoxLayout()

        paste_btn = QPushButton("粘贴")
        paste_btn.clicked.connect(self._paste)
        btn_layout.addWidget(paste_btn)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self.code_edit.clear)
        btn_layout.addWidget(clear_btn)

        gen_btn = QPushButton("生成节点")
        gen_btn.setStyleSheet("background: #4CAF50; color: white; font-weight: bold;")
        gen_btn.clicked.connect(self._generate_node)
        btn_layout.addWidget(gen_btn)

        layout.addLayout(btn_layout)

    def _paste(self):
        clipboard = QApplication.clipboard()
        self.code_edit.insertPlainText(clipboard.text())

    def _generate_node(self):
        code = self.code_edit.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "错误", "代码不能为空！")
            return

        # 1. 语法检查
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            QMessageBox.critical(
                self, "语法错误",
                f"代码存在语法错误：\n{e}\n\n标准示例：\n{NODE_CODE_EXAMPLE}"
            )
            return

        # 2. 检查是否恰好有一个顶层函数定义
        func_defs = [node for node in ast.iter_child_nodes(tree) if isinstance(node, ast.FunctionDef)]
        if len(func_defs) != 1:
            QMessageBox.critical(
                self, "结构错误",
                f"代码中必须定义且仅定义一个顶层函数（def），当前找到 {len(func_defs)} 个。\n\n标准示例：\n{NODE_CODE_EXAMPLE}"
            )
            return

        func_name = func_defs[0].name

        # 3. 检查是否与已有节点重名
        if func_name in LOCAL_NODE_LIBRARY:
            QMessageBox.critical(self, "命名冲突", f"节点名 '{func_name}' 已存在，请修改函数名。")
            return

        # 4. 编译执行
        try:
            namespace = {}
            exec(compile(tree, "<custom_node>", "exec"), namespace)
            func = namespace[func_name]
        except Exception as e:
            QMessageBox.critical(
                self, "执行错误",
                f"代码执行失败：\n{e}\n\n标准示例：\n{NODE_CODE_EXAMPLE}"
            )
            return

        if not callable(func):
            QMessageBox.critical(self, "错误", "定义的对象不是可调用函数。")
            return

        # 5. 弹出分类选择对话框
        dlg = CategorySelectDialog(self)
        if dlg.exec() == QDialog.Accepted:
            category = dlg.selected_category()
            if not category:
                return
            self.generated_func = func
            self.generated_name = func_name
            # 保存源代码到函数上，以便后续 inspect 可用
            func._custom_source = code
            add_node_to_library(func_name, func, category)
            QMessageBox.information(self, "成功", f"节点 '{func_name}' 已生成到分类 '{category}'！")
            self.accept()


# ==========================================
# 分类选择对话框
# ==========================================
class CategorySelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择节点保存分类")
        self.resize(350, 180)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("选择分类（或新建）："))

        self.combo = QComboBox()
        all_cats = list(NODE_LIBRARY_CATEGORIZED.keys())
        self.combo.addItems(all_cats)
        self.combo.addItem("── 新建分类 ──")
        layout.addWidget(self.combo)

        self.new_cat_edit = QLineEdit()
        self.new_cat_edit.setPlaceholderText("输入新分类名称...")
        self.new_cat_edit.setVisible(False)
        layout.addWidget(self.new_cat_edit)

        self.combo.currentTextChanged.connect(self._on_combo_changed)

        btn_layout = QHBoxLayout()
        gen_btn = QPushButton("生成")
        gen_btn.setStyleSheet("background: #4CAF50; color: white; font-weight: bold;")
        gen_btn.clicked.connect(self._on_accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(gen_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_combo_changed(self, text):
        self.new_cat_edit.setVisible(text == "── 新建分类 ──")

    def _on_accept(self):
        cat = self.selected_category()
        if not cat:
            QMessageBox.warning(self, "提示", "请选择或输入一个分类名称。")
            return
        self.accept()

    def selected_category(self):
        if self.combo.currentText() == "── 新建分类 ──":
            return self.new_cat_edit.text().strip()
        return self.combo.currentText()


# ==========================================
# 7. 自定义视图
# ==========================================
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
                self._selection_rect_item = SelectionRectItem()
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
            rect = QRectF(self._select_start, current_pos).normalized()
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
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        # 管理分类按钮
        cat_btn_layout = QHBoxLayout()
        add_cat_btn = QPushButton("+ 新建分类")
        add_cat_btn.setStyleSheet("background: #2196F3; color: white; border: none; padding: 4px 8px; border-radius: 3px;")
        add_cat_btn.clicked.connect(self._add_custom_category)

        cat_btn_layout.addWidget(add_cat_btn)

        custom_node_btn = QPushButton("+ 自定义节点")
        custom_node_btn.setStyleSheet("background: #FF9800; color: white; border: none; padding: 4px 8px; border-radius: 3px;")
        custom_node_btn.clicked.connect(self._open_custom_node_editor)
        cat_btn_layout.addWidget(custom_node_btn)

        layout.addLayout(cat_btn_layout)

        # 树形节点列表
        self.node_tree = DraggableNodeTree()
        self.node_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        layout.addWidget(self.node_tree)

        dock.setWidget(container)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self._refresh_node_tree()

    def _refresh_node_tree(self):
        self.node_tree.clear()
        for category, nodes in NODE_LIBRARY_CATEGORIZED.items():
            cat_item = QTreeWidgetItem(self.node_tree, [category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsDragEnabled)
            for name in nodes:
                child = QTreeWidgetItem(cat_item, [name])
                child.setData(0, Qt.UserRole, name)  # 存储节点名用于拖拽
            cat_item.setExpanded(True)

    def _on_tree_double_click(self, item, column):
        node_name = item.data(0, Qt.UserRole)
        if node_name and node_name in LOCAL_NODE_LIBRARY:
            func = LOCAL_NODE_LIBRARY[node_name]
            node = SimpleNodeItem(node_name, func, x=0, y=0)
            self.scene.addItem(node)
            node.setup_ports()
            print(f"已添加节点: {node_name}")

    def _add_custom_category(self):
        name, ok = QInputDialog.getText(self, "新建分类", "请输入分类名称：")
        if ok and name.strip():
            name = name.strip()
            if name in NODE_LIBRARY_CATEGORIZED:
                QMessageBox.warning(self, "提示", f"分类 '{name}' 已存在。")
                return
            NODE_LIBRARY_CATEGORIZED[name] = {}
            CUSTOM_CATEGORIES.append(name)
            self._refresh_node_tree()
            print(f"已新建分类: {name}")

    def _open_custom_node_editor(self):
        dlg = CustomNodeCodeDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_node_tree()
            print(f"自定义节点 '{dlg.generated_name}' 已添加到节点库。")

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
            # 自定义节点用保存的源代码
            if hasattr(func, '_custom_source'):
                source = func._custom_source
            else:
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