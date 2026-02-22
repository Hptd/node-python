"""节点组 - 用于将多个节点组合在一起"""

import re
from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsItem, QGraphicsTextItem,
    QGraphicsProxyWidget, QLineEdit
)
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter, QPainterPath

from utils.theme_manager import theme_manager


class NodeGroup(QGraphicsRectItem):
    """节点组图形项，用于将多个节点组合在一起"""

    # 类级别常量
    HEADER_HEIGHT = 28
    PADDING = 15
    MIN_WIDTH = 150
    MIN_HEIGHT = 100

    def __init__(self, nodes=None, name="组", parent=None):
        super().__init__(parent)
        
        self._nodes = set()  # 组内的节点集合
        self._group_name = name
        self._header_rect = QRectF()
        self._dragging = False
        self._drag_start_pos = QPointF()
        self._last_mouse_pos = QPointF()  # 记录上一次鼠标位置
        self._updating_bounds = False  # 防止递归更新边界
        self._last_pos = QPointF()  # 记录上一次位置
        self._node_initial_positions = {}  # 拖拽时记录节点初始位置
        self._selected_items_initial_pos = {}  # 拖拽时记录所有选中项目的初始位置

        # 设置图形项属性（不使用 ItemIsMovable，改用自定义拖拽）
        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(-10)  # 确保组在节点的下方

        # 初始化 UI
        self._setup_ui()

        # 添加初始节点
        if nodes:
            for node in nodes:
                self.add_node(node)

        # 应用主题
        self.update_theme()
        
        # 监听主题变化
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def _setup_ui(self):
        """初始化 UI 组件"""
        # 初始大小
        self.setRect(0, 0, self.MIN_WIDTH, self.MIN_HEIGHT)

        # 创建标题输入框
        self._name_edit = QLineEdit()
        self._name_edit.setText(self._group_name)
        self._name_edit.setAlignment(Qt.AlignCenter)
        self._name_edit.setAttribute(Qt.WA_TranslucentBackground, True)
        self._name_edit.setFrame(False)
        self._name_edit.setAttribute(Qt.WA_InputMethodEnabled, True)
        # 允许输入框接收所有键盘事件
        self._name_edit.setFocusPolicy(Qt.StrongFocus)
        
        # 名称编辑框代理
        self._name_proxy = QGraphicsProxyWidget(self)
        self._name_proxy.setWidget(self._name_edit)
        self._name_proxy.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self._name_proxy.setFlag(QGraphicsItem.ItemIsFocusable, True)
        # 确保代理可以接收键盘事件
        self._name_proxy.setFocusPolicy(Qt.StrongFocus)

        # 连接信号
        self._name_edit.textChanged.connect(self._on_name_changed)
        self._name_edit.editingFinished.connect(self._on_editing_finished)

    def _on_theme_changed(self, theme_name):
        """主题改变时更新样式"""
        self.update_theme()

    def update_theme(self):
        """更新主题颜色"""
        # 解析组背景颜色
        group_bg = theme_manager.get_color("group_bg")
        self._bg_color = self._parse_color(group_bg, QColor(100, 100, 100, 80))
        
        # 边框颜色
        border_color = theme_manager.get_color("group_border")
        self._border_color = QColor(border_color)
        
        # 标题栏背景色
        header_bg = theme_manager.get_color("group_header_bg")
        self._header_bg_color = self._parse_color(header_bg, QColor(80, 80, 80, 180))
        
        # 标题文字颜色
        header_text = theme_manager.get_color("group_header_text")
        self._header_text_color = QColor(header_text)

        # 更新名称编辑框样式
        self._name_edit.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {header_text};
                border: none;
                font-weight: bold;
                font-size: 12px;
                padding: 2px;
            }}
            QLineEdit:focus {{
                background: rgba(255, 255, 255, 30);
                border-radius: 3px;
            }}
        """)
        
        self.update()

    def _parse_color(self, color_str, default):
        """解析颜色字符串，支持 rgba 格式"""
        if color_str.startswith("rgba"):
            match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', color_str)
            if match:
                r, g, b, a = map(int, match.groups())
                return QColor(r, g, b, a)
        elif color_str.startswith("#"):
            return QColor(color_str)
        return default

    @property
    def group_name(self):
        return self._group_name

    @group_name.setter
    def group_name(self, value):
        self._group_name = value
        self._name_edit.setText(value)

    @property
    def nodes(self):
        return list(self._nodes)

    def add_node(self, node):
        """添加节点到组"""
        if node not in self._nodes:
            self._nodes.add(node)
            node._parent_group = self  # 为节点添加组的引用
            self._update_bounds()

    def remove_node(self, node):
        """从组中移除节点"""
        if node in self._nodes:
            self._nodes.discard(node)
            if hasattr(node, '_parent_group'):
                node._parent_group = None
            if self._nodes:
                self._update_bounds()
            else:
                # 如果组内没有节点了，解散组
                self.disband()

    def contains_node(self, node):
        """检查节点是否在组内"""
        return node in self._nodes

    def _update_bounds(self):
        """更新组边界以包含所有节点"""
        if self._updating_bounds:
            return
            
        self._updating_bounds = True
        try:
            if not self._nodes:
                self.setRect(0, 0, self.MIN_WIDTH, self.MIN_HEIGHT)
                self._update_name_edit_position()
                return

            # 记录当前位置
            old_pos = self.pos()
            
            # 计算所有节点的边界
            first_node = next(iter(self._nodes))
            rect = first_node.sceneBoundingRect()
            
            for node in self._nodes:
                rect = rect.united(node.sceneBoundingRect())

            # 转换到组的坐标系
            scene_rect = rect
            new_rect = QRectF(
                scene_rect.left() - self.PADDING,
                scene_rect.top() - self.PADDING - self.HEADER_HEIGHT,
                scene_rect.width() + 2 * self.PADDING,
                scene_rect.height() + 2 * self.PADDING + self.HEADER_HEIGHT
            )

            # 确保最小尺寸
            new_rect.setWidth(max(new_rect.width(), self.MIN_WIDTH))
            new_rect.setHeight(max(new_rect.height(), self.MIN_HEIGHT))

            # 更新组的位置和大小
            self.setPos(new_rect.topLeft())
            self.setRect(0, 0, new_rect.width(), new_rect.height())

            # 更新标题栏位置
            self._header_rect = QRectF(0, 0, new_rect.width(), self.HEADER_HEIGHT)
            
            # 更新名称编辑框位置
            self._update_name_edit_position()
        finally:
            self._updating_bounds = False

    def _update_name_edit_position(self):
        """更新名称编辑框位置"""
        rect = self.rect()
        name_width = min(rect.width() - 20, 150)
        name_height = 20
        self._name_proxy.setPos(
            (rect.width() - name_width) / 2,
            (self.HEADER_HEIGHT - name_height) / 2
        )
        self._name_edit.setFixedSize(int(name_width), int(name_height))

    def _on_name_changed(self, text):
        """名称改变时调用"""
        self._group_name = text

    def _on_editing_finished(self):
        """名称编辑完成"""
        self._group_name = self._name_edit.text()

    def paint(self, painter, option, widget):
        """绘制组"""
        rect = self.rect()
        
        # 绘制组背景
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect)

        # 绘制标题栏背景
        header_rect = QRectF(0, 0, rect.width(), self.HEADER_HEIGHT)
        painter.setBrush(QBrush(self._header_bg_color))
        painter.drawRect(header_rect)

        # 绘制边框
        border_width = 2 if self.isSelected() else 1
        pen = QPen(self._border_color, border_width)
        if self.isSelected():
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

    def boundingRect(self):
        return self.rect()

    def shape(self):
        """返回组的形状用于碰撞检测"""
        path = QPainterPath()
        path.addRect(self.rect())
        return path

    def itemChange(self, change, value):
        """项目改变时的处理"""
        if change == QGraphicsItem.ItemPositionHasChanged:
            # 记录当前位置用于下次计算偏移
            self._last_pos = value
        elif change == QGraphicsItem.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)

    def _move_nodes_with_group(self, delta):
        """组移动时同步移动内部节点"""
        if self._dragging:
            return  # 防止递归
        
        self._dragging = True
        try:
            for node in self._nodes:
                # 移动节点
                node.setPos(node.pos() + delta)
                # 更新连接线
                for port in node.input_ports + node.output_ports:
                    for conn in port.connections:
                        conn.update_position()
        finally:
            self._dragging = False

    def on_node_moved(self, node):
        """当组内节点移动时更新组边界"""
        if node in self._nodes and not self._dragging:
            self._update_bounds()

    def is_in_header(self, scene_pos):
        """检查场景坐标是否在标题栏内"""
        local_pos = self.mapFromScene(scene_pos)
        return self._header_rect.contains(local_pos)

    def is_in_content_area(self, scene_pos):
        """检查场景坐标是否在内容区域（非标题栏）"""
        local_pos = self.mapFromScene(scene_pos)
        content_rect = QRectF(
            0, 
            self.HEADER_HEIGHT, 
            self.rect().width(), 
            self.rect().height() - self.HEADER_HEIGHT
        )
        return content_rect.contains(local_pos)

    def disband(self):
        """解散组"""
        # 清除节点的组引用
        for node in list(self._nodes):
            if hasattr(node, '_parent_group'):
                node._parent_group = None
        self._nodes.clear()
        
        # 从场景中移除
        if self.scene():
            self.scene().removeItem(self)
        
        print(f"组 '{self._group_name}' 已解散")

    def export_to_json(self):
        """导出组为 JSON 格式"""
        return {
            "group_name": self._group_name,
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

    def save_group_to_json(self):
        """将组内所有节点保存为JSON文件"""
        from PySide6.QtWidgets import QFileDialog
        import json
        from .connection_item import ConnectionItem
        
        filepath, _ = QFileDialog.getSaveFileName(
            None,
            "组保存为JSON",
            f"{self._group_name}.json",
            "JSON 文件 (*.json)"
        )
        
        if filepath:
            # 构建组内节点的数据
            data = {
                "group_name": self._group_name,
                "nodes": [],
                "connections": []
            }
            
            # 收集组内所有节点
            node_ids = set()
            for node in self._nodes:
                node_ids.add(node.node_id)
                node_data = {
                    "id": node.node_id,
                    "type": node.name,
                    "x": node.x(),  # 使用绝对位置
                    "y": node.y()
                }
                # 保存参数值
                if hasattr(node, 'param_values') and node.param_values:
                    node_data["param_values"] = node.param_values.copy()
                data["nodes"].append(node_data)
            
            # 收集组内节点之间的连接
            scene = self.scene()
            if scene:
                for item in scene.items():
                    if isinstance(item, ConnectionItem):
                        if (hasattr(item, 'start_port') and hasattr(item, 'end_port') and 
                            item.end_port and item.start_port):
                            from_node = item.start_port.parent_node
                            to_node = item.end_port.parent_node
                            # 只保存组内节点之间的连接
                            if from_node.node_id in node_ids and to_node.node_id in node_ids:
                                data["connections"].append({
                                    "from_node": from_node.node_id,
                                    "from_port": item.start_port.port_name,
                                    "to_node": to_node.node_id,
                                    "to_port": item.end_port.port_name
                                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"组 '{self._group_name}' 已保存到: {filepath}")

    def get_context_menu_actions(self):
        """获取组的右键菜单动作列表"""
        return [
            ("解散组", self.disband),
            ("导出当前组为JSON", self._export_group_json)
        ]

    def _export_group_json(self):
        """导出组 JSON 到文件"""
        from PySide6.QtWidgets import QFileDialog
        import json
        
        filepath, _ = QFileDialog.getSaveFileName(
            None,
            "导出组",
            f"{self._group_name}.json",
            "JSON 文件 (*.json)"
        )
        
        if filepath:
            data = self.export_to_json()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"组 '{self._group_name}' 已导出到: {filepath}")

    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件 - 双击名称区域触发重命名"""
        if event.button() == Qt.LeftButton:
            scene_pos = event.scenePos()
            if self.is_in_header(scene_pos):
                # 检查是否双击在名称编辑框区域内
                name_edit_rect = self._name_proxy.sceneBoundingRect()
                if name_edit_rect.contains(scene_pos):
                    # 双击名称区域：触发重命名（让输入框获得焦点并全选）
                    self._name_edit.setFocus()
                    self._name_edit.selectAll()
                    print(f"重命名组: {self._group_name}")
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            # 检查组是否选中，以及是否有其他选中项
            scene = self.scene()
            if scene and self.isSelected():
                selected_items = scene.selectedItems()
                if len(selected_items) > 1:
                    # 开始拖拽多选项目
                    self._dragging = True
                    self._drag_start_pos = self.pos()
                    self._last_mouse_pos = event.scenePos()
                    # 记录所有选中项目的初始位置
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
                    selected_items = scene.selectedItems()
                    
                    # 移动所有选中的项目
                    for item in selected_items:
                        if id(item) in self._selected_items_initial_pos:
                            initial_pos = self._selected_items_initial_pos[id(item)]
                            new_pos = initial_pos + delta
                            item.setPos(new_pos)
                            
                            from .simple_node_item import SimpleNodeItem
                            if isinstance(item, SimpleNodeItem):
                                # 更新节点的连接线
                                for port in item.input_ports + item.output_ports:
                                    for conn in port.connections:
                                        conn.update_position()
                    
                    # 更新组的边界
                    self._update_bounds()
            
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            if self._dragging:
                self._dragging = False
                self._drag_start_pos = QPointF()
                self._last_mouse_pos = QPointF()
                self._selected_items_initial_pos = {}
                event.accept()
                return
        super().mouseReleaseEvent(event)