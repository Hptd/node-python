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
        return super().itemChange(change, value)
