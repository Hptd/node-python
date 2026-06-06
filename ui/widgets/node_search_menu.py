"""节点搜索菜单 - 瀑布流展示，支持展开/收缩层级"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
    QScrollArea, QFrame, QLabel, QApplication, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QMouseEvent, QWheelEvent

from utils.theme_manager import theme_manager


class CategoryHeader(QFrame):
    """分类标题栏 - 可点击展开/收缩"""
    clicked = Signal()
    
    def __init__(self, category_name: str, parent=None):
        super().__init__(parent)
        self.category_name = category_name
        self.expanded = True
        self._setup_ui()
        
    def _setup_ui(self):
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        
        # 展开/收缩箭头
        self.arrow_label = QLabel("▼")
        self.arrow_label.setFixedWidth(16)
        self.arrow_label.setStyleSheet(f"color: {theme_manager.get_color('text_secondary')}; font-size: 10px;")
        layout.addWidget(self.arrow_label)
        
        # 分类名称
        self.name_label = QLabel(self.category_name)
        self.name_label.setStyleSheet(f"""
            color: {theme_manager.get_color('text_primary')};
            font-weight: bold;
            font-size: 13px;
        """)
        layout.addWidget(self.name_label)
        
        # 伸缩空间
        layout.addStretch()
        
        # 设置背景样式
        self._update_style()
        
    def _update_style(self):
        bg_color = theme_manager.get_color('hover_bg')
        self.setStyleSheet(f"""
            CategoryHeader {{
                background: transparent;
                border-radius: 4px;
            }}
            CategoryHeader:hover {{
                background: {bg_color};
            }}
        """)
        
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.toggle()
            self.clicked.emit()
        super().mousePressEvent(event)
        
    def toggle(self):
        self.expanded = not self.expanded
        self.arrow_label.setText("▼" if self.expanded else "▶")
        
    def set_expanded(self, expanded: bool):
        self.expanded = expanded
        self.arrow_label.setText("▼" if self.expanded else "▶")


class NodeItem(QFrame):
    """节点项 - 可点击选择"""
    clicked = Signal(str)
    entered = Signal()

    def __init__(self, node_name: str, parent=None):
        super().__init__(parent)
        self.node_name = node_name
        self._keyboard_selected = False
        self._setup_ui()
        
    def _setup_ui(self):
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 12, 0)
        layout.setSpacing(0)
        
        # 节点名称
        self.name_label = QLabel(self.node_name)
        self.name_label.setStyleSheet(f"""
            color: {theme_manager.get_color('text_primary')};
            font-size: 12px;
        """)
        layout.addWidget(self.name_label)
        layout.addStretch()
        
        # 设置样式
        self._update_style()
        
    def _update_style(self):
        hover_bg = theme_manager.get_color('hover_bg')
        keyboard_bg = theme_manager.get_color('primary')
        self._hover_bg = hover_bg
        self._keyboard_bg = keyboard_bg
        self.setStyleSheet(f"""
            NodeItem {{
                background: transparent;
                border-radius: 3px;
            }}
            NodeItem:hover {{
                background: {hover_bg};
            }}
        """)

    def set_keyboard_selected(self, selected: bool):
        self._keyboard_selected = selected
        if selected:
            self.setStyleSheet(f"""
                NodeItem {{
                    background: {self._keyboard_bg};
                    border-radius: 3px;
                }}
                NodeItem:hover {{
                    background: {self._keyboard_bg};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                NodeItem {{
                    background: transparent;
                    border-radius: 3px;
                }}
                NodeItem:hover {{
                    background: {self._hover_bg};
                }}
            """)

    def enterEvent(self, event):
        self.entered.emit()
        super().enterEvent(event)
        
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.node_name)
        super().mousePressEvent(event)


class CategorySection(QWidget):
    """分类区域 - 包含标题和节点列表"""
    node_selected = Signal(str)
    
    def __init__(self, category_name: str, node_names: list, parent=None):
        super().__init__(parent)
        self.category_name = category_name
        self.node_names = node_names
        self.node_items = []
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # 分类标题
        self.header = CategoryHeader(self.category_name)
        self.header.clicked.connect(self._on_header_clicked)
        layout.addWidget(self.header)
        
        # 节点容器
        self.nodes_container = QWidget()
        nodes_layout = QVBoxLayout(self.nodes_container)
        nodes_layout.setContentsMargins(0, 2, 0, 4)
        nodes_layout.setSpacing(1)
        
        # 添加节点项
        for node_name in sorted(self.node_names):
            node_item = NodeItem(node_name)
            node_item.clicked.connect(self._on_node_clicked)
            nodes_layout.addWidget(node_item)
            self.node_items.append(node_item)
            
        nodes_layout.addStretch()
        layout.addWidget(self.nodes_container)
        
    def _on_header_clicked(self):
        self.nodes_container.setVisible(self.header.expanded)
        
    def _on_node_clicked(self, node_name: str):
        self.node_selected.emit(node_name)
        
    def filter_nodes(self, search_text: str) -> bool:
        """根据搜索文本过滤节点，返回是否有可见节点"""
        from utils.node_search import match_node
        
        if not search_text.strip():
            # 空搜索，显示所有
            for item in self.node_items:
                item.setVisible(True)
            self.setVisible(True)
            return True
            
        has_visible = False
        for item in self.node_items:
            is_match, _ = match_node(search_text, item.node_name)
            item.setVisible(is_match)
            if is_match:
                has_visible = True
                
        # 有匹配时自动展开
        if has_visible:
            self.header.set_expanded(True)
            self.nodes_container.setVisible(True)
            
        self.setVisible(has_visible)
        return has_visible
        
    def get_visible_node_items(self):
        """获取所有可见的 NodeItem（用于键盘导航）"""
        return [item for item in self.node_items if item.isVisible()]

    def set_expanded(self, expanded: bool):
        """设置展开/收缩状态"""
        self.header.set_expanded(expanded)
        self.nodes_container.setVisible(expanded)


class NodeSearchMenu(QFrame):
    """节点搜索菜单 - 瀑布流展示"""
    node_selected = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.category_sections = {}
        self._keyboard_selected_idx = -1
        self._setup_ui()
        
    def _setup_ui(self):
        # 设置窗口属性
        self.setWindowFlags(Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)
        
        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索节点...")
        self.search_edit.setFixedHeight(32)
        self.search_edit.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.search_edit.setFocusPolicy(Qt.StrongFocus)
        
        input_bg = theme_manager.get_color('input_bg')
        input_text = theme_manager.get_color('input_text')
        border_color = theme_manager.get_color('border')
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {input_bg};
                color: {input_text};
                border: 1px solid {border_color};
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme_manager.get_color('primary')};
            }}
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        main_layout.addWidget(self.search_edit)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(400)
        scroll.setMinimumWidth(220)
        
        # 滚动区域内容
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        self.content_layout.addStretch()
        
        scroll.setWidget(self.content_widget)
        main_layout.addWidget(scroll)
        
        # 设置整体样式
        menu_bg = theme_manager.get_color('menu_bg')
        self.setStyleSheet(f"""
            NodeSearchMenu {{
                background: {menu_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
        """)
        
        # 设置固定宽度
        self.setFixedWidth(260)
        
    def load_categories(self, categorized_nodes: dict):
        """加载分类节点数据"""
        # 清除现有内容（保留 stretch）
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.category_sections.clear()
        
        # 按分类名称排序添加
        for category_name in sorted(categorized_nodes.keys()):
            node_names = list(categorized_nodes[category_name].keys())
            if not node_names:
                continue
                
            section = CategorySection(category_name, node_names)
            section.node_selected.connect(self._on_node_selected)
            for item in section.node_items:
                item.entered.connect(self._on_item_entered)
            # 默认展开
            section.set_expanded(True)
            
            self.content_layout.insertWidget(
                self.content_layout.count() - 1, section
            )
            self.category_sections[category_name] = section
            
    def _on_search_changed(self, text: str):
        """搜索文本变化"""
        for section in self.category_sections.values():
            section.filter_nodes(text)
        self._clear_keyboard_selection()
        # 搜索后自动高亮第一个可见项
        visible = self._collect_visible_items()
        if visible:
            self._move_selection_to(0)
            
    def _on_node_selected(self, node_name: str):
        """节点被选中"""
        self.node_selected.emit(node_name)
        self.close()
        
    def get_first_visible_node(self) -> str:
        """获取第一个可见的节点名称，如果没有则返回空字符串"""
        search_text = self.search_edit.text().strip()
        
        # 遍历所有分类，找到第一个可见的节点
        for category_name in sorted(self.category_sections.keys()):
            section = self.category_sections[category_name]
            if not section.isVisible():
                continue
                
            for node_item in section.node_items:
                if node_item.isVisible():
                    # 如果有搜索文本，检查是否匹配
                    if search_text:
                        from utils.node_search import match_node
                        is_match, _ = match_node(search_text, node_item.node_name)
                        if is_match:
                            return node_item.node_name
                    else:
                        return node_item.node_name
        return ""
        
    def show_at(self, global_pos):
        """在指定位置显示菜单"""
        self.move(global_pos)
        self.show()
        self.raise_()
        self.activateWindow()
        
        # 延迟设置焦点，确保输入法正常工作
        QTimer.singleShot(10, lambda: self.search_edit.setFocus())
        
    def _collect_visible_items(self):
        """收集所有可见的 NodeItem（按分类排序）"""
        items = []
        for category_name in sorted(self.category_sections.keys()):
            section = self.category_sections[category_name]
            if section.isVisible():
                items.extend(section.get_visible_node_items())
        return items

    def _clear_keyboard_selection(self):
        """清除键盘高亮"""
        if self._keyboard_selected_idx >= 0:
            visible = self._collect_visible_items()
            if self._keyboard_selected_idx < len(visible):
                visible[self._keyboard_selected_idx].set_keyboard_selected(False)
        self._keyboard_selected_idx = -1

    def _move_selection_to(self, idx):
        """将键盘选择移动到指定索引"""
        visible = self._collect_visible_items()
        if not visible:
            self._keyboard_selected_idx = -1
            return
        idx = max(0, min(idx, len(visible) - 1))
        if idx == self._keyboard_selected_idx:
            return
        self._clear_keyboard_selection()
        self._keyboard_selected_idx = idx
        visible[idx].set_keyboard_selected(True)
        # 确保选中项在滚动区域可见（仅 ScrollArea 父级）
        self._ensure_item_visible(visible[idx])

    def _ensure_item_visible(self, item):
        """确保节点项在滚动区域内可见"""
        # 向上查找 QScrollArea
        parent = item.parent()
        while parent and parent != self:
            from PySide6.QtWidgets import QScrollArea
            if isinstance(parent, QScrollArea):
                parent.ensureWidgetVisible(item, 0, 10)
                break
            parent = parent.parent()

    def _on_item_entered(self):
        """鼠标进入 NodeItem 时清除键盘选择"""
        self._clear_keyboard_selection()

    def keyPressEvent(self, event):
        """处理键盘事件"""
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            visible = self._collect_visible_items()
            if self._keyboard_selected_idx >= 0 and self._keyboard_selected_idx < len(visible):
                self._on_node_selected(visible[self._keyboard_selected_idx].node_name)
            else:
                first_node = self.get_first_visible_node()
                if first_node:
                    self._on_node_selected(first_node)
        elif event.key() == Qt.Key_Down:
            visible = self._collect_visible_items()
            if visible:
                new_idx = self._keyboard_selected_idx + 1
                if new_idx >= len(visible):
                    new_idx = 0
                self._move_selection_to(new_idx)
        elif event.key() == Qt.Key_Up:
            visible = self._collect_visible_items()
            if visible:
                new_idx = self._keyboard_selected_idx - 1
                if new_idx < 0:
                    new_idx = len(visible) - 1
                self._move_selection_to(new_idx)
        else:
            super().keyPressEvent(event)
            
    def wheelEvent(self, event: QWheelEvent):
        """处理滚轮事件"""
        # 让滚动区域处理滚轮事件
        super().wheelEvent(event)
