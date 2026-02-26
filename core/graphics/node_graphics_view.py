"""自定义视图"""

from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QPushButton, QMenu,
                               QWidgetAction, QLineEdit, QWidget, QApplication, QDialog,
                               QMessageBox)
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QPainter, QDrag
from PySide6.QtCore import QMimeData

from .simple_node_item import SimpleNodeItem
from .port_item import PortItem
from .connection_item import ConnectionItem
from .node_group import NodeGroup
from .loop_node_item import LoopNodeItem
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
            
            # 检查是否是循环节点
            if name == "区间循环":
                from .loop_node_item import RangeLoopNodeItem
                node = RangeLoopNodeItem(name, x=scene_pos.x(), y=scene_pos.y())
                self.scene().addItem(node)
                print(f"已添加区间循环节点：{name}")
            elif name == "List 循环":
                from .loop_node_item import ListLoopNodeItem
                node = ListLoopNodeItem(name, x=scene_pos.x(), y=scene_pos.y())
                self.scene().addItem(node)
                print(f"已添加 List 循环节点：{name}")
            else:
                func = LOCAL_NODE_LIBRARY[name]
                node = SimpleNodeItem(name, func, scene_pos.x(), scene_pos.y())
                self.scene().addItem(node)
                node.setup_ports()
                self.node_added.emit(name)
                print(f"已添加节点：{name}")
            
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

            # 点击到端口：让端口自己处理（拖拽连接线）
            if isinstance(item, PortItem):
                # 调用父类的 mousePressEvent，让事件传播到 PortItem
                super().mousePressEvent(event)
                return

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
            # 检查是否是循环节点
            from .loop_node_item import LoopNodeItem
            if not isinstance(item, (SimpleNodeItem, LoopNodeItem)):
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
            
            from .loop_node_item import LoopNodeItem
            for item in self.scene().items():
                if isinstance(item, (SimpleNodeItem, LoopNodeItem)):
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
                print(f"已连接: {(getattr(self.start_port.parent_node, 'loop_name', None) or self.start_port.parent_node.name)} -> {(getattr(end_port.parent_node, 'loop_name', None) or end_port.parent_node.name)}")
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
        """自适应所有节点（包括普通节点和循环节点）"""
        from core.graphics.loop_node_item import LoopNodeItem
        
        # 获取所有节点（包括普通节点和循环节点）
        all_nodes = [item for item in self.scene().items() if isinstance(item, (SimpleNodeItem, LoopNodeItem))]
        
        if not all_nodes:
            return
        
        # 计算所有节点的边界
        rect = all_nodes[0].sceneBoundingRect()
        for node in all_nodes[1:]:
            rect = rect.united(node.sceneBoundingRect())
        
        margin = 50
        rect.adjust(-margin, -margin, margin, margin)
        self.fitInView(rect, Qt.KeepAspectRatio)

    def clear_all_nodes(self):
        """清空画布中的所有节点、连接和组"""
        from PySide6.QtWidgets import QMessageBox

        # 获取所有节点和组（包括循环节点）
        nodes = [item for item in self.scene().items() if isinstance(item, SimpleNodeItem)]
        loop_nodes = [item for item in self.scene().items() if isinstance(item, LoopNodeItem)]
        groups = [item for item in self.scene().items() if isinstance(item, NodeGroup)]

        if not nodes and not loop_nodes and not groups:
            return

        # 确认对话框
        msg_parts = []
        if nodes:
            msg_parts.append(f"{len(nodes)} 个节点")
        if loop_nodes:
            msg_parts.append(f"{len(loop_nodes)} 个循环节点")
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

            # 删除所有循环节点
            for loop_node in loop_nodes:
                self.delete_node(loop_node)

            # 删除所有组
            for group in groups:
                group.disband()

            print(f"已清空画布，删除了 {len(nodes)} 个节点，{len(loop_nodes)} 个循环节点，{len(groups)} 个组")

    def keyPressEvent(self, event):
        # Ctrl+G 打组快捷键
        if event.key() == Qt.Key_G and event.modifiers() == Qt.ControlModifier:
            self.group_selected_nodes()
            return
        # Ctrl+D 复制选中节点快捷键
        if event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            self.duplicate_selected_nodes()
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

        from .loop_node_item import LoopNodeItem
        
        selected_nodes = [i for i in self.scene().selectedItems() if isinstance(i, (SimpleNodeItem, LoopNodeItem))]
        selected_loop_nodes = [i for i in selected_nodes if isinstance(i, LoopNodeItem)]

        # 如果点击的是循环节点
        if isinstance(item, LoopNodeItem):
            menu = QMenu(self)

            # 添加调试子菜单
            debug_menu = menu.addMenu("🔍 调试")
            
            # 单节点调试选项
            single_debug_action = debug_menu.addAction("⚡ 单节点调试")
            single_debug_action.setToolTip("仅调试该循环节点，使用属性面板的循环配置")
            
            # 断点调试选项
            breakpoint_debug_action = debug_menu.addAction("🐛 断点调试")
            breakpoint_debug_action.setToolTip("调试该循环节点及其上游依赖节点")
            
            menu.addSeparator()

            # 如果有多个选中节点，添加批量操作
            if len(selected_nodes) > 1:
                delete_action = menu.addAction(f"删除 ({len(selected_nodes)}个节点)")
                duplicate_action = menu.addAction(f"复制并粘贴 ({len(selected_nodes)}个节点)")
            else:
                delete_action = menu.addAction("删除")
                duplicate_action = menu.addAction("复制并粘贴")

            action = menu.exec(event.globalPos())
            if action == delete_action:
                for node in selected_nodes:
                    if isinstance(node, LoopNodeItem):
                        # 删除循环节点时，将内部节点移出
                        for inner_node in list(node.nodes):
                            node.remove_node(inner_node)
                    self.delete_node(node)
            elif action == duplicate_action:
                self.duplicate_selected_nodes()
            elif action == single_debug_action:
                # 单节点调试 - 对选中的第一个循环节点
                self._debug_single_loop_node(selected_nodes[0] if len(selected_nodes) > 0 else item)
            elif action == breakpoint_debug_action:
                # 断点调试 - 对选中的第一个循环节点
                self._debug_breakpoint_loop(selected_nodes[0] if len(selected_nodes) > 0 else item)
            return

        if isinstance(item, SimpleNodeItem):
            menu = QMenu(self)

            # 获取场景中所有节点（包括普通节点和循环节点）
            from core.graphics.loop_node_item import LoopNodeItem
            all_nodes = [i for i in self.scene().items() if isinstance(i, (SimpleNodeItem, LoopNodeItem))]

            # 判断是否可以反选：选中了节点，且不是全部节点
            can_invert = len(selected_nodes) > 0 and len(selected_nodes) < len(all_nodes)

            # 添加调试子菜单
            debug_menu = menu.addMenu("🔍 调试")
            
            # 单节点调试选项
            single_debug_action = debug_menu.addAction("⚡ 单节点调试")
            single_debug_action.setToolTip("仅调试该节点，使用属性面板的输入值")
            
            # 断点调试选项
            breakpoint_debug_action = debug_menu.addAction("🐛 断点调试")
            breakpoint_debug_action.setToolTip("调试该节点及其上游依赖路径上的所有节点")
            
            menu.addSeparator()

            if len(selected_nodes) > 1 and item.isSelected():
                # 多选节点时的菜单
                group_action = menu.addAction(f"打组 ({len(selected_nodes)}个节点)")
                if can_invert:
                    invert_action = menu.addAction(f"反选节点 ({len(all_nodes) - len(selected_nodes)}个)")
                delete_action = menu.addAction(f"删除 ({len(selected_nodes)}个节点)")
                # 添加复制并粘贴选项
                duplicate_action = menu.addAction(f"复制并粘贴 ({len(selected_nodes)}个节点)")
                action = menu.exec(event.globalPos())
                if action == group_action:
                    self.group_selected_nodes()
                elif can_invert and action == invert_action:
                    self.invert_selection()
                elif action == delete_action:
                    for node in selected_nodes:
                        self.delete_node(node)
                elif action == duplicate_action:
                    self.duplicate_selected_nodes()
                elif action == single_debug_action:
                    # 单节点调试 - 对选中的第一个节点
                    self._debug_single_node(selected_nodes[0])
                elif action == breakpoint_debug_action:
                    # 断点调试 - 对选中的第一个节点
                    self._debug_breakpoint(selected_nodes[0])
            else:
                # 单选节点时的菜单
                group_action = None
                if len(selected_nodes) >= 1:
                    group_action = menu.addAction(f"打组 ({len(selected_nodes)}个节点)")
                if can_invert:
                    invert_action = menu.addAction(f"反选节点 ({len(all_nodes) - len(selected_nodes)}个)")
                delete_action = menu.addAction("删除")
                # 添加复制并粘贴选项
                duplicate_action = menu.addAction("复制并粘贴")
                action = menu.exec(event.globalPos())
                if action == group_action:
                    self.group_selected_nodes()
                elif can_invert and action == invert_action:
                    self.invert_selection()
                elif action == delete_action:
                    self.delete_node(item)
                elif action == duplicate_action:
                    self.duplicate_selected_nodes()
                elif action == single_debug_action:
                    # 单节点调试
                    self._debug_single_node(item)
                elif action == breakpoint_debug_action:
                    # 断点调试
                    self._debug_breakpoint(item)
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

    def invert_selection(self):
        """反选节点：选中未选中的节点，取消已选中节点的选中状态（支持普通节点和循环节点）"""
        from core.graphics.loop_node_item import LoopNodeItem
        
        # 获取所有节点（包括普通节点和循环节点）
        all_nodes = [item for item in self.scene().items() if isinstance(item, (SimpleNodeItem, LoopNodeItem))]
        for node in all_nodes:
            node.setSelected(not node.isSelected())
        selected_count = len([n for n in all_nodes if n.isSelected()])
        print(f"反选完成，当前选中 {selected_count} 个节点")

    def delete_selected_nodes(self):
        """删除选中的节点（支持普通节点和循环节点）"""
        selected_items = self.scene().selectedItems()
        # 先删除普通节点
        selected = [item for item in selected_items if isinstance(item, SimpleNodeItem)]
        for node in selected:
            self.delete_node(node)
        # 删除循环节点
        selected_loops = [item for item in selected_items if isinstance(item, LoopNodeItem)]
        for loop_node in selected_loops:
            self.delete_node(loop_node)

    def delete_node(self, node):
        """删除节点（支持普通节点和循环节点）"""
        # 删除节点的所有连接
        if hasattr(node, 'remove_all_connections'):
            # 普通节点
            node.remove_all_connections()
        elif isinstance(node, LoopNodeItem):
            # 循环节点：删除所有端口的连接
            for port in node.input_ports + node.output_ports:
                for conn in list(port.connections):
                    conn.remove_connection()
            # 删除循环内部的节点
            for inner_node in list(node.nodes):
                node.remove_node(inner_node)

        self.scene().removeItem(node)

        # 获取节点名称用于日志
        node_name = getattr(node, 'name', None) or getattr(node, 'loop_name', '未知节点')
        print(f"已删除节点：{node_name}")

    def duplicate_selected_nodes(self):
        """复制并粘贴选中的节点（支持普通节点和循环节点）"""
        selected_items = self.scene().selectedItems()
        selected_nodes = [item for item in selected_items if isinstance(item, (SimpleNodeItem, LoopNodeItem))]

        if not selected_nodes:
            print("请先选择要复制的节点")
            return

        # 计算偏移量：按照增量加载的方式，放置在当前画布内容的右侧
        offset_x, offset_y = self._calculate_duplicate_offset(selected_nodes)

        # 复制节点（不复制连接）
        node_pairs = []  # [(原节点，新节点), ...] 的映射
        for node in selected_nodes:
            if isinstance(node, SimpleNodeItem):
                new_node = self._duplicate_simple_node(node, offset_x, offset_y)
                node_pairs.append((node, new_node))
            elif isinstance(node, LoopNodeItem):
                new_node = self._duplicate_loop_node(node, offset_x, offset_y)
                node_pairs.append((node, new_node))

        # 复制选中节点之间的连接线
        self._duplicate_connections_between_nodes(node_pairs)

        # 清除原有节点的选中状态，选中新复制的节点
        for old_node, new_node in node_pairs:
            old_node.setSelected(False)
            new_node.setSelected(True)

        print(f"已复制并粘贴 {len(node_pairs)} 个节点")

    def _calculate_duplicate_offset(self, selected_nodes):
        """计算复制节点的偏移量（按照增量加载的位置处理方式）"""
        # 获取当前画布中所有节点的边界
        all_nodes = [item for item in self.scene().items() if isinstance(item, (SimpleNodeItem, LoopNodeItem))]

        if not all_nodes:
            return 50, 50  # 默认偏移

        # 计算当前画布内容的最右边和最下边位置
        max_right = 0
        max_bottom = 0
        for node in all_nodes:
            rect = node.sceneBoundingRect()
            max_right = max(max_right, rect.right())
            max_bottom = max(max_bottom, rect.bottom())

        # 计算选中节点的边界
        selected_rect = selected_nodes[0].sceneBoundingRect()
        for node in selected_nodes[1:]:
            selected_rect = selected_rect.united(node.sceneBoundingRect())

        # 计算新内容应该放置的偏移量（右边 +100 间距）
        offset_x = max_right - selected_rect.right() + 100
        offset_y = 0  # 保持相同的 Y 坐标

        # 确保最小偏移量为 50
        offset_x = max(offset_x, 50)

        return offset_x, offset_y

    def _duplicate_simple_node(self, node, offset_x, offset_y):
        """复制普通节点"""
        from core.graphics.simple_node_item import SimpleNodeItem
        from core.graphics.connection_item import ConnectionItem

        # 创建新节点
        new_node = SimpleNodeItem(node.name, node.func, x=node.x() + offset_x, y=node.y() + offset_y)
        self.scene().addItem(new_node)
        new_node.setup_ports()

        # 复制参数值
        if hasattr(node, 'param_values'):
            new_node.param_values.update(node.param_values)

        # 触发 node_added 信号
        self.node_added.emit(node.name)

        return new_node

    def _duplicate_loop_node(self, node, offset_x, offset_y):
        """复制循环节点"""
        from core.graphics.loop_node_item import LoopNodeItem, RangeLoopNodeItem, ListLoopNodeItem

        # 根据循环类型创建对应的节点
        if node.loop_type == LoopNodeItem.LOOP_TYPE_RANGE:
            new_node = RangeLoopNodeItem(name=node.loop_name, x=node.x() + offset_x, y=node.y() + offset_y)
        elif node.loop_type == LoopNodeItem.LOOP_TYPE_LIST:
            new_node = ListLoopNodeItem(name=node.loop_name, x=node.x() + offset_x, y=node.y() + offset_y)
        else:
            # 未知类型，默认为区间循环
            new_node = RangeLoopNodeItem(name=node.loop_name, x=node.x() + offset_x, y=node.y() + offset_y)

        self.scene().addItem(new_node)

        # 复制循环配置
        new_node._range_start = node.range_start
        new_node._range_end = node.range_end
        new_node._range_step = node.range_step
        new_node._list_data = node.list_data

        return new_node

    def _duplicate_connections_between_nodes(self, node_pairs):
        """复制选中节点之间的连接线

        Args:
            node_pairs: [(原节点，新节点), ...] 的列表
        """
        from core.graphics.connection_item import ConnectionItem

        # 创建原节点到新节点的映射
        node_map = {old_node: new_node for old_node, new_node in node_pairs}

        # 遍历所有原节点，查找它们之间的连接
        for old_source_node, new_source_node in node_pairs:
            # 获取原节点的所有输出端口连接
            output_ports = []
            if isinstance(old_source_node, SimpleNodeItem):
                output_ports = old_source_node.output_ports
            elif isinstance(old_source_node, LoopNodeItem):
                output_ports = old_source_node.output_ports

            for out_port in output_ports:
                for conn in out_port.connections:
                    # 检查连接的目标节点是否也在选中的节点中
                    target_node = conn.end_port.parent_node if conn.end_port else None
                    if target_node in node_map:
                        # 目标节点在选中节点中，需要复制这条连接线
                        new_target_node = node_map[target_node]

                        # 查找新节点中对应的端口
                        new_out_port = None
                        new_in_port = None

                        # 查找源端口（在新源节点中）
                        if isinstance(new_source_node, SimpleNodeItem):
                            for port in new_source_node.output_ports:
                                if port.port_name == out_port.port_name:
                                    new_out_port = port
                                    break
                        elif isinstance(new_source_node, LoopNodeItem):
                            for port in new_source_node.output_ports:
                                if port.port_name == out_port.port_name:
                                    new_out_port = port
                                    break

                        # 查找目标端口（在新目标节点中）
                        old_in_port = conn.end_port
                        if isinstance(new_target_node, SimpleNodeItem):
                            for port in new_target_node.input_ports:
                                if port.port_name == old_in_port.port_name:
                                    new_in_port = port
                                    break
                        elif isinstance(new_target_node, LoopNodeItem):
                            for port in new_target_node.input_ports:
                                if port.port_name == old_in_port.port_name:
                                    new_in_port = port
                                    break

                        # 创建新的连接线
                        if new_out_port and new_in_port:
                            new_conn = ConnectionItem(new_out_port, new_in_port)
                            self.scene().addItem(new_conn)
                            new_conn.finalize_connection(new_in_port)

    def group_selected_nodes(self):
        """将选中的节点打组（包括普通节点和循环节点）"""
        selected_items = self.scene().selectedItems()
        # 同时支持普通节点和循环节点
        selected_nodes = [item for item in selected_items if isinstance(item, (SimpleNodeItem, LoopNodeItem))]

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

    def _enter_loop_edit(self, loop_node):
        """进入循环编辑模式"""
        print(f"进入循环编辑：{loop_node.loop_name}")

    def _delete_loop(self, loop_node):
        """删除循环节点"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除循环节点 '{loop_node.loop_name}' 吗？\n\n循环内的节点将被移出并保留在画布上。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 移除循环内的节点
            for node in list(loop_node.nodes):
                loop_node.remove_node(node)

            # 删除循环节点
            self.scene().removeItem(loop_node)
            print(f"已删除循环节点 '{loop_node.loop_name}'")

    def _debug_single_node(self, node: SimpleNodeItem):
        """单节点调试
        
        仅执行选中的单个节点，使用该节点属性面板的输入值。
        
        Args:
            node: 要调试的节点
        """
        from core.engine.debug_executor import debug_single_node
        
        # 重置节点状态
        node.result = None
        node.reset_status()
        
        # 执行调试
        debug_single_node(node)

    def _debug_breakpoint(self, target_node: SimpleNodeItem):
        """断点调试
        
        执行目标节点及其上游依赖路径上的所有节点。
        基于 Python 代码的顺序执行原理。
        
        Args:
            target_node: 目标调试节点
        """
        from core.engine.debug_executor import debug_breakpoint
        from core.graphics.loop_node_item import LoopNodeItem
        
        # 获取所有节点（不包括循环节点）
        all_nodes = [
            item for item in self.scene().items() 
            if isinstance(item, SimpleNodeItem)
        ]
        
        # 重置相关节点状态
        target_node.result = None
        target_node.reset_status()
        
        # 执行调试
        debug_breakpoint(target_node, all_nodes)

    def _debug_single_loop_node(self, loop_node: LoopNodeItem):
        """单节点调试 - 循环节点
        
        执行一次完整的循环迭代。
        优先使用外部连接的输入值，如果没有连接则使用属性面板的配置值。
        
        Args:
            loop_node: 要调试的循环节点
        """
        from core.engine.debug_executor import debug_single_loop_node
        from core.graphics.loop_node_item import LoopNodeItem
        
        # 获取所有节点（包括普通节点和循环节点）
        all_nodes = [
            item for item in self.scene().items() 
            if isinstance(item, (SimpleNodeItem, LoopNodeItem))
        ]
        
        # 重置循环状态
        loop_node.reset_execution_state()
        
        # 执行调试（传入所有节点以支持外部输入）
        debug_single_loop_node(loop_node, all_nodes)

    def _debug_breakpoint_loop(self, loop_node: LoopNodeItem):
        """断点调试 - 循环节点
        
        执行循环节点及其上游依赖节点。
        包括：
        1. 执行所有上游依赖节点（为循环提供输入数据）
        2. 执行完整的循环迭代
        
        Args:
            loop_node: 目标调试的循环节点
        """
        from core.engine.debug_executor import debug_breakpoint_loop
        from core.graphics.loop_node_item import LoopNodeItem
        
        # 获取所有节点（包括普通节点和循环节点）
        all_nodes = [
            item for item in self.scene().items() 
            if isinstance(item, (SimpleNodeItem, LoopNodeItem))
        ]
        
        # 重置循环状态
        loop_node.reset_execution_state()
        
        # 执行调试
        debug_breakpoint_loop(loop_node, all_nodes)

