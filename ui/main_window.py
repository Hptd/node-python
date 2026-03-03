"""主窗口UI"""

import sys
import json
import inspect
import os
from PySide6.QtWidgets import (QMainWindow, QGraphicsScene, QDockWidget, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QTextEdit, QToolBar, QPushButton,
                               QInputDialog, QMessageBox, QApplication, QTreeWidgetItem,
                               QFileDialog, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
                               QMenu, QDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QTextCursor, QColor, QTextCharFormat

from core.graphics.node_graphics_view import NodeGraphicsView
from core.graphics.simple_node_item import SimpleNodeItem
from core.graphics.connection_item import ConnectionItem
from core.graphics.port_item import PortItem
from core.graphics.loop_node_item import LoopNodeItem, RangeLoopNodeItem, ListLoopNodeItem
from core.graphics.multithread_node_item import MultithreadNodeItem
from core.engine.graph_executor import execute_graph
from core.nodes.node_library import (NODE_LIBRARY_CATEGORIZED, LOCAL_NODE_LIBRARY,
                                      CUSTOM_CATEGORIES, add_node_to_library,
                                      get_node_source_code, get_node_category,
                                      is_custom_node, remove_node_from_library)
from ui.widgets.draggable_node_tree import DraggableNodeTree
from ui.dialogs.custom_node_dialog import CustomNodeCodeDialog
from ui.dialogs.ai_node_generator_dialog import AINodeGeneratorDialog
from ui.dialogs.path_selector_dialog import PathSelectorDialog
from ui.dialogs.package_manager_dialog import PackageManagerDialog
from ui.dialogs.node_plugin_dialog import NodePluginExportDialog, NodePluginImportDialog
from ui.dialogs.regex_generator_dialog import RegexGeneratorDialog
from utils.console_stream import EmittingStream, get_message_format, detect_message_type
from utils.theme_manager import theme_manager
from config.settings import settings


class SimplePyFlowWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("中文节点py编辑器")
        self.resize(1000, 700)

        self.setup_bottom_dock()

        self.scene = QGraphicsScene()
        self.view = NodeGraphicsView(self.scene)
        self.setCentralWidget(self.view)

        self.scene.selectionChanged.connect(self.on_selection_changed)

        self.setup_toolbar()
        self.setup_left_dock()
        self.setup_right_dock()

        # 初始化主题（在 UI 创建之后）
        self._init_theme()

        # 连接主题切换信号
        theme_manager.theme_changed.connect(self._on_theme_changed)

    def setup_toolbar(self):
        toolbar = QToolBar("主工具栏")
        self.addToolBar(toolbar)

        run_action = QAction("▶ 运行", self)
        run_action.triggered.connect(self.run_graph)
        toolbar.addAction(run_action)

        stop_action = QAction("⏹ 停止", self)
        stop_action.triggered.connect(self.stop_graph)
        toolbar.addAction(stop_action)

        toolbar.addSeparator()

        save_action = QAction("💾 保存为 JSON", self)
        save_action.triggered.connect(self.save_to_json)
        toolbar.addAction(save_action)

        # 加载JSON改为带菜单的按钮
        load_menu = QMenu(self)
        load_overwrite_action = load_menu.addAction("覆盖加载")
        load_overwrite_action.setToolTip("清空当前画布后加载JSON内容")
        load_overwrite_action.triggered.connect(lambda: self.load_from_json(mode="overwrite"))
        
        load_increment_action = load_menu.addAction("增量加载")
        load_increment_action.setToolTip("保留当前画布内容，在空白位置添加JSON内容")
        load_increment_action.triggered.connect(lambda: self.load_from_json(mode="increment"))
        
        load_action = QAction("📂 加载 JSON", self)
        load_action.setMenu(load_menu)
        load_action.triggered.connect(lambda: self.load_from_json(mode="overwrite"))
        toolbar.addAction(load_action)

        toolbar.addSeparator()
        
        # 节点插件导出
        export_plugin_action = QAction("📤 导出节点插件", self)
        export_plugin_action.setToolTip("将自定义节点导出为JSON格式插件包")
        export_plugin_action.triggered.connect(self._open_export_plugin_dialog)
        toolbar.addAction(export_plugin_action)

        # 节点插件导入
        import_plugin_action = QAction("📥 导入节点插件", self)
        import_plugin_action.setToolTip("导入JSON格式的节点插件包")
        import_plugin_action.triggered.connect(self._open_import_plugin_dialog)
        toolbar.addAction(import_plugin_action)
        
        # 依赖包管理
        pkg_action = QAction("📦 依赖管理", self)
        pkg_action.triggered.connect(self._open_package_manager)
        toolbar.addAction(pkg_action)

        # 嵌入式 Python 环境初始化
        setup_action = QAction("🔧 初始化环境", self)
        setup_action.triggered.connect(self._setup_embedded_python)
        toolbar.addAction(setup_action)

        toolbar.addSeparator()

        # 主题切换按钮
        self.theme_action = QAction(self._get_theme_icon() + " 切换主题", self)
        self.theme_action.triggered.connect(self._toggle_theme)
        self.theme_action.setToolTip(f"当前主题: {theme_manager.get_theme_info()['name']}，点击切换")
        toolbar.addAction(self.theme_action)

    def setup_left_dock(self):
        dock = QDockWidget("📦 本地节点库", self)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        # 管理分类按钮
        cat_btn_layout = QHBoxLayout()
        add_cat_btn = QPushButton("+ 新建分类")
        add_cat_btn.setObjectName("btn_secondary")
        add_cat_btn.clicked.connect(self._add_custom_category)

        cat_btn_layout.addWidget(add_cat_btn)

        custom_node_btn = QPushButton("+ 自定义节点")
        custom_node_btn.setObjectName("btn_warning")
        custom_node_btn.clicked.connect(self._open_custom_node_editor)
        cat_btn_layout.addWidget(custom_node_btn)

        ai_gen_btn = QPushButton("🤖 AI模板")
        ai_gen_btn.setObjectName("btn_ai")
        ai_gen_btn.clicked.connect(self._open_ai_node_generator)
        cat_btn_layout.addWidget(ai_gen_btn)

        layout.addLayout(cat_btn_layout)

        # 树形节点列表
        self.node_tree = DraggableNodeTree()
        self.node_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        # 连接右键菜单信号
        self.node_tree.node_right_clicked.connect(self._on_node_right_click)
        self.node_tree.node_delete_requested.connect(self._on_node_delete_requested)
        layout.addWidget(self.node_tree)

        dock.setWidget(container)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self._refresh_node_tree()

    def _refresh_node_tree(self):
        self.node_tree.clear()
        # 更新自定义分类列表（用于右键菜单判断）
        self.node_tree.set_custom_categories(CUSTOM_CATEGORIES)
        
        for category, nodes in NODE_LIBRARY_CATEGORIZED.items():
            cat_item = QTreeWidgetItem(self.node_tree, [category])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsDragEnabled)
            for name in nodes:
                child = QTreeWidgetItem(cat_item, [name])
                child.setData(0, Qt.UserRole, name)  # 存储节点名用于拖拽
            cat_item.setExpanded(True)

    def _on_tree_double_click(self, item, column):
        node_name = item.data(0, Qt.UserRole)
        if node_name and node_name in LOCAL_NODE_LIBRARY:
            func = LOCAL_NODE_LIBRARY[node_name]
            
            # 检查是否是循环节点
            if node_name == "区间循环":
                from core.graphics.loop_node_item import RangeLoopNodeItem
                node = RangeLoopNodeItem(node_name, x=0, y=0)
                self.scene.addItem(node)
                print(f"已添加区间循环节点：{node_name}")
            elif node_name == "List 循环":
                from core.graphics.loop_node_item import ListLoopNodeItem
                node = ListLoopNodeItem(node_name, x=0, y=0)
                self.scene.addItem(node)
                print(f"已添加 List 循环节点：{node_name}")
            elif node_name == "多线程处理":
                node = MultithreadNodeItem(node_name, x=0, y=0)
                self.scene.addItem(node)
                print(f"已添加多线程处理节点：{node_name}")
            else:
                node = SimpleNodeItem(node_name, func, x=0, y=0)
                self.scene.addItem(node)
                node.setup_ports()
                print(f"已添加节点：{node_name}")
    def _add_custom_category(self):
        name, ok = QInputDialog.getText(self, "新建分类", "请输入分类名称：")
        if ok and name.strip():
            name = name.strip()
            if name in NODE_LIBRARY_CATEGORIZED:
                QMessageBox.warning(self, "提示", f"分类 '{name}' 已存在。")
                return
            NODE_LIBRARY_CATEGORIZED[name] = {}
            CUSTOM_CATEGORIES.append(name)
            self._refresh_node_tree()
            print(f"已新建分类: {name}")

    def _open_custom_node_editor(self):
        dlg = CustomNodeCodeDialog(self)
        # 连接信号：节点创建成功后立即刷新列表
        dlg.node_created.connect(lambda name, category: self._refresh_node_tree())
        if dlg.exec() == QDialog.Accepted:
            # 信号已经在创建时触发刷新，这里做最终确认
            self._refresh_node_tree()
            print(f"自定义节点 '{dlg.generated_name}' 已添加到节点库。")

    def _open_ai_node_generator(self):
        """打开AI节点生成器对话框"""
        dlg = AINodeGeneratorDialog(self)
        # 连接信号：节点创建成功后刷新列表
        dlg.node_created.connect(lambda name, category: self._refresh_node_tree())
        if dlg.exec() == QDialog.Accepted:
            self._refresh_node_tree()
            print(f"AI生成节点 '{dlg.generated_name}' 已添加到节点库。")

    def _on_node_right_click(self, node_name, global_pos):
        """处理节点树右键点击事件"""
        # 创建右键菜单
        menu = QMenu(self)
        
        edit_action = QAction("✏️ 编辑节点", self)
        edit_action.triggered.connect(lambda: self._edit_custom_node(node_name))
        menu.addAction(edit_action)
        
        delete_action = QAction("🗑️ 删除节点", self)
        delete_action.triggered.connect(lambda: self._on_node_delete_requested(node_name))
        menu.addAction(delete_action)
        
        menu.exec(global_pos)

    def _edit_custom_node(self, node_name):
        """编辑自定义节点"""
        # 获取节点的源代码和分类
        source_code = get_node_source_code(node_name)
        category = get_node_category(node_name)
        
        if not source_code:
            QMessageBox.warning(self, "警告", f"无法获取节点 '{node_name}' 的源代码。")
            return
        
        # 打开编辑对话框
        dlg = CustomNodeCodeDialog(
            parent=self,
            edit_mode=True,
            original_name=node_name,
            original_code=source_code,
            original_display_name=node_name,
            original_category=category
        )
        
        # 连接更新信号
        dlg.node_updated.connect(self._on_node_updated)
        
        if dlg.exec() == QDialog.Accepted:
            print(f"节点 '{node_name}' 编辑完成。")

    def _on_node_updated(self, original_name, new_name, category):
        """处理节点更新事件，同步更新画布中的节点引用"""
        # 刷新节点树
        self._refresh_node_tree()
        
        # 同步更新画布中所有该节点的引用
        updated_count = 0
        for item in self.scene.items():
            if isinstance(item, SimpleNodeItem) and item.name == original_name:
                # 保存旧的连接关系（按端口名）
                old_input_connections = {}
                old_output_connections = {}
                
                for port in item.input_ports:
                    if port.connections:
                        # 保存连接的源端口信息
                        connections_info = []
                        for conn in port.connections:
                            if conn.start_port:
                                connections_info.append({
                                    'source_port': conn.start_port,
                                    'source_node': conn.start_port.parent_node
                                })
                        old_input_connections[port.port_name] = connections_info
                
                for port in item.output_ports:
                    if port.connections:
                        # 保存连接的目标端口信息
                        connections_info = []
                        for conn in port.connections:
                            if conn.end_port:
                                connections_info.append({
                                    'target_port': conn.end_port,
                                    'target_node': conn.end_port.parent_node
                                })
                        old_output_connections[port.port_name] = connections_info
                
                # 移除所有现有连接
                all_ports = item.input_ports + item.output_ports
                for port in all_ports:
                    for conn in port.connections[:]:
                        conn.remove_connection()
                
                # 更新节点名称
                item.name = new_name
                # 更新节点函数
                new_func = LOCAL_NODE_LIBRARY.get(new_name)
                item.func = new_func
                
                # 更新源代码和自定义节点标记（关键：确保执行时使用最新代码）
                if new_func and hasattr(new_func, '_custom_source'):
                    item.source_code = new_func._custom_source
                    item.is_custom_node = True
                else:
                    item.source_code = None
                    item.is_custom_node = False
                
                # 清除端口列表
                item.input_ports = []
                item.output_ports = []
                
                # 重新设置端口（因为函数签名可能改变）
                item.setup_ports()
                
                # 尝试恢复连接（如果端口名仍然存在）
                for port in item.input_ports:
                    if port.port_name in old_input_connections:
                        for conn_info in old_input_connections[port.port_name]:
                            source_port = conn_info['source_port']
                            # 检查源端口是否仍然有效
                            if source_port and source_port.scene():
                                # 重新创建连接
                                new_conn = ConnectionItem(source_port, port)
                                self.scene.addItem(new_conn)
                                new_conn.finalize_connection(port)
                
                for port in item.output_ports:
                    if port.port_name in old_output_connections:
                        for conn_info in old_output_connections[port.port_name]:
                            target_port = conn_info['target_port']
                            # 检查目标端口是否仍然有效
                            if target_port and target_port.scene():
                                # 重新创建连接
                                new_conn = ConnectionItem(port, target_port)
                                self.scene.addItem(new_conn)
                                new_conn.finalize_connection(target_port)
                
                # 触发重绘
                item.update()
                updated_count += 1
        
        if updated_count > 0:
            print(f"已同步更新画布中 {updated_count} 个 '{original_name}' 节点引用为 '{new_name}'。")
        
        # 刷新属性面板（如果当前选中的是被更新的节点或同类型节点）
        selected_items = self.scene.selectedItems()
        if selected_items:
            for selected in selected_items:
                if isinstance(selected, SimpleNodeItem) and selected.name == new_name:
                    self.on_selection_changed()
                    break

    def _on_node_delete_requested(self, node_name):
        """处理节点删除请求"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除自定义节点 '{node_name}' 吗？\n\n注意：画布中已存在的该节点实例将保留，但无法再添加新实例。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if remove_node_from_library(node_name):
                self._refresh_node_tree()
                print(f"节点 '{node_name}' 已从节点库中删除。")
            else:
                QMessageBox.warning(self, "删除失败", f"无法删除节点 '{node_name}'。")

    def setup_right_dock(self):
        dock = QDockWidget("📝 节点属性", self)
        panel = QWidget()
        layout = QVBoxLayout()

        # 参数输入区域
        layout.addWidget(QLabel("📥 参数输入:"))
        self.params_container = QWidget()
        self.params_layout = QVBoxLayout(self.params_container)
        self.params_layout.setContentsMargins(0, 0, 0, 0)
        self.params_layout.setSpacing(5)
        layout.addWidget(self.params_container)

        # 错误信息区域（初始隐藏）
        self.error_label = QLabel("❌ 执行错误:")
        self.error_label.setStyleSheet("color: #FF5555; font-weight: bold;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setMaximumHeight(100)
        self.error_text.setStyleSheet("background-color: #2a1a1a; color: #FF5555; border: 1px solid #FF5555;")
        self.error_text.setVisible(False)
        layout.addWidget(self.error_text)

        layout.addWidget(QLabel("📄 节点文档注释:"))
        self.doc_text = QTextEdit()
        self.doc_text.setReadOnly(True)
        layout.addWidget(self.doc_text)

        layout.addWidget(QLabel("💻 节点源代码:"))
        self.source_text = QTextEdit()
        self.source_text.setReadOnly(True)
        self.source_text.setObjectName("code_editor")
        layout.addWidget(self.source_text)

        layout.addStretch()  # 添加弹性空间
        panel.setLayout(layout)
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def setup_bottom_dock(self):
        dock = QDockWidget("💻 运行控制台", self)

        # 创建主容器
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏（设置日志路径按钮）
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(5, 2, 5, 2)

        self.log_path_label = QLabel()
        self.log_path_label.setStyleSheet("color: #888; font-size: 11px;")
        toolbar_layout.addWidget(self.log_path_label)

        toolbar_layout.addStretch()

        set_log_path_btn = QPushButton("📁 设置日志路径")
        set_log_path_btn.setObjectName("btn_primary_small")
        set_log_path_btn.clicked.connect(self._set_log_path)
        toolbar_layout.addWidget(set_log_path_btn)

        open_folder_btn = QPushButton("📂 打开文件夹")
        open_folder_btn.setObjectName("btn_secondary_small")
        open_folder_btn.clicked.connect(self._open_log_folder)
        toolbar_layout.addWidget(open_folder_btn)

        clear_log_btn = QPushButton("🗑️ 清空控制台")
        clear_log_btn.setObjectName("btn_danger_small")
        clear_log_btn.clicked.connect(self._clear_console)
        toolbar_layout.addWidget(clear_log_btn)

        layout.addWidget(toolbar)

        # 搜索框（初始隐藏）
        self.search_widget = QWidget()
        search_layout = QHBoxLayout(self.search_widget)
        search_layout.setContentsMargins(5, 2, 5, 2)
        search_layout.setSpacing(5)

        # 搜索图标
        search_icon = QLabel("🔍")
        search_layout.addWidget(search_icon)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._find_next)
        search_layout.addWidget(self.search_input, 1)

        # 匹配数量显示
        self.search_count_label = QLabel("0/0")
        self.search_count_label.setStyleSheet("color: #888; font-size: 12px; min-width: 40px;")
        search_layout.addWidget(self.search_count_label)

        # 上一个按钮（上箭头）
        self.prev_btn = QPushButton("▲")
        self.prev_btn.setFixedWidth(30)
        self.prev_btn.setToolTip("上一个匹配项")
        self.prev_btn.clicked.connect(self._find_previous)
        search_layout.addWidget(self.prev_btn)

        # 下一个按钮（下箭头）
        self.next_btn = QPushButton("▼")
        self.next_btn.setFixedWidth(30)
        self.next_btn.setToolTip("下一个匹配项")
        self.next_btn.clicked.connect(self._find_next)
        search_layout.addWidget(self.next_btn)

        # 关闭搜索按钮
        close_search_btn = QPushButton("✕")
        close_search_btn.setFixedWidth(30)
        close_search_btn.setToolTip("隐藏搜索框")
        close_search_btn.clicked.connect(self._close_search)
        search_layout.addWidget(close_search_btn)

        # 搜索框常显
        layout.addWidget(self.search_widget)

        # 控制台文本区域
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("console")
        self.console.installEventFilter(self)  # 安装事件过滤器以捕获快捷键
        layout.addWidget(self.console)

        dock.setWidget(container)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        # 初始化日志流
        self._stream = EmittingStream()
        self._stream.textWritten.connect(self.colored_output)
        sys.stdout = self._stream

        # 从设置加载日志配置
        self._init_log_settings()

        # 初始化搜索相关变量
        self._search_results = []  # 存储所有匹配的位置
        self._current_search_index = -1  # 当前选中的匹配项索引
        self._search_text = ""  # 当前搜索文本
        self._highlight_format = QTextCharFormat()
        self._highlight_format.setBackground(QColor("#FFEB3B"))  # 黄色高亮
        self._highlight_format.setForeground(QColor("#000000"))  # 黑色文字
        self._current_highlight_format = QTextCharFormat()
        self._current_highlight_format.setBackground(QColor("#FF9800"))  # 橙色高亮当前选中项
        self._current_highlight_format.setForeground(QColor("#FFFFFF"))  # 白色文字

    def _init_log_settings(self):
        """初始化日志设置"""
        log_dir = settings.get("logging.log_dir", "output_logs")
        log_filename = settings.get("logging.log_filename", "output_log.txt")
        enabled = settings.get("logging.enabled", True)

        self._stream.set_log_path(log_dir, log_filename)
        self._stream.set_enabled(enabled)

        # 更新标签显示
        log_file_path = self._stream.get_log_file_path()
        self.log_path_label.setText(f"日志文件: {log_file_path}")

    def _set_log_path(self):
        """设置日志文件保存路径"""
        current_dir = settings.get("logging.log_dir", "output_logs")

        # 选择文件夹
        new_dir = QFileDialog.getExistingDirectory(
            self,
            "选择日志保存文件夹",
            current_dir,
            QFileDialog.ShowDirsOnly
        )

        if new_dir:
            # 更新设置
            settings.set("logging.log_dir", new_dir)
            settings.save()

            # 更新日志流
            log_filename = settings.get("logging.log_filename", "output_log.txt")
            self._stream.set_log_path(new_dir, log_filename)

            # 更新显示
            log_file_path = self._stream.get_log_file_path()
            self.log_path_label.setText(f"日志文件: {log_file_path}")

            print(f"日志保存路径已设置为: {log_file_path}")
            QMessageBox.information(self, "设置成功", f"日志保存路径已设置为:\n{log_file_path}")

    def _open_log_folder(self):
        """打开日志文件所在文件夹"""
        import subprocess
        import platform

        log_file_path = self._stream.get_log_file_path()
        log_dir = os.path.dirname(log_file_path)

        # 确保目录存在
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # 根据操作系统打开文件夹
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", log_dir], check=True)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", log_dir], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", log_dir], check=True)
            print(f"已打开日志文件夹: {log_dir}")
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件夹:\n{e}")
            print(f"[打开文件夹失败] {e}")

    def _clear_console(self):
        """清空控制台显示内容"""
        self.console.clear()
        print("控制台已清空")

    def eventFilter(self, obj, event):
        """事件过滤器，捕获 Ctrl+F 快捷键"""
        if obj == self.console and event.type() == event.Type.KeyPress:
            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_F:
                # Ctrl+F 切换搜索框显示/隐藏
                if self.search_widget.isVisible():
                    # 已显示则隐藏
                    self._close_search()
                else:
                    # 未显示则打开
                    self._open_search()
                return True
            elif event.key() == Qt.Key_Escape and self.search_widget.isVisible():
                self._close_search()
                return True
        return super().eventFilter(obj, event)

    def _open_search(self):
        """打开搜索框"""
        self.search_widget.setVisible(True)
        self.search_input.setFocus()
        self.search_input.selectAll()
        # 如果控制台有选中文本，将其填入搜索框
        cursor = self.console.textCursor()
        if cursor.hasSelection():
            self.search_input.setText(cursor.selectedText())
            self._on_search_text_changed(cursor.selectedText())

    def _close_search(self):
        """关闭搜索框并清除高亮"""
        self.search_widget.setVisible(False)
        self._clear_search_highlights()
        self.console.setFocus()

    def _clear_search_highlights(self):
        """清除所有搜索高亮并恢复原始颜色"""
        # 获取文档的所有文本
        cursor = self.console.textCursor()
        cursor.select(QTextCursor.Document)

        # 清除搜索高亮（背景和前景）
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("transparent"))
        # 不设置前景色，让它恢复为默认颜色
        cursor.mergeCharFormat(fmt)

        # 重置搜索状态
        self._search_results = []
        self._current_search_index = -1
        self._search_text = ""
        self._update_search_count_label()

    def _on_search_text_changed(self, text):
        """搜索文本变化时的处理"""
        self._search_text = text
        self._clear_search_highlights()
        
        if not text:
            self._update_search_count_label()
            return
        
        # 查找所有匹配项
        self._find_all_matches(text)
        
        # 如果有匹配项，选中第一个
        if self._search_results:
            self._current_search_index = 0
            self._highlight_current_match()
        
        self._update_search_count_label()

    def _find_all_matches(self, text):
        """查找所有匹配的文本位置"""
        self._search_results = []
        if not text:
            return
        
        # 获取文档内容
        document = self.console.document()
        
        # 从文档开头开始查找
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.Start)
        
        # 使用 QTextDocument::find 查找所有匹配
        while True:
            # 查找下一个匹配
            found_cursor = document.find(text, cursor)
            
            if found_cursor.isNull():
                break
            
            # 记录匹配位置
            self._search_results.append({
                'start': found_cursor.selectionStart(),
                'end': found_cursor.selectionEnd()
            })
            
            # 高亮显示（非当前选中的用黄色）
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#FFEB3B"))
            fmt.setForeground(QColor("#000000"))
            found_cursor.mergeCharFormat(fmt)
            
            # 移动到匹配位置之后继续查找
            cursor = found_cursor
            cursor.movePosition(QTextCursor.Right)

    def _highlight_current_match(self):
        """高亮显示当前选中的匹配项（橙色）"""
        if not self._search_results or self._current_search_index < 0:
            return
        
        # 获取当前匹配项的位置
        match = self._search_results[self._current_search_index]
        
        # 创建光标并选中当前匹配项
        cursor = self.console.textCursor()
        cursor.setPosition(match['start'])
        cursor.setPosition(match['end'], QTextCursor.KeepAnchor)
        
        # 应用橙色高亮
        cursor.mergeCharFormat(self._current_highlight_format)
        
        # 滚动到当前匹配项
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def _restore_highlight(self, index):
        """将指定索引的匹配项恢复为黄色高亮"""
        if index < 0 or index >= len(self._search_results):
            return
        
        match = self._search_results[index]
        cursor = self.console.textCursor()
        cursor.setPosition(match['start'])
        cursor.setPosition(match['end'], QTextCursor.KeepAnchor)
        cursor.mergeCharFormat(self._highlight_format)

    def _find_next(self):
        """查找下一个匹配项"""
        if not self._search_results:
            return
        
        # 恢复当前匹配项的颜色
        if self._current_search_index >= 0:
            self._restore_highlight(self._current_search_index)
        
        # 移动到下一个
        self._current_search_index += 1
        
        # 如果超出范围，停在最后一个（不循环）
        if self._current_search_index >= len(self._search_results):
            self._current_search_index = len(self._search_results) - 1
        
        self._highlight_current_match()
        self._update_search_count_label()

    def _find_previous(self):
        """查找上一个匹配项"""
        if not self._search_results:
            return
        
        # 恢复当前匹配项的颜色
        if self._current_search_index >= 0:
            self._restore_highlight(self._current_search_index)
        
        # 移动到上一个
        self._current_search_index -= 1
        
        # 如果超出范围，停在第一个（不循环）
        if self._current_search_index < 0:
            self._current_search_index = 0
        
        self._highlight_current_match()
        self._update_search_count_label()

    def _update_search_count_label(self):
        """更新匹配数量显示"""
        total = len(self._search_results)
        current = self._current_search_index + 1 if self._current_search_index >= 0 else 0
        
        if total == 0:
            self.search_count_label.setText("0/0")
        else:
            self.search_count_label.setText(f"{current}/{total}")

    def normal_output(self, text):
        """普通输出（兼容旧代码）"""
        self.colored_output(text, "normal")

    def colored_output(self, text, msg_type: str = "normal"):
        """彩色输出到控制台
        
        Args:
            text: 要输出的文本
            msg_type: 消息类型 (normal, error, warning, info, success, debug, system)
        """
        # 如果没有指定类型，尝试自动检测
        if msg_type == "normal":
            msg_type = detect_message_type(text)
        
        # 获取对应消息类型的格式
        fmt = get_message_format(msg_type)
        
        # 移动到末尾并插入带格式的文本
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text, fmt)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def on_selection_changed(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            self.doc_text.clear()
            self.source_text.clear()
            self._clear_param_inputs()
            # 隐藏错误信息
            self.error_label.setVisible(False)
            self.error_text.setVisible(False)
            return

        item = selected_items[0]
        
        # 处理循环节点
        from core.graphics.loop_node_item import LoopNodeItem
        if isinstance(item, MultithreadNodeItem):
            self._setup_multithread_node_properties(item)
        elif isinstance(item, LoopNodeItem):
            self._setup_loop_node_properties(item)
        elif hasattr(item, 'func'):  # SimpleNodeItem
            func = item.func
            doc = inspect.getdoc(func) or "该节点无注释。"
            # 优先使用内置节点保存的源代码（解决 PyInstaller 打包后无法获取源码的问题）
            if hasattr(func, '_source'):
                source = func._source
            # 其次使用自定义节点保存的源代码
            elif hasattr(func, '_custom_source'):
                source = func._custom_source
            else:
                try:
                    source = inspect.getsource(func)
                except Exception:
                    source = "无法获取源代码。"

            self.doc_text.setText(doc)
            self.source_text.setText(source)
            
            # 显示错误信息（如果节点有错误）
            if hasattr(item, 'get_error_message') and item.get_error_message():
                self.error_label.setVisible(True)
                self.error_text.setVisible(True)
                self.error_text.setText(item.get_error_message())
            else:
                self.error_label.setVisible(False)
                self.error_text.setVisible(False)
            
            # 显示参数输入控件
            self._setup_param_inputs(item)
        else:
            self.error_label.setVisible(False)
            self.error_text.setVisible(False)


    def _setup_loop_node_properties(self, loop_item):
        """为循环节点设置属性面板 UI"""
        from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QLabel, QSpinBox, QTextEdit
        
        self._clear_param_inputs()
        self._current_node_item = loop_item  # 保存当前循环节点引用

        # 显示循环节点文档
        if isinstance(loop_item, RangeLoopNodeItem):
            doc = """区间循环节点（Range Loop）。
