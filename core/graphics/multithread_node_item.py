"""多线程处理节点图形类

与循环节点类似，但使用多线程并发执行列表中的每个元素。
"""

import re
import json
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsTextItem
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainterPath, QTextCursor

from utils.theme_manager import theme_manager
from .port_item import PortItem


class MultithreadNodeItem(QGraphicsRectItem):
    """多线程处理节点图形类"""

    HEADER_HEIGHT = 35
    MIN_WIDTH = 200
    MIN_HEIGHT = 110

    def __init__(self, name="多线程处理", x=0, y=0, parent=None):
        super().__init__(parent)
        self.setPos(x, y)

        self._node_name = name
        self._dragging = False
        self._last_mouse_pos = None
        self._selected_items_initial_pos = {}

        # 组拖拽标记（新增）
        self._in_group_drag = False

        # 多线程配置
        self._input_list = '[]'
        self._thread_count = 4
        self._return_order = "按输入顺序"

        # 执行结果
        self._results = []

        # 节点 ID
        self.node_id = id(self)

        # 所属父组
        self._parent_group = None

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(0)

        self.input_ports = []
        self.output_ports = []

        self._setup_ui()
        self.update_theme()
        theme_manager.theme_changed.connect(self._on_theme_changed)
        self._create_ports()

    def _setup_ui(self):
        self.setRect(0, 0, self.MIN_WIDTH, self.MIN_HEIGHT)

        self._name_text = QGraphicsTextItem(self)
        self._name_text.setPlainText(self._node_name)
        self._name_text.setDefaultTextColor(QColor("#FFFFFF"))
        font = QFont("Arial", 13, QFont.Bold)
        self._name_text.setFont(font)
        self._name_text.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self._name_text.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self._name_text.setTextInteractionFlags(Qt.TextEditorInteraction)
        self._name_text.document().contentsChanged.connect(self._on_name_changed)
        self._name_text.focusOutEvent = self._on_name_focus_out

    def _create_ports(self):
        # 3 个输入端口
        self.input_ports.append(PortItem(self, 'input', '输入列表', 0, 3))
        self.input_ports.append(PortItem(self, 'input', '线程数量', 1, 3))
        self.input_ports.append(PortItem(self, 'input', '返回顺序', 2, 3))

        # 2 个输出端口
        self.output_ports.append(PortItem(self, 'output', '迭代值', 0, 2))
        self.output_ports.append(PortItem(self, 'output', '汇总结果', 1, 2))

    def _on_theme_changed(self, theme_name):
        self.update_theme()

    def update_theme(self):
        node_bg = theme_manager.get_color("node_bg")
        self._bg_color = self._parse_color(node_bg, QColor(50, 60, 80))

        border_color = theme_manager.get_color("node_border")
        self._border_color = QColor(border_color)

        header_bg = theme_manager.get_color("node_header_bg")
        self._header_bg_color = self._parse_color(header_bg, QColor(60, 80, 120))

        header_text = theme_manager.get_color("node_text")
        self._header_text_color = QColor(header_text)

        if self.isSelected():
            selected_bg = theme_manager.get_color("node_bg_selected")
            self._bg_color = self._parse_color(selected_bg, QColor(80, 100, 150))
            border_color = theme_manager.get_color("node_border_selected")
            self._border_color = QColor(border_color)

        self._name_text.setDefaultTextColor(QColor(header_text))
        self.update()

    def _parse_color(self, color_str, default):
        if color_str.startswith("rgba"):
            match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', color_str)
            if match:
                r, g, b, a = map(int, match.groups())
                return QColor(r, g, b, a)
        elif color_str.startswith("#"):
            return QColor(color_str)
        return default

    # ---- 属性 ----

    @property
    def node_name(self):
        return self._node_name

    @node_name.setter
    def node_name(self, value):
        self._node_name = value
        self._name_text.setPlainText(value)

    # 兼容 loop_node 接口（loop_name）
    @property
    def loop_name(self):
        return self._node_name

    @property
    def input_list(self):
        return self._input_list

    @input_list.setter
    def input_list(self, value):
        if isinstance(value, list):
            self._input_list = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, str):
            try:
                json.loads(value)
                self._input_list = value
            except json.JSONDecodeError:
                self._input_list = '[]'
        else:
            self._input_list = '[]'

    @property
    def thread_count(self):
        return self._thread_count

    @thread_count.setter
    def thread_count(self, value):
        try:
            v = int(value)
            self._thread_count = max(1, v)
        except (ValueError, TypeError):
            self._thread_count = 4

    @property
    def return_order(self):
        return self._return_order

    @return_order.setter
    def return_order(self, value):
        if value in ("按输入顺序", "按完成顺序"):
            self._return_order = value
        else:
            self._return_order = "按输入顺序"

    # param_values 兼容接口（供属性面板读写）
    @property
    def param_values(self):
        return {
            '输入列表': self._input_list,
            '线程数量': self._thread_count,
            '返回顺序': self._return_order,
        }

    def get_input_list(self):
        try:
            return json.loads(self._input_list)
        except Exception:
            return []

    def get_thread_count(self):
        return self._thread_count

    def get_return_order(self):
        return self._return_order

    # ---- 执行结果 ----

    def reset_execution_state(self):
        self._results = []

    def add_result(self, result):
        self._results.append(result)

    def get_aggregated_result(self):
        return self._results

    # ---- 绘制 ----

    def paint(self, painter, option, widget):
        rect = self.rect()
        bg_color = self._bg_color
        border_color = self._border_color

        painter.setBrush(QBrush(bg_color))
        border_width = 2 if self.isSelected() else 1
        painter.setPen(QPen(border_color, border_width))
        painter.drawRoundedRect(rect, 5, 5)

        # 标题栏（蓝紫色调，区别于循环节点）
        header_rect = QRectF(0, 0, rect.width(), self.HEADER_HEIGHT)
        header_bg = QColor(70, 100, 160)
        header_bg.setAlpha(120)
        painter.setBrush(QBrush(header_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(header_rect, 5, 5)

        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 5, 5)

    def boundingRect(self):
        return self.rect()

    def shape(self):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 5, 5)
        return path

    def _update_widget_positions(self):
        rect = self.rect()
        name_width = min(rect.width() - 40, 160)
        self._name_text.setPos((rect.width() - name_width) / 2, 4)
        self._name_text.setTextWidth(name_width)
        self._name_text.document().setDocumentMargin(2)

    def _on_name_changed(self):
        self._node_name = self._name_text.toPlainText().strip()

    def _on_name_focus_out(self, event):
        self._node_name = self._name_text.toPlainText().strip()
        from PySide6.QtWidgets import QGraphicsTextItem as _QGT
        _QGT.focusOutEvent(self._name_text, event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.update_theme()
            for port in self.input_ports + self.output_ports:
                for conn in port.connections:
                    conn.update_position()
        elif change == QGraphicsItem.ItemPositionHasChanged:
            for port in self.input_ports + self.output_ports:
                for conn in port.connections:
                    conn.update_position()
        elif change == QGraphicsItem.ItemSceneChange:
            for port in self.input_ports + self.output_ports:
                if hasattr(port, 'update_position'):
                    port.update_position()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 如果节点属于某个组，且组正在 Header 拖拽中
            if hasattr(self, '_parent_group') and self._parent_group:
                if self._parent_group._header_dragging or self._in_group_drag:
                    # 不处理，让组来处理
                    super().mousePressEvent(event)
                    return

            # 检查是否有选中的组
            scene = self.scene()
            if scene:
                selected_items = scene.selectedItems()
                from .node_group import NodeGroup
                selected_groups = [item for item in selected_items if isinstance(item, NodeGroup)]

                if selected_groups and self._parent_group in selected_groups:
                    self._dragging = True
                    self._last_mouse_pos = event.scenePos()
                    self._selected_items_initial_pos = {}
                    for item in selected_items:
                        self._selected_items_initial_pos[id(item)] = item.pos()
                    event.accept()
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        # 如果正在参与组拖拽，跳过节点自身的移动逻辑
        if self._in_group_drag:
            super().mouseMoveEvent(event)
            return

        if self._dragging and event.buttons() & Qt.LeftButton:
            delta = event.scenePos() - self._last_mouse_pos
            if not delta.isNull():
                scene = self.scene()
                if scene:
                    from .node_group import NodeGroup
                    selected_items = scene.selectedItems()
                    for item in selected_items:
                        if id(item) in self._selected_items_initial_pos:
                            initial_pos = self._selected_items_initial_pos[id(item)]
                            new_pos = initial_pos + delta
                            item.setPos(new_pos)
                            if isinstance(item, MultithreadNodeItem):
                                for port in item.input_ports + item.output_ports:
                                    for conn in port.connections:
                                        conn.update_position()
                    if self._parent_group:
                        self._parent_group.on_node_moved(self)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            local_pos = self.mapFromScene(event.scenePos())
            if QRectF(0, 0, self.rect().width(), self.HEADER_HEIGHT).contains(local_pos):
                self._name_text.setFocus()
                self._name_text.setTextInteractionFlags(Qt.TextEditorInteraction)
                cursor = self._name_text.textCursor()
                cursor.select(QTextCursor.Document)
                self._name_text.setTextCursor(cursor)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        delete_action = menu.addAction("删除")
        action = menu.exec(event.screenPos())
        if action == delete_action:
            if self.scene():
                self.scene().removeItem(self)

    def is_in_header(self, scene_pos):
        local_pos = self.mapFromScene(scene_pos)
        return QRectF(0, 0, self.rect().width(), self.HEADER_HEIGHT).contains(local_pos)

    def export_to_json(self):
        return {
            "type": "multithread",
            "node_name": self._node_name,
            "input_list": self._input_list,
            "thread_count": self._thread_count,
            "return_order": self._return_order,
        }
