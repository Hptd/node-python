"""自定义视图"""

from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QPushButton, QMenu, 
                               QWidgetAction, QLineEdit, QWidget, QApplication)
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QDrag
from PySide6.QtCore import QMimeData

from .simple_node_item import SimpleNodeItem
from .port_item import PortItem
from .connection_item import ConnectionItem
from .node_group import NodeGroup
from ..nodes.node_library import LOCAL_NODE_LIBRARY
from utils.theme_manager import theme_manager
from ui.widgets.node_search_menu import NodeSearchMenu


class SelectionRectItem:
    """框选矩形"""
    def __init__(self):
        from PySide6.QtWidgets import QGraphicsRectItem
        from PySide6.QtGui import QPen, QBrush, QColor

        self.item = QGraphicsRectItem()
        # 使用主题颜色
        selection_color = QColor(theme_manager.get_color("selection"))
        self.item.setPen(QPen(selection_color, 1, Qt.DashLine))
        # 解析 RGBA 颜色
        fill_color = theme_manager.get_color("selection_fill")
        if fill_color.startswith("rgba"):
            # 解析 rgba(r, g, b, a) 格式
            import re
            match = re.match(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)', fill_color)
            if match:
                r, g, b, a = map(int, match.groups())
                self.item.setBrush(QBrush(QColor(r, g, b, a)))
        else:
            self.item.setBrush(QBrush(QColor(fill_color)))
        self.item.setZValue(1000)


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
        self._ctrl_selecting = False  # 记录是否为 Ctrl+框选增选模式

        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setRenderHint(QPainter.Antialiasing)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSceneRect(-10000, -10000, 20000, 20000)
        self.setAcceptDrops(True)

        self.fit_btn = QPushButton("自适应", self)
        self.fit_btn.setFixedSize(70, 28)
        self._update_fit_button_style()
        self.fit_btn.clicked.connect(self.fit_all_nodes)

        # 清空画布按钮
        self.clear_btn = QPushButton("清空画布", self)
        self.clear_btn.setFixedSize(80, 28)
        self._update_clear_button_style()
        self.clear_btn.clicked.connect(self.clear_all_nodes)

    def _update_clear_button_style(self):
        """更新清空画布按钮样式"""
        btn_bg = theme_manager.get_color("button_danger")
        btn_hover = theme_manager.get_color("button_danger_hover")
        self.clear_btn.setStyleSheet(
            f"QPushButton {{ background: {btn_bg}; color: white; border: none; border-radius: 4px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {btn_hover}; }}"
        )

    def _update_fit_button_style(self):
        """更新自适应按钮样式"""
        btn_bg = theme_manager.get_color("button_primary")
        btn_hover = theme_manager.get_color("button_primary_hover")
        self.fit_btn.setStyleSheet(
            f"QPushButton {{ background: {btn_bg}; color: white; border: none; border-radius: 4px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {btn_hover}; }}"
        )

    def update_theme(self):
        """更新视图主题"""
        self._update_fit_button_style()
        self._update_clear_button_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 自适应按钮在右上角
        self.fit_btn.move(self.width() - self.fit_btn.width() - 10, 10)
        # 清空画布按钮在自适应按钮左侧
        self.clear_btn.move(self.width() - self.fit_btn.width() - self.clear_btn.width() - 20, 10)

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
            
            # Ctrl + 左键单击：增选/取消选中节点
            if event.modifiers() == Qt.ControlModifier:
                if isinstance(item, SimpleNodeItem):
                    # 切换该节点的选中状态
                    item.setSelected(not item.isSelected())
                    event.accept()
                    return
                else:
                    # Ctrl + 点击空白区域，不做任何操作（保持当前选择）
                    event.accept()
                    return
            
            # 普通左键点击（不含 Ctrl）或 Shift+左键点击
            if not isinstance(item, SimpleNodeItem):
                # 点击空白区域：开始框选
                self._selecting = True
                self._select_start = scene_pos
                self._selection_rect_item = SelectionRectItem().item
                self.scene().addItem(self._selection_rect_item)
                
                # 检查是否按住 Ctrl 或 Shift 键进行增选
                self._ctrl_selecting = bool(event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier))
                
                # 如果不是增选模式，先清空选择
                if not self._ctrl_selecting:
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
            rect = self._selection_rect_item.rect()
            rect.setTopLeft(self._select_start)
            rect.setBottomRight(current_pos)
            rect = rect.normalized()
            self._selection_rect_item.setRect(rect)
            
            # 实时更新检测 Ctrl/Shift 键状态（允许用户在框选过程中按下/释放修饰键）
            modifiers = QApplication.keyboardModifiers()
            is_additive = bool(modifiers & (Qt.ControlModifier | Qt.ShiftModifier))
            
            for item in self.scene().items():
                if isinstance(item, SimpleNodeItem):
                    in_rect = rect.intersects(item.sceneBoundingRect())
                    if is_additive:
                        # 增选模式：框选范围内的节点选中，范围外的保持原有状态
                        if in_rect:
                            item.setSelected(True)
                        # 不在范围内的节点保持原状态，不做修改
                    else:
                        # 普通模式：框选范围内的选中，范围外的取消选中
                        item.setSelected(in_rect)
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
        rect = nodes[0].sceneBoundingRect()
        for node in nodes[1:]:
            rect = rect.united(node.sceneBoundingRect())
        margin = 50
        rect.adjust(-margin, -margin, margin, margin)
        self.fitInView(rect, Qt.KeepAspectRatio)

    def clear_all_nodes(self):
        """清空画布中的所有节点、连接和组"""
        from PySide6.QtWidgets import QMessageBox

        # 获取所有节点和组
        nodes = [item for item in self.scene().items() if isinstance(item, SimpleNodeItem)]
        groups = [item for item in self.scene().items() if isinstance(item, NodeGroup)]
        
        if not nodes and not groups:
            return

        # 确认对话框
        msg_parts = []
        if nodes:
            msg_parts.append(f"{len(nodes)} 个节点")
        if groups:
            msg_parts.append(f"{len(groups)} 个组")
        msg = "、".join(msg_parts)
        
        reply = QMessageBox.question(
            self,
            "确认清空",
            f"确定要清空画布中的所有内容吗？\n共有 {msg} 将被删除。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 删除所有节点（包括连接）
            for node in nodes:
                self.delete_node(node)
            
            # 删除所有组
            for group in groups:
                group.disband()
            
            print(f"已清空画布，删除了 {len(nodes)} 个节点，{len(groups)} 个组")

    def keyPressEvent(self, event):
        # Ctrl+G 打组快捷键
        if event.key() == Qt.Key_G and event.modifiers() == Qt.ControlModifier:
            self.group_selected_nodes()
            return
        # 空格键调出节点列表（在鼠标位置或视图中心）
        if event.key() == Qt.Key_Space and event.modifiers() == Qt.NoModifier:
            self._show_node_menu_at_cursor()
            return
        # Delete 和 Backspace 键用于删除节点，但如果焦点在输入控件上则不拦截
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            # 检查是否有焦点在输入控件上
            focus_item = self.scene().focusItem()
            if focus_item:
                from PySide6.QtWidgets import QGraphicsProxyWidget
                if isinstance(focus_item, QGraphicsProxyWidget):
                    widget = focus_item.widget()
                    from PySide6.QtWidgets import QLineEdit, QTextEdit
                    if isinstance(widget, (QLineEdit, QTextEdit)):
                        # 焦点在输入控件上，不拦截按键
                        super().keyPressEvent(event)
                        return
            self.delete_selected_nodes()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        from PySide6.QtWidgets import QMenu, QVBoxLayout, QLabel
        
        scene_pos = self.mapToScene(event.pos())
        item = self.scene().itemAt(scene_pos, self.transform())
        if isinstance(item, PortItem):
            item = item.parent_node

        selected_nodes = [i for i in self.scene().selectedItems() if isinstance(i, SimpleNodeItem)]

        if isinstance(item, SimpleNodeItem):
            menu = QMenu(self)
            if len(selected_nodes) > 1 and item.isSelected():
                # 多选节点时的菜单
                group_action = menu.addAction(f"打组 ({len(selected_nodes)}个节点)")
                delete_action = menu.addAction(f"删除 ({len(selected_nodes)}个节点)")
                action = menu.exec(event.globalPos())
                if action == group_action:
                    self.group_selected_nodes()
                elif action == delete_action:
                    for node in selected_nodes:
                        self.delete_node(node)
            else:
                # 单选节点时的菜单
                group_action = None
                if len(selected_nodes) >= 1:
                    group_action = menu.addAction(f"打组 ({len(selected_nodes)}个节点)")
                delete_action = menu.addAction("删除")
                action = menu.exec(event.globalPos())
                if action == group_action:
                    self.group_selected_nodes()
                elif action == delete_action:
                    self.delete_node(item)
        elif isinstance(item, NodeGroup):
            # 点击节点组时的菜单
            menu = QMenu(self)
            select_all_action = menu.addAction("选中全部节点")
            menu.addSeparator()
            disband_action = menu.addAction("解散组")
            rename_action = menu.addAction("重命名")
            save_group_action = menu.addAction("组保存为JSON")
            action = menu.exec(event.globalPos())
            if action == select_all_action:
                # 选中组内所有节点
                for node in item.nodes:
                    node.setSelected(True)
                print(f"已选中组内 {len(item.nodes)} 个节点")
            elif action == disband_action:
                item.disband()
            elif action == rename_action:
                # 让名称编辑框获得焦点并全选
                item._name_edit.setFocus()
                item._name_edit.selectAll()
            elif action == save_group_action:
                # 将组内节点保存为JSON
                item.save_group_to_json()
        else:
            self._show_node_create_menu(event.globalPos(), scene_pos)

    def _show_node_menu_at_cursor(self):
        """在鼠标位置或视图中心显示节点创建菜单"""
        from PySide6.QtGui import QCursor
        
        # 获取鼠标在视图中的位置
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        
        # 检查鼠标是否在视图范围内
        view_rect = self.rect()
        if view_rect.contains(cursor_pos):
            # 鼠标在视图内，使用鼠标位置
            scene_pos = self.mapToScene(cursor_pos)
            global_pos = QCursor.pos()
        else:
            # 鼠标在视图外，使用视图中心
            center_pos = self.viewport().rect().center()
            scene_pos = self.mapToScene(center_pos)
            global_pos = self.mapToGlobal(center_pos)
        
        self._show_node_create_menu(global_pos, scene_pos)

    def _show_node_create_menu(self, global_pos, scene_pos):
        """显示节点创建菜单 - 使用瀑布流展示"""
        from ..nodes.node_library import NODE_LIBRARY_CATEGORIZED

        # 创建自定义菜单
        menu = NodeSearchMenu(self)
        menu.load_categories(NODE_LIBRARY_CATEGORIZED)
        
        # 连接节点选择信号
        def on_node_selected(name):
            func = LOCAL_NODE_LIBRARY[name]
            node = SimpleNodeItem(name, func, scene_pos.x(), scene_pos.y())
            self.scene().addItem(node)
            node.setup_ports()
            self.node_added.emit(name)
            print(f"已添加节点: {name}")
            
        menu.node_selected.connect(on_node_selected)
        
        # 显示菜单
        menu.show_at(global_pos)

    def delete_selected_nodes(self):
        selected = [item for item in self.scene().selectedItems() if isinstance(item, SimpleNodeItem)]
        for node in selected:
            self.delete_node(node)

    def delete_node(self, node):
        node.remove_all_connections()
        self.scene().removeItem(node)
        print(f"已删除节点: {node.name}")

    def group_selected_nodes(self):
        """将选中的节点打组"""
        selected_nodes = [item for item in self.scene().selectedItems() if isinstance(item, SimpleNodeItem)]
        
        if len(selected_nodes) < 1:
            print("请至少选择一个节点进行打组")
            return
        
        # 检查是否有节点已经在组中
        nodes_in_group = [node for node in selected_nodes if hasattr(node, '_parent_group') and node._parent_group]
        if nodes_in_group:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self,
                "节点已分组",
                f"有 {len(nodes_in_group)} 个节点已经在组中。\n是否将这些节点移动到新组？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            # 从原有组中移除
            for node in nodes_in_group:
                if node._parent_group:
                    node._parent_group.remove_node(node)
        
        # 创建新的节点组
        group = NodeGroup(nodes=selected_nodes, name=f"组 {len(self._get_all_groups()) + 1}")
        self.scene().addItem(group)
        
        # 清除节点选中状态，选中组
        for node in selected_nodes:
            node.setSelected(False)
        group.setSelected(True)
        
        print(f"已创建节点组，包含 {len(selected_nodes)} 个节点")

    def _get_all_groups(self):
        """获取场景中所有的节点组"""
        return [item for item in self.scene().items() if isinstance(item, NodeGroup)]

    def ungroup_selected_group(self):
        """解散选中的组"""
        selected_groups = [item for item in self.scene().selectedItems() if isinstance(item, NodeGroup)]
        for group in selected_groups:
            group.disband()