按照指定的整数范围和步长进行循环迭代，每次迭代输出一个整数值。

端口说明:
    输入端口（左侧）:
        • 最小值：循环起始值（包含），int 类型
        • 最大值：循环结束值（不包含），int 类型
        • 步长：每次迭代的增量，int 类型
    
    输出端口（右侧）:
        • 迭代值：当前循环的整数值，每次迭代更新
        • 汇总结果：循环完成后输出所有迭代结果的列表

使用说明:
    1. 配置左侧三个输入参数（最小值、最大值、步长）
    2. 将"迭代值"端口连接到需要接收循环数据的节点
    3. 将"汇总结果"端口连接到需要接收完整结果列表的节点
    4. 运行后，节点会按照 range(最小值，最大值，步长) 生成迭代序列

示例:
    最小值=0, 最大值=5, 步长=1 → 迭代值依次为：0, 1, 2, 3, 4"""
        else:
            doc = """List 循环节点（List Loop）。
遍历列表中的每个元素进行循环迭代，每次迭代输出一个列表元素。

端口说明:
    输入端口（左侧）:
        • 列表数据：要迭代的列表数据，支持 JSON 格式字符串或 list 类型
    
    输出端口（右侧）:
        • 迭代值：当前循环的列表元素，每次迭代更新
        • 汇总结果：循环完成后输出所有迭代结果的列表

