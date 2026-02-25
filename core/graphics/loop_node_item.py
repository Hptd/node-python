"""循环嵌套节点 - 作为内置功能节点

提供两种循环类型：
- 区间循环节点：基于整数范围进行循环
- List 循环节点：基于列表数据进行迭代
"""

import re
import json
from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsItem,
    QGraphicsProxyWidget, QLineEdit, QGraphicsTextItem
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter, QPainterPath, QTextDocument, QTextCursor

from utils.theme_manager import theme_manager
from .port_item import PortItem


class LoopNodeItem(QGraphicsRectItem):
    """循环节点基类"""

    # 类级别常量
    HEADER_HEIGHT = 35
    MIN_WIDTH = 180
    MIN_HEIGHT = 100

    # 循环类型
    LOOP_TYPE_RANGE = "range"  # 区间循环
    LOOP_TYPE_LIST = "list"    # 列表循环

    def __init__(self, name="循环", loop_type=LOOP_TYPE_RANGE, x=0, y=0, parent=None):
        super().__init__(parent)

        # 设置位置
        self.setPos(x, y)

        self._loop_name = name
        self._loop_type = loop_type
        self._dragging = False
        self._updating_bounds = False
        self._last_mouse_pos = None
        self._selected_items_initial_pos = {}

        # 循环配置
        self._range_start = 0
        self._range_end = 10
        self._range_step = 1
        self._list_data = '["item1", "item2", "item3"]'

        # 组内节点集合
        self._nodes = set()
        # 循环结果
        self._loop_results = []
        # 当前迭代索引
        self._current_index = -1
        # 总迭代次数
        self._total_iterations = 0

        # 所属的父组
        self._parent_group = None
        
        # 节点 ID（与 SimpleNodeItem 保持一致）
        self.node_id = id(self)

        # 设置图形项属性 - 支持移动、选中
        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(0)

        # 输入输出端口
        self.input_ports = []
        self.output_ports = []

        # 初始化 UI
        self._setup_ui()

        # 应用主题
        self.update_theme()

        # 监听主题变化
        theme_manager.theme_changed.connect(self._on_theme_changed)

        # 创建输入输出端口
        self._create_ports()

    def _setup_ui(self):
        """初始化 UI 组件"""
        self.setRect(0, 0, self.MIN_WIDTH, self.MIN_HEIGHT)

        # 使用 QGraphicsTextItem 显示标题名称（无背景）
        self._name_text = QGraphicsTextItem(self)
        self._name_text.setPlainText(self._loop_name)
        self._name_text.setDefaultTextColor(QColor("#FFFFFF"))
        font = QFont("Arial", 13, QFont.Bold)
        self._name_text.setFont(font)
        self._name_text.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self._name_text.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self._name_text.setTextInteractionFlags(Qt.TextEditorInteraction)
        self._name_text.document().contentsChanged.connect(self._on_name_changed)
        self._name_text.focusOutEvent = self._on_name_focus_out  # 重写失去焦点事件

    def _create_ports(self):
        """创建输入输出端口"""
        if self._loop_type == self.LOOP_TYPE_RANGE:
            # 区间循环：3 个输入端口
            min_port = PortItem(self, 'input', '最小值', 0, 3)
            self.input_ports.append(min_port)
            max_port = PortItem(self, 'input', '最大值', 1, 3)
            self.input_ports.append(max_port)
            step_port = PortItem(self, 'input', '步长', 2, 3)
            self.input_ports.append(step_port)
        else:
            # List 循环：1 个输入端口
            list_port = PortItem(self, 'input', '列表数据', 0, 1)
            self.input_ports.append(list_port)

        # 输出端口：2 个输出端口
        iterator_port = PortItem(self, 'output', '迭代值', 0, 2)
        self.output_ports.append(iterator_port)
        result_port = PortItem(self, 'output', '汇总结果', 1, 2)
        self.output_ports.append(result_port)

    def _on_theme_changed(self, theme_name):
        self.update_theme()

    def update_theme(self):
        """更新主题颜色"""
        node_bg = theme_manager.get_color("node_bg")
        self._bg_color = self._parse_color(node_bg, QColor(60, 60, 60))

        border_color = theme_manager.get_color("node_border")
        self._border_color = QColor(border_color)

        header_bg = theme_manager.get_color("node_header_bg")
        self._header_bg_color = self._parse_color(header_bg, QColor(80, 80, 80))

        header_text = theme_manager.get_color("node_text")
        self._header_text_color = QColor(header_text)

        # 选中状态
        if self.isSelected():
            selected_bg = theme_manager.get_color("node_bg_selected")
            self._bg_color = self._parse_color(selected_bg, QColor(100, 100, 150))
            border_color = theme_manager.get_color("node_border_selected")
            self._border_color = QColor(border_color)

        # 更新名称文本颜色
        self._name_text.setDefaultTextColor(QColor(header_text))

        self.update()

    def _parse_color(self, color_str, default):
        """解析颜色字符串"""
        if color_str.startswith("rgba"):
            match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', color_str)
            if match:
                r, g, b, a = map(int, match.groups())
                return QColor(r, g, b, a)
        elif color_str.startswith("#"):
            return QColor(color_str)
        return default

    @property
    def loop_name(self):
        return self._loop_name

    @loop_name.setter
    def loop_name(self, value):
        self._loop_name = value
        self._name_text.setPlainText(value)

    @property
    def loop_type(self):
        return self._loop_type

    @property
    def nodes(self):
        return list(self._nodes)

    @property
    def range_start(self):
        return self._range_start

    @range_start.setter
    def range_start(self, value):
        """设置区间循环起始值（带验证）"""
        try:
            self._range_start = int(value) if value is not None else 0
        except (ValueError, TypeError):
            print(f"警告：区间循环起始值必须是整数，当前值：{value}")
            self._range_start = 0

    @property
    def range_end(self):
        return self._range_end

    @range_end.setter
    def range_end(self, value):
        """设置区间循环结束值（带验证）"""
        try:
            self._range_end = int(value) if value is not None else 10
        except (ValueError, TypeError):
            print(f"警告：区间循环结束值必须是整数，当前值：{value}")
            self._range_end = 10

    @property
    def range_step(self):
        return self._range_step

    @range_step.setter
    def range_step(self, value):
        """设置区间循环步长（带验证，自动修正 0 值）"""
        try:
            step_value = int(value) if value is not None else 1
            if step_value == 0:
                print(f"警告：区间循环步长不能为 0，已自动设置为 1")
                step_value = 1
            self._range_step = step_value
        except (ValueError, TypeError):
            print(f"警告：区间循环步长必须是整数，当前值：{value}")
            self._range_step = 1

    @property
    def list_data(self):
        return self._list_data

    @list_data.setter
    def list_data(self, value):
        """设置列表循环数据（带 JSON 验证）"""
        if isinstance(value, list):
            # 如果已经是列表，直接转换为 JSON
            self._list_data = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, str):
            # 验证 JSON 格式
            try:
                json.loads(value)
                self._list_data = value
            except json.JSONDecodeError as e:
                print(f"警告：列表数据 JSON 格式无效：{e}，使用默认值")
                self._list_data = '[]'
        else:
            print(f"警告：列表数据类型无效：{type(value)}，使用默认值")
            self._list_data = '[]'

    @property
    def loop_results(self):
        return self._loop_results

    def get_iterator_values(self):
        """获取迭代器值列表"""
        if self._loop_type == self.LOOP_TYPE_RANGE:
            # 使用属性访问，自动触发验证
            try:
                return list(range(self.range_start, self.range_end, self.range_step))
            except ValueError as e:
                print(f"循环节点 '{self._loop_name}' 参数错误：{e}")
                return []
        else:
            try:
                return json.loads(self._list_data)
            except json.JSONDecodeError as e:
                print(f"循环节点 '{self._loop_name}' 列表数据格式错误：{e}")
                return []
            except Exception as e:
                print(f"循环节点 '{self._loop_name}' 列表数据错误：{e}")
                return []

    def add_node(self, node):
        """添加节点到循环"""
        if node not in self._nodes:
            self._nodes.add(node)
            node._parent_loop = self
            self._update_bounds()

    def remove_node(self, node):
        """从循环中移除节点"""
        if node in self._nodes:
            self._nodes.discard(node)
            if hasattr(node, '_parent_loop'):
                node._parent_loop = None
            if self._nodes:
                self._update_bounds()

    def contains_node(self, node):
        return node in self._nodes

    def _update_bounds(self):
        """更新循环节点边界"""
        if self._updating_bounds:
            return

        self._updating_bounds = True
        try:
            if not self._nodes:
                self.setRect(0, 0, self.MIN_WIDTH, self.MIN_HEIGHT)
                self._update_widget_positions()
                return

            first_node = next(iter(self._nodes))
            rect = first_node.sceneBoundingRect()

            for node in self._nodes:
                rect = rect.united(node.sceneBoundingRect())

            scene_rect = rect
            new_rect = QRectF(
                scene_rect.left() - 20,
                scene_rect.top() - 20 - self.HEADER_HEIGHT,
                scene_rect.width() + 40,
                scene_rect.height() + 40 + self.HEADER_HEIGHT
            )

            new_rect.setWidth(max(new_rect.width(), self.MIN_WIDTH))
            new_rect.setHeight(max(new_rect.height(), self.MIN_HEIGHT))

            self.setPos(new_rect.topLeft())
            self.setRect(0, 0, new_rect.width(), new_rect.height())

            self._update_widget_positions()
        finally:
            self._updating_bounds = False

    def _update_widget_positions(self):
        """更新内部控件位置"""
        rect = self.rect()

        # 名称文本位置（居中，在头部区域内）
        name_width = min(rect.width() - 40, 140)
        name_height = self.HEADER_HEIGHT - 6
        self._name_text.setPos(
            (rect.width() - name_width) / 2,
            4
        )
        self._name_text.setTextWidth(name_width)
        self._name_text.document().setDocumentMargin(2)

    def _on_name_changed(self):
        """名称文本变化时调用"""
        self._loop_name = self._name_text.toPlainText().strip()

    def _on_name_focus_out(self, event):
        """失去焦点时保存名称"""
        self._loop_name = self._name_text.toPlainText().strip()
        # 调用原始的 focusOutEvent
        from PySide6.QtGui import QFocusEvent
        QGraphicsTextItem.focusOutEvent(self._name_text, event)

    def reset_execution_state(self):
        """重置执行状态"""
        self._loop_results = []
        self._current_index = -1
        self._total_iterations = len(self.get_iterator_values())

    def update_iterator_display(self, index):
        """更新迭代器显示"""
        self._current_index = index

    def add_result(self, result):
        """添加循环结果"""
        self._loop_results.append(result)

    def get_aggregated_result(self):
        """获取汇总结果"""
        return self._loop_results

    def paint(self, painter, option, widget):
        """绘制循环节点"""
        rect = self.rect()

        # 根据状态和选中状态决定颜色
        bg_color = self._bg_color
        border_color = self._border_color

        # 应用画刷和画笔
        painter.setBrush(QBrush(bg_color))
        
        # 绘制边框
        border_width = 2 if self.isSelected() else 1
        painter.setPen(QPen(border_color, border_width))
        
        # 绘制圆角矩形背景
        painter.drawRoundedRect(rect, 5, 5)

        # 绘制标题栏背景
        header_rect = QRectF(0, 0, rect.width(), self.HEADER_HEIGHT)
        header_bg = QColor(self._header_bg_color)
        header_bg.setAlpha(80)
        painter.setBrush(QBrush(header_bg))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(header_rect, 5, 5)

        # 重新绘制边框（确保边框在最上层）
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 5, 5)

    def boundingRect(self):
        return self.rect()

    def shape(self):
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 5, 5)
        return path

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
            if hasattr(self, '_parent_group') and self._parent_group and not self._dragging:
                self._parent_group.on_node_moved(self)
        elif change == QGraphicsItem.ItemSceneChange:
            for port in self.input_ports + self.output_ports:
                if hasattr(port, 'update_position'):
                    port.update_position()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            scene_pos = event.scenePos()

            # 检查是否点击在头部（用于开始拖动）
            if self.is_in_header(scene_pos):
                # 点击头部空白区域，开始拖动
                pass

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
                            if isinstance(item, LoopNodeItem):
                                for port in item.input_ports + item.output_ports:
                                    for conn in port.connections:
                                        conn.update_position()
                    if self._parent_group:
                        self._parent_group.on_node_moved(self)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            if self._dragging:
                self._dragging = False
                self._last_mouse_pos = None
                self._selected_items_initial_pos = {}
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击事件"""
        if event.button() == Qt.LeftButton:
            scene_pos = event.scenePos()
            if self.is_in_header(scene_pos):
                # 双击头部区域，让名称文本框获得焦点进行编辑
                self._name_text.setFocus()
                self._name_text.setTextInteractionFlags(Qt.TextEditorInteraction)
                # 全选文本
                cursor = self._name_text.textCursor()
                cursor.select(QTextCursor.Document)
                self._name_text.setTextCursor(cursor)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        """右键菜单"""
        from PySide6.QtWidgets import QMenu
        menu = QMenu()

        delete_action = menu.addAction("删除")

        action = menu.exec(event.screenPos())

        if action == delete_action:
            self._delete_self()

    def _delete_self(self):
        """删除自己"""
        for node in list(self._nodes):
            self.remove_node(node)
        if self.scene():
            self.scene().removeItem(self)

    def is_in_header(self, scene_pos):
        local_pos = self.mapFromScene(scene_pos)
        header_rect = QRectF(0, 0, self.rect().width(), self.HEADER_HEIGHT)
        return header_rect.contains(local_pos)

    def export_to_json(self):
        """导出为 JSON"""
        return {
            "type": "loop",
            "loop_type": self._loop_type,
            "loop_name": self._loop_name,
            "range_start": self._range_start,
            "range_end": self._range_end,
            "range_step": self._range_step,
            "list_data": self._list_data,
            "nodes": [
                {
                    "id": node.node_id,
                    "type": node.name,
                    "x": node.x(),
                    "y": node.y()
                }
                for node in self._nodes
            ]
        }


class RangeLoopNodeItem(LoopNodeItem):
    """区间循环节点"""

    def __init__(self, name="区间循环", x=0, y=0, parent=None):
        super().__init__(name, self.LOOP_TYPE_RANGE, x, y, parent)


class ListLoopNodeItem(LoopNodeItem):
    """List 循环节点"""

    def __init__(self, name="List 循环", x=0, y=0, parent=None):
        super().__init__(name, self.LOOP_TYPE_LIST, x, y, parent)
