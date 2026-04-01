"""自定义图形节点"""

import inspect
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QVariantAnimation, QRectF
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter, QLinearGradient, QPainterPath

from ..nodes.node_library import LOCAL_NODE_LIBRARY
from .port_item import PortItem
from utils.theme_manager import theme_manager


class SimpleNodeItem(QGraphicsRectItem):
    # 节点状态常量
    STATUS_IDLE = "idle"  # 空闲状态
    STATUS_RUNNING = "running"  # 运行中
    STATUS_SUCCESS = "success"  # 执行成功
    STATUS_ERROR = "error"  # 执行错误
    
    def __init__(self, name, func, x=0, y=0):
        # 计算节点宽度：最小120，根据名称长度动态调整
        from PySide6.QtGui import QFontMetrics
        font = QFont("Arial", 10, QFont.Bold)
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(name) + 20  # 添加20像素边距
        node_width = max(120, text_width)  # 最小宽度为120像素
        node_height = 50  # 初始高度，后续会根据输入端口数量调整
        super().__init__(0, 0, node_width, node_height)
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

        # 组拖拽标记（新增）
        self._in_group_drag = False

        # 检测是否为自定义节点
        self.is_custom_node = hasattr(func, '_custom_source')
        self.source_code = getattr(func, '_custom_source', None)

        # 节点状态管理
        self._status = self.STATUS_IDLE
        self._error_message = ""
        
        # 运行动画相关
        self._animation_timer = None
        self._animation_phase = 0

        # 应用主题颜色
        self.update_theme()

    def setup_ports(self):
        sig = inspect.signature(self.func)
        params = list(sig.parameters.items())
        
        # 存储参数类型信息 {参数名: 类型}
        self.param_types = {}

        # 计算端口数量，确定节点高度
        num_inputs = len(params)
        num_outputs = 0
        if sig.return_annotation != inspect.Parameter.empty:
            num_outputs = 1

        # 根据输入端口数量调整节点高度，每个端口预留一定空间，最小高度为50
        port_height = 25  # 每个端口占用的高度
        min_node_height = 50  # 最小高度
        node_height = max(min_node_height, 40 + num_inputs * port_height)  # 40为标题区高度加上一些边距
        self.setRect(0, 0, self.rect().width(), node_height)

        for i, (param_name, param) in enumerate(params):
            port = PortItem(self, 'input', param_name, i, num_inputs)
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
            port = PortItem(self, 'output', 'output', 0, num_outputs)
            self.output_ports.append(port)

    def remove_all_connections(self):
        for port in self.input_ports + self.output_ports:
            for conn in port.connections[:]:
                conn.remove_connection()

    def update_theme(self):
        """更新主题颜色"""
        bg_color = theme_manager.get_color("node_bg")
        border_color = theme_manager.get_color("node_border")
        
        # 根据状态覆盖颜色
        if self._status == self.STATUS_RUNNING:
            bg_color = theme_manager.get_color("node_running")
            border_color = theme_manager.get_color("node_running_border")
        elif self._status == self.STATUS_ERROR:
            bg_color = theme_manager.get_color("node_error")
            border_color = theme_manager.get_color("node_error_border")
        
        if self.isSelected():
            bg_color = theme_manager.get_color("node_bg_selected")
        
        self.setBrush(QColor(bg_color))
        self.setPen(QPen(QColor(border_color), 2))

    def set_status(self, status: str, error_message: str = ""):
        """设置节点状态
        
        Args:
            status: 节点状态 (STATUS_IDLE, STATUS_RUNNING, STATUS_SUCCESS, STATUS_ERROR)
            error_message: 错误信息（仅在 STATUS_ERROR 时使用）
        """
        self._status = status
        self._error_message = error_message
        
        if status == self.STATUS_RUNNING:
            self._start_running_animation()
        else:
            self._stop_running_animation()
        
        self.update_theme()
        self.update()  # 触发重绘

    def get_status(self) -> str:
        """获取当前节点状态"""
        return self._status

    def get_error_message(self) -> str:
        """获取错误信息"""
        return self._error_message

    def _start_running_animation(self):
        """启动运行动画效果"""
        if self._animation_timer is None:
            self._animation_timer = QTimer()
            self._animation_timer.timeout.connect(self._animate_running)
        self._animation_phase = 0
        self._animation_timer.start(100)  # 每100ms更新一次

    def _stop_running_animation(self):
        """停止运行动画效果"""
        if self._animation_timer:
            self._animation_timer.stop()
            self._animation_timer.deleteLater()
            self._animation_timer = None
        self._animation_phase = 0

    def _animate_running(self):
        """运行动画帧更新"""
        self._animation_phase = (self._animation_phase + 1) % 10
        self.update()  # 触发重绘

    def reset_status(self):
        """重置节点状态为空闲"""
        self.set_status(self.STATUS_IDLE)

    def paint(self, painter, option, widget):
        # 根据状态和选中状态决定颜色
        bg_color = theme_manager.get_color("node_bg")
        border_color = theme_manager.get_color("node_border")
        text_color = QColor(theme_manager.get_color("node_text"))

        # 状态颜色覆盖
        if self._status == self.STATUS_RUNNING:
            bg_color = theme_manager.get_color("node_running")
            border_color = theme_manager.get_color("node_running_border")
        elif self._status == self.STATUS_ERROR:
            bg_color = theme_manager.get_color("node_error")
            border_color = theme_manager.get_color("node_error_border")
            text_color = QColor(theme_manager.get_color("node_error_text"))

        # 选中状态优先
        if self.isSelected():
            bg_color = theme_manager.get_color("node_bg_selected")

        # 绘制圆角矩形背景（2px 圆角）
        corner_radius = 2
        path = QPainterPath()
        path.addRoundedRect(self.rect(), corner_radius, corner_radius)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setBrush(QColor(bg_color))
        painter.setPen(QPen(QColor(border_color), 2))
        painter.drawPath(path)

        # 绘制节点名称
        painter.setPen(text_color)
        painter.setFont(QFont("Arial", 10, QFont.Bold))
        # 使用左对齐，为节点名称留出适当的边距
        margin = 10
        text_rect = self.rect().adjusted(margin, margin, -margin, -margin)
        painter.drawText(text_rect, Qt.AlignCenter, self.name)

        # 运行状态动画效果：边框闪烁
        if self._status == self.STATUS_RUNNING and self._animation_timer:
            # 计算闪烁透明度
            alpha = int(128 + 127 * (0.5 + 0.5 * ((-1) ** self._animation_phase)))
            glow_color = QColor(theme_manager.get_color("node_running_border"))
            glow_color.setAlpha(alpha)
            painter.setPen(QPen(glow_color, 4))
            painter.setBrush(Qt.NoBrush)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(self.rect().adjusted(-2, -2, 2, 2), corner_radius, corner_radius)
            painter.drawPath(glow_path)

        # 错误状态：显示错误标记
        if self._status == self.STATUS_ERROR:
            painter.setPen(QPen(QColor(theme_manager.get_color("node_error_border")), 3))
            painter.setBrush(Qt.NoBrush)
            error_path = QPainterPath()
            error_path.addRoundedRect(self.rect().adjusted(-1, -1, 1, 1), corner_radius, corner_radius)
            painter.drawPath(error_path)

            # 在节点右上角显示错误图标
            painter.setPen(QColor("#FF0000"))
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            error_rect = self.rect()
            painter.drawText(error_rect.right() - 12, error_rect.top() + 12, "⚠")

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
        elif change == QGraphicsItem.ItemSceneChange:
            # 当节点被添加到场景时，确保端口位置正确
            for port in self.input_ports + self.output_ports:
                if hasattr(port, 'update_position'):
                    port.update_position()
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 如果节点属于某个组，且组正在 Header 拖拽中，不处理节点自身拖拽
            if hasattr(self, '_parent_group') and self._parent_group:
                if self._parent_group._header_dragging or self._in_group_drag:
                    # 事件不处理，让组来处理
                    super().mousePressEvent(event)
                    return

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
        # 如果正在参与组拖拽，跳过节点自身的移动逻辑
        if self._in_group_drag:
            super().mouseMoveEvent(event)
            return

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