使用说明:
    1. 在左侧"列表数据"端口输入要迭代的列表（JSON 格式，如：["a","b","c"]）
    2. 将"迭代值"端口连接到需要接收循环数据的节点
    3. 将"汇总结果"端口连接到需要接收完整结果列表的节点
    4. 运行后，节点会依次输出列表中的每个元素

示例:
    列表数据=["apple","banana","orange"] → 迭代值依次为：apple, banana, orange"""
        
        self.doc_text.setPlainText(doc)
        self.source_text.setPlainText("循环节点是内置功能节点，不支持查看源代码。")
        
        # 隐藏错误信息
        self.error_label.setVisible(False)
        self.error_text.setVisible(False)
        
        # 创建循环节点专用属性 UI
        from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QLabel
        
        # 区间循环参数
        if isinstance(loop_item, RangeLoopNodeItem):
            # Range 参数组
            range_group = QGroupBox("循环参数")
            range_layout = QVBoxLayout()
            
            # 开始值
            start_label = QLabel("最小值:")
            range_layout.addWidget(start_label)
            
            self._loop_start_spin = QSpinBox()
            self._loop_start_spin.setRange(-10000, 10000)
            self._loop_start_spin.setValue(loop_item.range_start)
            self._loop_start_spin.setToolTip("循环起始值（包含）")
            self._loop_start_spin.valueChanged.connect(self._on_loop_range_start_changed)
            range_layout.addWidget(self._loop_start_spin)
            
            # 结束值
            end_label = QLabel("最大值:")
            range_layout.addWidget(end_label)
            
            self._loop_end_spin = QSpinBox()
            self._loop_end_spin.setRange(-10000, 10000)
            self._loop_end_spin.setValue(loop_item.range_end)
            self._loop_end_spin.setToolTip("循环结束值（不包含）")
            self._loop_end_spin.valueChanged.connect(self._on_loop_range_end_changed)
            range_layout.addWidget(self._loop_end_spin)
            
            # 步长
            step_label = QLabel("步长:")
            range_layout.addWidget(step_label)
            
            self._loop_step_spin = QSpinBox()
            self._loop_step_spin.setRange(1, 1000)
            self._loop_step_spin.setValue(loop_item.range_step)
            self._loop_step_spin.setToolTip("每次迭代的增量")
            self._loop_step_spin.valueChanged.connect(self._on_loop_range_step_changed)
            range_layout.addWidget(self._loop_step_spin)
            
            # 预览标签
            self._loop_preview_label = QLabel()
            self._loop_preview_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
            self._update_loop_preview()
            range_layout.addWidget(self._loop_preview_label)
            
            range_group.setLayout(range_layout)
            self.params_layout.addWidget(range_group)
        
        # List 循环参数
        elif isinstance(loop_item, ListLoopNodeItem):
            # List 参数组
            list_group = QGroupBox("列表数据")
            list_layout = QVBoxLayout()

            list_label = QLabel("JSON 列表数据:")
            list_layout.addWidget(list_label)

            self._loop_list_text = QTextEdit()
            self._loop_list_text.setPlaceholderText('例如：["apple", "banana", "orange"]')
            self._loop_list_text.setMaximumHeight(150)
            self._loop_list_text.setText(loop_item.list_data)
            self._loop_list_text.textChanged.connect(self._on_loop_list_data_changed)
            list_layout.addWidget(self._loop_list_text)
            
            # 预览标签
            self._loop_list_preview_label = QLabel()
            self._loop_list_preview_label.setStyleSheet("color: #2196F3; font-size: 12px;")
            self._loop_list_preview_label.setWordWrap(True)
            self._update_list_loop_preview()
            list_layout.addWidget(self._loop_list_preview_label)
            
            list_group.setLayout(list_layout)
            self.params_layout.addWidget(list_group)

        self.params_layout.addStretch()
    
    def _on_loop_range_start_changed(self, value):
        """区间循环 - 开始值变化"""
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, RangeLoopNodeItem):
            self._current_node_item.range_start = value  # 使用属性设置，自动验证
            self._update_loop_preview()

    def _on_loop_range_end_changed(self, value):
        """区间循环 - 结束值变化"""
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, RangeLoopNodeItem):
            self._current_node_item.range_end = value  # 使用属性设置，自动验证
            self._update_loop_preview()

    def _on_loop_range_step_changed(self, value):
        """区间循环 - 步长变化"""
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, RangeLoopNodeItem):
            self._current_node_item.range_step = value  # 使用属性设置，自动验证
            self._update_loop_preview()

    def _on_loop_list_data_changed(self):
        """List 循环 - 列表数据变化"""
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, ListLoopNodeItem):
            self._current_node_item.list_data = self._loop_list_text.toPlainText()  # 使用属性设置，自动验证
            self._update_list_loop_preview()
    
    def _update_loop_preview(self):
        """更新区间循环预览"""
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, RangeLoopNodeItem):
            loop_item = self._current_node_item
            try:
                preview_list = list(range(loop_item.range_start, loop_item.range_end, loop_item.range_step))
                if len(preview_list) > 10:
                    preview_text = f"{preview_list[:5]} ... (共 {len(preview_list)} 项)"
                else:
                    preview_text = str(preview_list)
                if hasattr(self, '_loop_preview_label'):
                    self._loop_preview_label.setText(f"将生成：{preview_text}")
            except Exception as e:
                if hasattr(self, '_loop_preview_label'):
                    self._loop_preview_label.setText(f"错误：{e}")
    
    def _update_list_loop_preview(self):
        """更新 List 循环预览"""
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, ListLoopNodeItem):
            loop_item = self._current_node_item
            import json
            try:
                data = json.loads(loop_item.list_data)
                if isinstance(data, list):
                    if len(data) > 5:
                        preview_text = f"{data[:3]} ... (共 {len(data)} 项)"
                    else:
                        preview_text = str(data)
                    if hasattr(self, '_loop_list_preview_label'):
                        self._loop_list_preview_label.setText(f"有效列表：{preview_text}")
                else:
                    if hasattr(self, '_loop_list_preview_label'):
                        self._loop_list_preview_label.setText("⚠ 请输入列表格式的 JSON 数据")
            except json.JSONDecodeError as e:
                if hasattr(self, '_loop_list_preview_label'):
                    self._loop_list_preview_label.setText(f"⚠ JSON 格式错误：{e}")
            except Exception as e:
                if hasattr(self, '_loop_list_preview_label'):
                    self._loop_list_preview_label.setText(f"错误：{e}")

    def _setup_multithread_node_properties(self, node_item: MultithreadNodeItem):
        """为多线程处理节点设置属性面板 UI"""
        from PySide6.QtWidgets import (QGroupBox, QVBoxLayout, QLabel,
                                       QSpinBox, QTextEdit, QComboBox)

        self._current_node_item = node_item

        doc = (
            "多线程处理节点\n\n"
            "使用多线程并发处理列表中的每个元素。\n\n"
            "端口说明：\n"
            "  输入列表：待处理的列表数据（JSON 格式）\n"
            "  线程数量：并发线程数（默认 4）\n"
            "  返回顺序：按输入顺序 / 按完成顺序\n"
            "  迭代值：连接到需要并发处理的节点\n"
            "  汇总结果：所有线程完成后的结果列表"
        )
        self.doc_text.setPlainText(doc)

        # 清除旧控件
        self._clear_param_inputs()

        # ── 输入列表 ──
        group = QGroupBox("多线程参数")
        layout = QVBoxLayout()

        layout.addWidget(QLabel("输入列表（JSON 格式）："))
        self._mt_list_text = QTextEdit()
        self._mt_list_text.setPlainText(node_item.input_list)
        self._mt_list_text.setMaximumHeight(80)
        self._mt_list_text.textChanged.connect(self._on_mt_list_changed)
        layout.addWidget(self._mt_list_text)

        # ── 线程数量 ──
        layout.addWidget(QLabel("线程数量："))
        self._mt_thread_spin = QSpinBox()
        self._mt_thread_spin.setRange(1, 999999)
        self._mt_thread_spin.setValue(node_item.thread_count)
        self._mt_thread_spin.valueChanged.connect(self._on_mt_thread_count_changed)
        layout.addWidget(self._mt_thread_spin)

        # ── 返回顺序 ──
        layout.addWidget(QLabel("返回顺序："))
        self._mt_order_combo = QComboBox()
        self._mt_order_combo.addItems(["按输入顺序", "按完成顺序"])
        self._mt_order_combo.setEditable(False)
        self._mt_order_combo.setCurrentText(node_item.return_order)
        self._mt_order_combo.currentTextChanged.connect(self._on_mt_order_changed)
        layout.addWidget(self._mt_order_combo)

        group.setLayout(layout)
        self.params_layout.addWidget(group)

    def _on_mt_list_changed(self):
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, MultithreadNodeItem):
            self._current_node_item.input_list = self._mt_list_text.toPlainText()

    def _on_mt_thread_count_changed(self, value):
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, MultithreadNodeItem):
            self._current_node_item.thread_count = value

    def _on_mt_order_changed(self, text):
        if hasattr(self, '_current_node_item') and isinstance(self._current_node_item, MultithreadNodeItem):
            self._current_node_item.return_order = text

    def _clear_param_inputs(self):
        """清除参数输入控件"""
        # 保存当前引用以便后续使用
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _setup_param_inputs(self, node_item):
        """为节点设置参数输入控件"""
        self._clear_param_inputs()
        self._current_node_item = node_item  # 保存当前节点引用

        # 获取参数信息
        if not hasattr(node_item, 'param_types') or not node_item.param_types:
            no_params_label = QLabel("<i>该节点无输入参数</i>")
            no_params_label.setStyleSheet("color: #888;")
            self.params_layout.addWidget(no_params_label)
            return

        # 特殊处理：文件夹选择器节点（整体处理，不按参数遍历）
        if node_item.name == "文件夹选择器":
            # 参数行布局
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            # 参数名标签
            label = QLabel("文件夹路径:")
            label.setFixedWidth(80)
            row_layout.addWidget(label)

            # 显示当前路径值
            path_label = QLabel()
            path_label.setObjectName("folder_path_label")
            current_path = node_item.param_values.get("folder_path", "")
            if current_path:
                path_label.setText(current_path)
                path_label.setToolTip(current_path)
            else:
                path_label.setText("<i style='color: #888;'>点击右侧按钮选择文件夹...</i>")
            path_label.setWordWrap(True)
            path_label.setStyleSheet("padding: 5px; background: rgba(128, 128, 128, 0.1); border-radius: 3px;")
            row_layout.addWidget(path_label, 1)

            # 添加文件夹选取按钮
            picker_btn = QPushButton("📁 选取")
            picker_btn.setFixedWidth(60)
            picker_btn.setToolTip("打开文件夹选择对话框")
            picker_btn.setObjectName("btn_primary_small")
            picker_btn.clicked.connect(lambda: self._open_folder_picker_dialog(node_item))
            row_layout.addWidget(picker_btn)

            self.params_layout.addWidget(row)
            return

        for param_name, param_type in node_item.param_types.items():
            # 参数行布局
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            # 参数名标签
            label = QLabel(f"{param_name}:")
            label.setFixedWidth(80)
            row_layout.addWidget(label)

            # 根据类型创建不同的输入控件
            current_value = node_item.param_values.get(param_name)

            # 特殊处理：数据提取节点的 path 参数
            if node_item.name == "数据提取" and param_name == "path":
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("点击右侧按钮选择路径...")
                if current_value is not None:
                    input_widget.setText(str(current_value))
                input_widget.textChanged.connect(
                    lambda text, name=param_name, node=node_item: self._on_param_value_changed(node, name, text)
                )
                row_layout.addWidget(input_widget)

                # 添加路径选择按钮
                selector_btn = QPushButton("🔍")
                selector_btn.setFixedWidth(30)
                selector_btn.setToolTip("打开路径选择器")
                selector_btn.setStyleSheet("background: #2196F3; color: white;")
                selector_btn.clicked.connect(self._open_path_selector)
                row_layout.addWidget(selector_btn)
            # 特殊处理：文件选择器节点的 file_filter 参数
            elif node_item.name == "文件选择器" and param_name == "file_filter":
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("全部文件 (*)")
                if current_value is not None:
                    input_widget.setText(str(current_value))
                input_widget.textChanged.connect(
                    lambda text, name=param_name, node=node_item: self._on_param_value_changed(node, name, text)
                )
                row_layout.addWidget(input_widget)

                # 添加文件选取按钮
                picker_btn = QPushButton("📁 选取")
                picker_btn.setFixedWidth(60)
                picker_btn.setToolTip("打开文件选择对话框")
                picker_btn.setObjectName("btn_primary_small")
                picker_btn.clicked.connect(lambda: self._open_file_picker_dialog(node_item))
                row_layout.addWidget(picker_btn)
            # 特殊处理：正则提取节点的 pattern 参数
            elif node_item.name == "正则提取" and param_name == "pattern":
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("点击右侧按钮生成正则表达式...")
                if current_value is not None:
                    input_widget.setText(str(current_value))
                input_widget.textChanged.connect(
                    lambda text, name=param_name, node=node_item: self._on_param_value_changed(node, name, text)
                )
                row_layout.addWidget(input_widget)

                # 添加正则生成器按钮
                regex_btn = QPushButton("🪄")
                regex_btn.setFixedWidth(30)
                regex_btn.setToolTip("打开正则表达式生成器")
                regex_btn.setStyleSheet("background: #9C27B0; color: white;")
                regex_btn.clicked.connect(lambda: self._open_regex_generator(node_item))
                row_layout.addWidget(regex_btn)
            elif param_type == bool or param_type == 'bool':
                input_widget = QCheckBox()
                input_widget.setChecked(bool(current_value) if current_value is not None else False)
                input_widget.stateChanged.connect(
                    lambda state, name=param_name, node=node_item: self._on_param_value_changed(node, name, bool(state))
                )
                row_layout.addWidget(input_widget)
            elif param_type == int or param_type == 'int':
                input_widget = QSpinBox()
                input_widget.setRange(-999999, 999999)
                input_widget.setValue(int(current_value) if current_value is not None else 0)
                input_widget.valueChanged.connect(
                    lambda val, name=param_name, node=node_item: self._on_param_value_changed(node, name, val)
                )
                row_layout.addWidget(input_widget)
            elif param_type == float or param_type == 'float':
                input_widget = QDoubleSpinBox()
                input_widget.setRange(-999999.99, 999999.99)
                input_widget.setDecimals(4)
                input_widget.setValue(float(current_value) if current_value is not None else 0.0)
                input_widget.valueChanged.connect(
                    lambda val, name=param_name, node=node_item: self._on_param_value_changed(node, name, val)
                )
                row_layout.addWidget(input_widget)
            elif param_type == list or param_type == 'list':
                # 列表类型：使用 JSON 格式输入
                input_widget = QLineEdit()
                input_widget.setPlaceholderText('输入 JSON 格式，如: [1, 2, 3] 或 []')
                if current_value is not None:
                    import json
                    try:
                        input_widget.setText(json.dumps(current_value, ensure_ascii=False))
                    except:
                        input_widget.setText(str(current_value))
                else:
                    input_widget.setText("[]")
                input_widget.textChanged.connect(
                    lambda text, name=param_name, node=node_item: self._on_list_param_value_changed(node, name, text)
                )
                row_layout.addWidget(input_widget)
            elif param_type == dict or param_type == 'dict':
                # 字典类型：使用 JSON 格式输入
                input_widget = QLineEdit()
                input_widget.setPlaceholderText('输入 JSON 格式，如: {"key": "value"} 或 {}')
                if current_value is not None:
                    import json
                    try:
                        input_widget.setText(json.dumps(current_value, ensure_ascii=False))
                    except:
                        input_widget.setText(str(current_value))
                else:
                    input_widget.setText("{}")
                input_widget.textChanged.connect(
                    lambda text, name=param_name, node=node_item: self._on_dict_param_value_changed(node, name, text)
                )
                row_layout.addWidget(input_widget)
            else:  # 默认为字符串
                input_widget = QLineEdit()
                input_widget.setPlaceholderText("输入值...")
                if current_value is not None:
                    input_widget.setText(str(current_value))
                input_widget.textChanged.connect(
                    lambda text, name=param_name, node=node_item: self._on_param_value_changed(node, name, text)
                )
                row_layout.addWidget(input_widget)

            self.params_layout.addWidget(row)

    def _on_param_value_changed(self, node_item, param_name, value):
        """参数值改变时的回调"""
        node_item.param_values[param_name] = value
        print(f"节点 '{node_item.name}' 的参数 '{param_name}' 设置为: {value}")

    def _on_list_param_value_changed(self, node_item, param_name, text):
        """列表类型参数值改变时的回调"""
        try:
            import json
            if text.strip():
                value = json.loads(text)
                if isinstance(value, list):
                    node_item.param_values[param_name] = value
                    print(f"节点 '{node_item.name}' 的参数 '{param_name}' 设置为列表: {value}")
                else:
                    print(f"警告: 参数 '{param_name}' 的值不是有效的列表格式")
            else:
                node_item.param_values[param_name] = []
        except json.JSONDecodeError as e:
            # 解析失败时暂时存储原始文本，但不报错
            node_item.param_values[param_name] = text
            print(f"节点 '{node_item.name}' 的参数 '{param_name}' 输入中: {text}")

    def _on_dict_param_value_changed(self, node_item, param_name, text):
        """字典类型参数值改变时的回调"""
        try:
            import json
            if text.strip():
                value = json.loads(text)
                if isinstance(value, dict):
                    node_item.param_values[param_name] = value
                    print(f"节点 '{node_item.name}' 的参数 '{param_name}' 设置为字典: {value}")
                else:
                    print(f"警告: 参数 '{param_name}' 的值不是有效的字典格式")
            else:
                node_item.param_values[param_name] = {}
        except json.JSONDecodeError as e:
            # 解析失败时暂时存储原始文本，但不报错
            node_item.param_values[param_name] = text
            print(f"节点 '{node_item.name}' 的参数 '{param_name}' 输入中: {text}")

    def _open_path_selector(self):
        """打开数据提取路径选择对话框"""
        # 获取当前 path 值
        current_path = ""
        if hasattr(self, '_current_node_item') and self._current_node_item:
            current_path = self._current_node_item.param_values.get("path", "")

        # 打开路径选择对话框
        dialog = PathSelectorDialog(self, current_path)
        if dialog.exec() == QDialog.Accepted:
            selected_path = dialog.get_selected_path()
            if selected_path and hasattr(self, '_current_node_item'):
                # 更新节点的 path 参数值
                self._current_node_item.param_values["path"] = selected_path
                # 刷新参数面板
                self._setup_param_inputs(self._current_node_item)
                print(f"数据提取路径已设置为: {selected_path}")


    def _open_regex_generator(self, node_item):
        """打开正则表达式生成对话框，并将结果保存到节点参数"""
        # 获取当前的 pattern 值
        current_pattern = node_item.param_values.get("pattern", "")

        # 打开正则表达式生成对话框
        dialog = RegexGeneratorDialog(self, current_pattern)
        if dialog.exec() == QDialog.Accepted:
            selected_pattern = dialog.get_selected_regex()
            if selected_pattern:
                # 将结果保存到节点的 param_values 中
                node_item.param_values["pattern"] = selected_pattern
                # 刷新参数面板以显示结果
                self._setup_param_inputs(node_item)
                print(f"正则表达式已设置为：{selected_pattern}")


    def _open_file_picker_dialog(self, node_item):
        """打开文件选择对话框，并将结果保存到节点参数"""
        # 获取当前的文件过滤器
        file_filter = node_item.param_values.get("file_filter", "全部文件 (*)")
        if not file_filter:
            file_filter = "全部文件 (*)"

        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            file_filter
        )

        if file_path:
            # 将结果保存到节点的 param_values 中
            node_item.param_values["selected_file_path"] = file_path
            # 更新文件过滤器（如果用户修改了）
            current_filter = node_item.param_values.get("file_filter", "")
            # 刷新参数面板以显示结果
            self._setup_param_inputs(node_item)
            print(f"文件选择器已选择: {file_path}")

    def _open_folder_picker_dialog(self, node_item):
        """打开文件夹选择对话框，并将结果保存到节点参数"""
        # 打开文件夹选择对话框
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "选择文件夹",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder_path:
            # 将结果保存到节点的 param_values 中
            node_item.param_values["folder_path"] = folder_path
            # 刷新参数面板以显示结果
            self._setup_param_inputs(node_item)
            print(f"文件夹选择器已选择: {folder_path}")

    def get_all_nodes(self):
        from core.graphics.simple_node_item import SimpleNodeItem
        return [item for item in self.scene.items() if isinstance(item, SimpleNodeItem)]

    def run_graph(self):
        """执行图表"""
        from core.graphics.simple_node_item import SimpleNodeItem
        from core.graphics.loop_node_item import LoopNodeItem
        from core.engine.graph_executor import execute_graph_embedded
        from core.engine.loop_executor import execute_graph_with_loops
        from core.engine.thread_executor import execute_multithreaded_node

        all_items = self.scene.items()
        nodes = [item for item in all_items if isinstance(item, SimpleNodeItem)]
        loop_nodes = [item for item in all_items if isinstance(item, LoopNodeItem)]
        thread_nodes = [item for item in all_items if isinstance(item, MultithreadNodeItem)]

        all_special = loop_nodes + thread_nodes

        if thread_nodes and not loop_nodes:
            # 只有多线程节点
            all_nodes = list(nodes)
            for tn in thread_nodes:
                tn.reset_execution_state()
            for node in nodes:
                node.result = None
                node.reset_status()
            from utils.console_stream import colored_print
            colored_print("=" * 50, "system")
            colored_print(f"检测到 {len(thread_nodes)} 个多线程处理节点，使用多线程执行模式...", "info")
            for tn in thread_nodes:
                execute_multithreaded_node(tn, all_nodes)
            colored_print("运行完成！", "success")
            colored_print("=" * 50, "system")
        elif loop_nodes:
            # 有循环节点（可能同时有多线程节点，暂由循环执行器处理普通节点）
            print(f"检测到 {len(loop_nodes)} 个循环节点，使用循环执行模式...")
            execute_graph_with_loops(nodes, loop_nodes)
            # 额外执行多线程节点
            if thread_nodes:
                all_nodes = list(nodes)
                for tn in thread_nodes:
                    execute_multithreaded_node(tn, all_nodes)
        else:
            execute_graph_embedded(nodes)

    def stop_graph(self):
        print("已发送停止信号。")

    def save_to_json(self):
        """保存图表为 JSON 文件，弹出对话框选择路径和命名"""
        # 弹出保存文件对话框
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "保存图表为 JSON",
            "flow_chart.json",  # 默认文件名
            "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return  # 用户取消了对话框

        # 确保文件扩展名为 .json
        if not filepath.endswith('.json'):
            filepath += '.json'

        # 收集图表数据
        graph_data = {"nodes": [], "connections": [], "groups": [], "loop_nodes": [], "thread_nodes": []}

        # 导入 NodeGroup
        from core.graphics.node_group import NodeGroup
        from core.graphics.loop_node_item import LoopNodeItem
        
        # 用于记录节点ID
        node_ids = set()
        
        for item in self.scene.items():
            if isinstance(item, SimpleNodeItem):
                node_ids.add(item.node_id)
                node_data = {
                    "id": item.node_id,
                    "type": item.name,
                    "x": item.x(),
                    "y": item.y()
                }
                # 保存参数值
                if hasattr(item, 'param_values') and item.param_values:
                    node_data["param_values"] = item.param_values
                graph_data["nodes"].append(node_data)
            elif isinstance(item, ConnectionItem) and item.end_port:
                graph_data["connections"].append({
                    "from_node": item.start_port.parent_node.node_id,
                    "from_port": item.start_port.port_name,
                    "to_node": item.end_port.parent_node.node_id,
                    "to_port": item.end_port.port_name
                })
            elif isinstance(item, NodeGroup):
                # 保存组信息
                group_data = {
                    "name": item.group_name,
                    "node_ids": [node.node_id for node in item.nodes]
                }
                graph_data["groups"].append(group_data)
            elif isinstance(item, LoopNodeItem):
                # 保存循环节点
                loop_data = {
                    "id": item.node_id,
                    "type": "loop",
                    "loop_type": item.loop_type,
                    "loop_name": item.loop_name,
                    "x": item.x(),
                    "y": item.y(),
                    "range_start": item.range_start,
                    "range_end": item.range_end,
                    "range_step": item.range_step,
                    "list_data": item.list_data,
                    "inner_nodes": []
                }
                # 保存循环内部的节点
                for inner_node in item.nodes:
                    inner_node_data = {
                        "id": inner_node.node_id,
                        "type": inner_node.name,
                        "x": inner_node.x(),
                        "y": inner_node.y()
                    }
                    if hasattr(inner_node, 'param_values') and inner_node.param_values:
                        inner_node_data["param_values"] = inner_node.param_values
                    loop_data["inner_nodes"].append(inner_node_data)
                    node_ids.add(inner_node.node_id)
                graph_data["loop_nodes"].append(loop_data)
            elif isinstance(item, MultithreadNodeItem):
                # 保存多线程节点
                thread_data = {
                    "id": item.node_id,
                    "type": "multithread",
                    "node_name": item.node_name,
                    "x": item.x(),
                    "y": item.y(),
                    "input_list": item.input_list,
                    "thread_count": item.thread_count,
                    "return_order": item.return_order,
                }
                graph_data["thread_nodes"].append(thread_data)

        # 保存到文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=4)
            print(f"图表已保存到: {filepath}")
            QMessageBox.information(self, "保存成功", f"图表已成功保存到:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件时出错:\n{e}")
            print(f"保存图表失败: {e}")

    def load_from_json(self, mode="overwrite"):
        """从 JSON 文件加载图表
        
        Args:
            mode: 加载模式
                - "overwrite": 覆盖加载，清空当前画布后加载
                - "increment": 增量加载，保留当前内容，在空白位置添加
        """
        filepath, _ = QFileDialog.getOpenFileName(
            self, "加载 JSON 文件", "", "JSON Files (*.json);;All Files (*)"
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                graph_data = json.load(f)

            # 检测是否是组JSON文件（有 group_name 但没有 groups 字段）
            is_group_file = "group_name" in graph_data and "groups" not in graph_data

            # 覆盖模式：清空当前场景
            if mode == "overwrite":
                self.scene.clear()

            # 计算偏移量（增量模式下使用）
            offset_x, offset_y = 0, 0
            if mode == "increment":
                # 获取当前画布中所有节点的边界
                current_nodes = [item for item in self.scene.items() if isinstance(item, SimpleNodeItem)]
                current_groups = [item for item in self.scene.items() if isinstance(item, NodeGroup)] if 'NodeGroup' in dir() else []
                
                # 获取当前画布内容的最右边和最下边位置
                max_right = 0
                max_bottom = 0
                for node in current_nodes:
                    rect = node.sceneBoundingRect()
                    max_right = max(max_right, rect.right())
                    max_bottom = max(max_bottom, rect.bottom())
                for group in current_groups:
                    rect = group.sceneBoundingRect()
                    max_right = max(max_right, rect.right())
                    max_bottom = max(max_bottom, rect.bottom())
                
                # 计算新内容应该放置的偏移量（右边+50间距）
                offset_x = max_right + 100 if max_right > 0 else 0
                offset_y = 0

            # 创建节点
            node_map = {}  # id -> node对象
            new_nodes = []  # 新创建的节点列表（用于增量加载时定位）

            for node_data in graph_data.get("nodes", []):
                node_id = node_data.get("id")
                node_type = node_data.get("type")
                x = node_data.get("x", 0) + offset_x
                y = node_data.get("y", 0) + offset_y

                if node_type in LOCAL_NODE_LIBRARY:
                    func = LOCAL_NODE_LIBRARY[node_type]
                    node = SimpleNodeItem(node_type, func, x=x, y=y)
                    self.scene.addItem(node)
                    node.setup_ports()
                    
                    # 加载参数值
                    param_values = node_data.get("param_values", {})
                    if param_values:
                        node.param_values.update(param_values)
                    
                    node_map[node_id] = node
                    new_nodes.append(node)

            # 加载循环节点
            from core.graphics.loop_node_item import LoopNodeItem, RangeLoopNodeItem, ListLoopNodeItem
            for loop_data in graph_data.get("loop_nodes", []):
                loop_id = loop_data.get("id")
                loop_type = loop_data.get("loop_type")
                loop_name = loop_data.get("loop_name")
                x = loop_data.get("x", 0) + offset_x
                y = loop_data.get("y", 0) + offset_y

                # 根据循环类型创建对应的节点
                try:
                    if loop_type == LoopNodeItem.LOOP_TYPE_RANGE:
                        loop_node = RangeLoopNodeItem(name=loop_name, x=x, y=y)
                    elif loop_type == LoopNodeItem.LOOP_TYPE_LIST:
                        loop_node = ListLoopNodeItem(name=loop_name, x=x, y=y)
                    else:
                        # 未知类型，默认为区间循环
                        loop_node = RangeLoopNodeItem(name=loop_name, x=x, y=y)
                except Exception as e:
                    print(f"警告：创建循环节点失败 '{loop_name}': {e}")
                    continue
                
                self.scene.addItem(loop_node)

                # 恢复循环配置（带数据验证）
                try:
                    range_start = loop_data.get("range_start", 0)
                    range_end = loop_data.get("range_end", 10)
                    range_step = loop_data.get("range_step", 1)
                    list_data = loop_data.get("list_data", '[]')
                    
                    # 验证并设置区间循环参数
                    if isinstance(loop_node, RangeLoopNodeItem):
                        loop_node._range_start = int(range_start) if range_start is not None else 0
                        loop_node._range_end = int(range_end) if range_end is not None else 10
                        loop_node._range_step = int(range_step) if range_step is not None and range_step != 0 else 1
                    
                    # 验证并设置 List 循环参数
                    elif isinstance(loop_node, ListLoopNodeItem):
                        if isinstance(list_data, list):
                            # 如果已经是列表，直接转换为 JSON
                            loop_node._list_data = json.dumps(list_data, ensure_ascii=False)
                        elif isinstance(list_data, str):
                            # 验证 JSON 格式
                            try:
                                json.loads(list_data)
                                loop_node._list_data = list_data
                            except json.JSONDecodeError:
                                print(f"警告：循环节点 '{loop_name}' 的列表数据格式无效，使用默认值")
                                loop_node._list_data = '[]'
                        else:
                            print(f"警告：循环节点 '{loop_name}' 的列表数据类型无效，使用默认值")
                            loop_node._list_data = '[]'
                except (ValueError, TypeError) as e:
                    print(f"警告：恢复循环节点 '{loop_name}' 配置失败：{e}")
                
                node_map[loop_id] = loop_node
                
                # 加载循环内部的节点
                for inner_data in loop_data.get("inner_nodes", []):
                    inner_id = inner_data.get("id")
                    inner_type = inner_data.get("type")
                    inner_x = inner_data.get("x", 0)
                    inner_y = inner_data.get("y", 0)
                    
                    if inner_type in LOCAL_NODE_LIBRARY:
                        func = LOCAL_NODE_LIBRARY[inner_type]
                        inner_node = SimpleNodeItem(inner_type, func, x=inner_x, y=inner_y)
                        loop_node.add_node(inner_node)
                        self.scene.addItem(inner_node)
                        inner_node.setup_ports()
                        
                        # 加载参数值
                        param_values = inner_data.get("param_values", {})
                        if param_values:
                            inner_node.param_values.update(param_values)
                        
                        node_map[inner_id] = inner_node

            # 加载多线程节点
            for thread_data in graph_data.get("thread_nodes", []):
                thread_id = thread_data.get("id")
                node_name = thread_data.get("node_name", "多线程处理")
                x = thread_data.get("x", 0) + offset_x
                y = thread_data.get("y", 0) + offset_y
                try:
                    thread_node = MultithreadNodeItem(name=node_name, x=x, y=y)
                    thread_node.input_list = thread_data.get("input_list", "[]")
                    thread_node.thread_count = thread_data.get("thread_count", 4)
                    thread_node.return_order = thread_data.get("return_order", "按输入顺序")
                    self.scene.addItem(thread_node)
                    node_map[thread_id] = thread_node
                except Exception as e:
                    print(f"警告：创建多线程节点失败 '{node_name}': {e}")

            # 创建连接
            for conn_data in graph_data.get("connections", []):
                from_node_id = conn_data.get("from_node")
                to_node_id = conn_data.get("to_node")
                from_port_name = conn_data.get("from_port")
                to_port_name = conn_data.get("to_port")

                if from_node_id in node_map and to_node_id in node_map:
                    from_node = node_map[from_node_id]
                    to_node = node_map[to_node_id]

                    # 查找对应的端口
                    from_port = None
                    to_port = None

                    for port in from_node.output_ports:
                        if port.port_name == from_port_name:
                            from_port = port
                            break

                    for port in to_node.input_ports:
                        if port.port_name == to_port_name:
                            to_port = port
                            break

                    if from_port and to_port:
                        conn = ConnectionItem(from_port, to_port)
                        self.scene.addItem(conn)
                        conn.finalize_connection(to_port)

            # 创建节点组
            from core.graphics.node_group import NodeGroup
            groups_count = 0
            new_groups = []  # 新创建的组列表
            
            # 如果是组JSON文件，创建一个包含所有节点的组
            if is_group_file:
                group_name = graph_data.get("group_name", "组")
                all_nodes = list(node_map.values())
                if all_nodes:
                    group = NodeGroup(nodes=all_nodes, name=group_name)
                    self.scene.addItem(group)
                    groups_count = 1
                    new_groups.append(group)
            else:
                # 普通图表文件，按 groups 字段创建组
                for group_data in graph_data.get("groups", []):
                    group_name = group_data.get("name", "组")
                    node_ids = group_data.get("node_ids", [])
                    
                    # 获取组内的节点
                    group_nodes = [node_map[nid] for nid in node_ids if nid in node_map]
                    
                    if group_nodes:
                        group = NodeGroup(nodes=group_nodes, name=group_name)
                        self.scene.addItem(group)
                        groups_count += 1
                        new_groups.append(group)

            # 增量加载时，将视图焦点定位到新加载的内容
            if mode == "increment" and new_nodes:
                # 计算新内容的边界
                first_node = new_nodes[0]
                view_rect = first_node.sceneBoundingRect()
                for node in new_nodes[1:]:
                    view_rect = view_rect.united(node.sceneBoundingRect())
                for group in new_groups:
                    view_rect = view_rect.united(group.sceneBoundingRect())
                
                # 添加边距
                view_rect.adjust(-50, -50, 50, 50)
                
                # 将视图中心移动到新内容
                self.view.centerOn(view_rect.center())
                # 适当缩放以确保新内容可见
                self.view.fitInView(view_rect, Qt.KeepAspectRatio)
                # 如果缩放太小，恢复到合适的缩放级别
                if self.view.transform().m11() < 0.5:
                    self.view.resetTransform()
                    self.view.scale(1.0, 1.0)
                    self.view.centerOn(view_rect.center())

            print(f"已从 {filepath} 加载图表（{'覆盖' if mode == 'overwrite' else '增量'}模式）")
            msg = f"已成功加载图表，共 {len(node_map)} 个节点"
            if groups_count > 0:
                msg += f"，{groups_count} 个组"
            QMessageBox.information(self, "加载成功", msg)

        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载 JSON 文件失败:\n{e}")
            print(f"加载图表失败: {e}")

    def _open_package_manager(self):
        """打开依赖包管理器"""
        try:
            from core.engine.embedded_executor import get_executor
            executor = get_executor()
            
            dialog = PackageManagerDialog(self, executor)
            dialog.exec()
            
        except RuntimeError as e:
            # 嵌入式 Python 未安装
            reply = QMessageBox.question(
                self, "环境未初始化",
                f"嵌入式 Python 环境未初始化。\n\n{e}\n\n是否立即初始化？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._setup_embedded_python()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开包管理器失败:\n{e}")

    def _open_export_plugin_dialog(self):
        """打开节点插件导出对话框"""
        # 检查是否有自定义节点
        if not CUSTOM_CATEGORIES:
            QMessageBox.information(
                self, "提示",
                "当前没有自定义节点可以导出。\n\n请先创建自定义节点。"
            )
            return
        
        dialog = NodePluginExportDialog(self)
        if dialog.exec() == QDialog.Accepted:
            print("节点插件导出完成。")

    def _open_import_plugin_dialog(self):
        """打开节点插件导入对话框"""
        # 尝试获取嵌入式 Python 执行器（用于安装依赖）
        executor = None
        try:
            from core.engine.embedded_executor import get_executor
            executor = get_executor()
        except RuntimeError:
            pass  # 环境未初始化时，对话框会在安装依赖时提示用户
        
        dialog = NodePluginImportDialog(self, executor=executor)
        # 连接导入完成信号，刷新节点树
        dialog.import_completed.connect(self._refresh_node_tree)
        dialog.exec()

    def _setup_embedded_python(self):
        """初始化嵌入式 Python 环境"""
        import platform
        
        # 检查平台
        if platform.system() != "Windows":
            QMessageBox.information(
                self, "平台提示",
                "嵌入式 Python 主要针对 Windows 设计。\n\n"
                f"当前平台: {platform.system()}\n"
                "在 macOS/Linux 上，建议使用系统 Python 或 pyenv 管理环境。\n\n"
                "如需在 Windows 上使用，请在 Windows 环境下运行此功能。"
            )
            return
        
        reply = QMessageBox.question(
            self, "初始化嵌入式 Python",
            "这将下载并配置嵌入式 Python 环境（约 15-20MB）。\n"
            "安装后可在节点中使用第三方库（如 requests、pandas 等）。\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 显示进度对话框
        from PySide6.QtWidgets import QProgressDialog
        
        progress = QProgressDialog("正在初始化嵌入式 Python...", "取消", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setWindowTitle("初始化中")
        progress.show()
        
        # 在后台线程中执行初始化
        from PySide6.QtCore import QThread, Signal
        
        class SetupThread(QThread):
            progress_signal = Signal(str, int)
            finished_signal = Signal(bool, str)
            
            def run(self):
                try:
                    from utils.setup_embedded_python import EmbeddedPythonSetup
                    
                    def progress_callback(message, percent):
                        self.progress_signal.emit(message, percent)
                    
                    setup = EmbeddedPythonSetup(progress_callback=progress_callback)
                    success = setup.install()
                    
                    if success:
                        self.finished_signal.emit(True, "初始化完成！")
                    else:
                        self.finished_signal.emit(False, "初始化失败，请查看控制台输出。")
                        
                except Exception as e:
                    self.finished_signal.emit(False, str(e))
        
        self.setup_thread = SetupThread()
        self.setup_thread.progress_signal.connect(
            lambda msg, pct: (progress.setLabelText(msg), progress.setValue(pct))
        )
        self.setup_thread.finished_signal.connect(
            lambda success, msg: self._on_setup_finished(success, msg, progress)
        )
        self.setup_thread.start()

    def _on_setup_finished(self, success: bool, message: str, progress_dialog):
        """初始化完成回调"""
        progress_dialog.close()
        
        if success:
            QMessageBox.information(self, "成功", message)
            print("嵌入式 Python 环境初始化成功！")
        else:
            QMessageBox.critical(self, "失败", f"初始化失败:\n{message}")
            print(f"嵌入式 Python 环境初始化失败: {message}")
        
        # 清理线程引用
        self.setup_thread = None

    def _init_theme(self):
        """初始化主题设置"""
        # 从设置加载主题
        saved_theme = settings.get("ui.theme", "dark")
        if saved_theme in theme_manager.get_theme_names():
            theme_manager.set_theme(saved_theme)
        # 应用主题样式
        self._apply_theme()

    def _apply_theme(self):
        """应用当前主题到整个应用"""
        # 应用 QSS 样式表
        self.setStyleSheet(theme_manager.get_stylesheet())
        # 更新画布背景
        self._update_canvas_background()

    def _update_canvas_background(self):
        """更新画布背景颜色"""
        bg_color = theme_manager.get_color("canvas_bg")
        self.scene.setBackgroundBrush(QColor(bg_color))

    def _get_theme_icon(self) -> str:
        """获取当前主题的图标"""
        return theme_manager.get_theme_info()["icon"]

    def _toggle_theme(self):
        """切换主题"""
        new_theme = theme_manager.toggle_theme()
        # 保存到设置
        settings.set("ui.theme", new_theme)
        settings.save()
        # 更新按钮图标和提示
        self.theme_action.setText(self._get_theme_icon() + " 切换主题")
        self.theme_action.setToolTip(f"当前主题: {theme_manager.get_theme_info()['name']}，点击切换")
        print(f"主题已切换为: {theme_manager.get_theme_info()['name']}")

    def _on_theme_changed(self, theme_name: str):
        """主题改变时的回调"""
        self._apply_theme()
        # 通知所有图形项更新主题
        self._update_graphics_theme()

    def _update_graphics_theme(self):
        """更新所有图形项的主题颜色"""
        # 更新所有节点的颜色
        for item in self.scene.items():
            if hasattr(item, 'update_theme'):
                item.update_theme()
        # 刷新视图
        self.scene.update()

    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 断开 scene 的信号连接，防止访问已销毁的 C++ 对象
        try:
            self.scene.selectionChanged.disconnect(self.on_selection_changed)
        except (RuntimeError, TypeError):
            pass  # 已经断开则忽略
        
        # 恢复标准输出
        sys.stdout = sys.__stdout__
        
        # 调用父类方法
        super().closeEvent(event)
