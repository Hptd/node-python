"""端口（链接点）"""

from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QToolTip
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
        self.total = total  # 新增：保存总端口数
        self.connections = []

        # 应用主题颜色
        self.update_theme()

        self.setParentItem(parent_node)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        # 设置端口 Z 值，确保在父节点（特别是循环节点）背景之上，可被点击
        self.setZValue(10)

        # 启用鼠标跟踪以支持悬浮提示
        self.setAcceptHoverEvents(True)

        # 初始设置位置
        self.update_position()

    def update_position(self):
        """更新端口位置，当节点大小改变时调用此方法"""
        node_rect = self.parent_node.rect()
        if self.total > 0:
            spacing = node_rect.height() / (self.total + 1)
            y_pos = spacing * (self.index + 1)
        else:
            y_pos = node_rect.height() / 2  # 如果没有端口，将端口放在中间（理论上不会发生）

        if self.port_type == 'input':
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
            view = self.scene().views()[0]
            view.start_connection(self)
        elif self.port_type == 'input' and self.connections:
            for conn in self.connections[:]:
                conn.remove_connection()
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def hoverEnterEvent(self, event):
        """鼠标进入端口时显示提示"""
        if self.port_type == 'input':
            # 获取参数类型（安全访问）
            param_type = str
            type_name = "any"
            
            # 检查是否是循环节点，提供准确的类型提示
            from .loop_node_item import LoopNodeItem
            
            if isinstance(self.parent_node, LoopNodeItem):
                # 循环节点端口类型映射
                loop_type_map = {
                    '最小值': 'int',
                    '最大值': 'int',
                    '步长': 'int',
                    '列表数据': 'list',
                }
                type_name = loop_type_map.get(self.port_name, 'any')
            elif hasattr(self.parent_node, 'param_types'):
                param_type = self.parent_node.param_types.get(self.port_name, str)
                type_name = getattr(param_type, '__name__', str(param_type))

            # 构建提示文本
            tooltip_text = f"输入：{self.port_name}\n类型：{type_name}"

            # 显示提示
            QToolTip.showText(
                event.screenPos(),
                tooltip_text,
                None
            )
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开端口时隐藏提示"""
        QToolTip.hideText()
        super().hoverLeaveEvent(event)
