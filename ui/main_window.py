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
from PySide6.QtGui import QAction, QTextCursor, QColor

from core.graphics.node_graphics_view import NodeGraphicsView
from core.graphics.simple_node_item import SimpleNodeItem
from core.graphics.connection_item import ConnectionItem
from core.graphics.port_item import PortItem
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
from utils.console_stream import EmittingStream
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

        load_action = QAction("📂 加载 JSON", self)
        load_action.triggered.connect(self.load_from_json)
        toolbar.addAction(load_action)

        toolbar.addSeparator()

        toolbar.addSeparator()
        
        # AI生成节点
        ai_gen_action = QAction("🤖 Ai节点模板", self)
        ai_gen_action.triggered.connect(self._open_ai_node_generator)
        toolbar.addAction(ai_gen_action)
        
        toolbar.addSeparator()
        
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
            node = SimpleNodeItem(node_name, func, x=0, y=0)
            self.scene.addItem(node)
            node.setup_ports()
            print(f"已添加节点: {node_name}")

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
                item.func = LOCAL_NODE_LIBRARY.get(new_name)
                
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

        # 控制台文本区域
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setObjectName("console")
        layout.addWidget(self.console)

        dock.setWidget(container)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        # 初始化日志流
        self._stream = EmittingStream()
        self._stream.textWritten.connect(self.normal_output)
        sys.stdout = self._stream

        # 从设置加载日志配置
        self._init_log_settings()

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

    def normal_output(self, text):
        self.console.moveCursor(QTextCursor.End)
        self.console.insertPlainText(text)
        self.console.ensureCursorVisible()

    def on_selection_changed(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            self.doc_text.clear()
            self.source_text.clear()
            self._clear_param_inputs()
            return

        item = selected_items[0]
        if hasattr(item, 'func'):  # SimpleNodeItem
            func = item.func
            doc = inspect.getdoc(func) or "该节点无注释。"
            # 自定义节点用保存的源代码
            if hasattr(func, '_custom_source'):
                source = func._custom_source
            else:
                try:
                    source = inspect.getsource(func)
                except Exception:
                    source = "无法获取源代码。"

            self.doc_text.setText(doc)
            self.source_text.setText(source)
            
            # 显示参数输入控件
            self._setup_param_inputs(item)
        else:
            self._clear_param_inputs()

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

    def get_all_nodes(self):
        from core.graphics.simple_node_item import SimpleNodeItem
        return [item for item in self.scene.items() if isinstance(item, SimpleNodeItem)]

    def run_graph(self):
        nodes = self.get_all_nodes()
        from core.engine.graph_executor import execute_graph_embedded
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
        graph_data = {"nodes": [], "connections": [], "groups": []}

        # 导入 NodeGroup
        from core.graphics.node_group import NodeGroup
        
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

        # 保存到文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=4)
            print(f"图表已保存到: {filepath}")
            QMessageBox.information(self, "保存成功", f"图表已成功保存到:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存文件时出错:\n{e}")
            print(f"保存图表失败: {e}")

    def load_from_json(self):
        """从 JSON 文件加载图表"""
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

            # 清空当前场景
            self.scene.clear()

            # 创建节点
            node_map = {}  # id -> node对象

            for node_data in graph_data.get("nodes", []):
                node_id = node_data.get("id")
                node_type = node_data.get("type")
                x = node_data.get("x", 0)
                y = node_data.get("y", 0)

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
            
            # 如果是组JSON文件，创建一个包含所有节点的组
            if is_group_file:
                group_name = graph_data.get("group_name", "组")
                all_nodes = list(node_map.values())
                if all_nodes:
                    group = NodeGroup(nodes=all_nodes, name=group_name)
                    self.scene.addItem(group)
                    groups_count = 1
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

            print(f"已从 {filepath} 加载图表")
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
