"""自定义图形节点"""

import inspect
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter

from ..nodes.node_library import LOCAL_NODE_LIBRARY
from .port_item import PortItem
from utils.theme_manager import theme_manager


class SimpleNodeItem(QGraphicsRectItem):
    def __init__(self, name, func, x=0, y=0):
        super().__init__(0, 0, 120, 50)
        self.setPos(x, y)
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

        # 存储参数默认值 {参数名: 值}
        self.param_values = {}
        
        # 所属的组（如果有的话）
        self._parent_group = None
        
        # 拖拽相关
        self._dragging = False
        self._last_mouse_pos = None
        self._selected_items_initial_pos = {}

        # 检测是否为自定义节点
        self.is_custom_node = hasattr(func, '_custom_source')
        self.source_code = getattr(func, '_custom_source', None)

        # 应用主题颜色
        self.update_theme()

    def setup_ports(self):
        sig = inspect.signature(self.func)
        params = list(sig.parameters.items())
        
        # 存储参数类型信息 {参数名: 类型}
        self.param_types = {}

        for i, (param_name, param) in enumerate(params):
            port = PortItem(self, 'input', param_name, i, len(params))
            self.input_ports.append(port)
            
            # 解析参数类型
            if param.annotation != inspect.Parameter.empty:
                self.param_types[param_name] = param.annotation
            else:
                self.param_types[param_name] = str  # 默认为字符串类型
            
            # 如果有默认值，存储到 param_values
            if param.default != inspect.Parameter.empty:
                self.param_values[param_name] = param.default

        return_annotation = sig.return_annotation
        if return_annotation != inspect.Parameter.empty:
            port = PortItem(self, 'output', 'output', 0, 1)
            self.output_ports.append(port)

    def remove_all_connections(self):
        for port in self.input_ports + self.output_ports:
            for conn in port.connections[:]:
                conn.remove_connection()

    def update_theme(self):
        """更新主题颜色"""
        if self.isSelected():
            bg_color = theme_manager.get_color("node_bg_selected")
        else:
            bg_color = theme_manager.get_color("node_bg")
        self.setBrush(QColor(bg_color))
        self.setPen(QPen(QColor(theme_manager.get_color("node_border")), 2))

    def paint(self, painter, option, widget):
        # 根据选中状态更新颜色
        if self.isSelected():
            bg_color = theme_manager.get_color("node_bg_selected")
            self.setBrush(QColor(bg_color))
        else:
            bg_color = theme_manager.get_color("node_bg")
            self.setBrush(QColor(bg_color))

        super().paint(painter, option, widget)

        # 使用主题文本颜色
        text_color = QColor(theme_manager.get_color("node_text"))
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, self.name)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            # 选中状态改变时更新主题
            self.update_theme()
        elif change == QGraphicsItem.ItemPositionHasChanged:
            for port in self.input_ports + self.output_ports:
                for conn in port.connections:
                    conn.update_position()
            # 通知所属的组更新边界（仅当不是在拖拽多选项目时）
            if hasattr(self, '_parent_group') and self._parent_group and not self._dragging:
                self._parent_group.on_node_moved(self)
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 检查是否有选中的组和节点
            scene = self.scene()
            if scene:
                selected_items = scene.selectedItems()
                from .node_group import NodeGroup
                selected_groups = [item for item in selected_items if isinstance(item, NodeGroup)]
                
                # 如果有选中的组，且当前节点在某个选中的组内
                if selected_groups and self._parent_group in selected_groups:
                    self._dragging = True
                    self._last_mouse_pos = event.scenePos()
                    # 记录所有选中项目（组和节点）的初始位置
                    self._selected_items_initial_pos = {}
                    for item in selected_items:
                        self._selected_items_initial_pos[id(item)] = item.pos()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._dragging and event.buttons() & Qt.LeftButton:
            # 计算鼠标移动的偏移量
            delta = event.scenePos() - self._last_mouse_pos
            
            if not delta.isNull():
                scene = self.scene()
                if scene:
                    from .node_group import NodeGroup
                    selected_items = scene.selectedItems()
                    
                    # 移动所有选中的项目
                    for item in selected_items:
                        if id(item) in self._selected_items_initial_pos:
                            initial_pos = self._selected_items_initial_pos[id(item)]
                            new_pos = initial_pos + delta
                            item.setPos(new_pos)
                            
                            # 更新连接线
                            if isinstance(item, SimpleNodeItem):
                                for port in item.input_ports + item.output_ports:
                                    for conn in port.connections:
                                        conn.update_position()
                    
                    # 更新组的边界
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
