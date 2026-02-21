"""端口（链接点）"""

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen

from utils.theme_manager import theme_manager


class PortItem(QGraphicsEllipseItem):
    def __init__(self, parent_node, port_type, port_name, index, total):
        super().__init__(-6, -6, 12, 12)
        self.parent_node = parent_node
        self.port_type = port_type
        self.port_name = port_name
        self.index = index
        self.connections = []

        # 应用主题颜色
        self.update_theme()

        self.setParentItem(parent_node)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

        node_rect = parent_node.rect()
        spacing = node_rect.height() / (total + 1)
        y_pos = spacing * (index + 1)

        if port_type == 'input':
            self.setPos(0, y_pos)
        else:
            self.setPos(node_rect.width(), y_pos)

    def update_theme(self):
        """更新主题颜色"""
        if self.port_type == 'input':
            self.setBrush(QBrush(QColor(theme_manager.get_color("input_port"))))
        else:
            self.setBrush(QBrush(QColor(theme_manager.get_color("output_port"))))
        self.setPen(QPen(QColor(theme_manager.get_color("port_border")), 1))

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