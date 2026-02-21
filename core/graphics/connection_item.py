"""连接线"""

from PySide6.QtWidgets import QGraphicsLineItem
from PySide6.QtGui import QPen, QColor

from utils.theme_manager import theme_manager


class ConnectionItem(QGraphicsLineItem):
    def __init__(self, start_port, end_port=None):
        super().__init__()
        self.start_port = start_port
        self.end_port = end_port
        self.setZValue(-1)
        # 应用主题颜色
        self.update_theme()
        self.update_position()

    def update_theme(self):
        """更新主题颜色"""
        self.setPen(QPen(QColor(theme_manager.get_color("connection")), 2))

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