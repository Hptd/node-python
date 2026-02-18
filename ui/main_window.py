"""主窗口UI"""

import sys
import json
import inspect
from PySide6.QtWidgets import (QMainWindow, QGraphicsScene, QDockWidget, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QTextEdit, QToolBar, QPushButton,
                               QInputDialog, QMessageBox, QApplication, QTreeWidgetItem,
                               QFileDialog, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QTextCursor

from core.graphics.node_graphics_view import NodeGraphicsView
from core.engine.graph_executor import execute_graph
from core.nodes.node_library import (NODE_LIBRARY_CATEGORIZED, LOCAL_NODE_LIBRARY,
                                      CUSTOM_CATEGORIES, add_node_to_library)
from ui.widgets.draggable_node_tree import DraggableNodeTree
from ui.dialogs.custom_node_dialog import CustomNodeCodeDialog
from utils.console_stream import EmittingStream


class SimplePyFlowWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("简易中文节点编辑器")
        self.resize(1000, 700)

        self.setup_bottom_dock()

        self.scene = QGraphicsScene()
        self.view = NodeGraphicsView(self.scene)
        self.setCentralWidget(self.view)

        self.scene.selectionChanged.connect(self.on_selection_changed)

        self.setup_toolbar()
        self.setup_left_dock()
        self.setup_right_dock()

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

    def setup_left_dock(self):
        dock = QDockWidget("📦 本地节点库", self)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        # 管理分类按钮
        cat_btn_layout = QHBoxLayout()
        add_cat_btn = QPushButton("+ 新建分类")
        add_cat_btn.setStyleSheet("background: #2196F3; color: white; border: none; padding: 4px 8px; border-radius: 3px;")
        add_cat_btn.clicked.connect(self._add_custom_category)

        cat_btn_layout.addWidget(add_cat_btn)

        custom_node_btn = QPushButton("+ 自定义节点")
        custom_node_btn.setStyleSheet("background: #FF9800; color: white; border: none; padding: 4px 8px; border-radius: 3px;")
        custom_node_btn.clicked.connect(self._open_custom_node_editor)
        cat_btn_layout.addWidget(custom_node_btn)

        layout.addLayout(cat_btn_layout)

        # 树形节点列表
        self.node_tree = DraggableNodeTree()
        self.node_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        layout.addWidget(self.node_tree)

        dock.setWidget(container)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

        self._refresh_node_tree()

    def _refresh_node_tree(self):
        self.node_tree.clear()
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
            from core.graphics.simple_node_item import SimpleNodeItem
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
        self.source_text.setStyleSheet("background-color: #2b2b2b; color: #a9b7c6; font-family: Consolas;")
        layout.addWidget(self.source_text)

        layout.addStretch()  # 添加弹性空间
        panel.setLayout(layout)
        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def setup_bottom_dock(self):
        dock = QDockWidget("💻 运行控制台", self)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #1e1e1e; color: #00FF00; font-family: Consolas;")
        dock.setWidget(self.console)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        self._stream = EmittingStream()
        self._stream.textWritten.connect(self.normal_output)
        sys.stdout = self._stream

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
            
            if param_type == bool or param_type == 'bool':
                input_widget = QCheckBox()
                input_widget.setChecked(bool(current_value) if current_value is not None else False)
                input_widget.stateChanged.connect(
                    lambda state, name=param_name, node=node_item: self._on_param_value_changed(node, name, bool(state))
                )
            elif param_type == int or param_type == 'int':
                input_widget = QSpinBox()
                input_widget.setRange(-999999, 999999)
                input_widget.setValue(int(current_value) if current_value is not None else 0)
                input_widget.valueChanged.connect(
                    lambda val, name=param_name, node=node_item: self._on_param_value_changed(node, name, val)
                )
            elif param_type == float or param_type == 'float':
                input_widget = QDoubleSpinBox()
                input_widget.setRange(-999999.99, 999999.99)
                input_widget.setDecimals(4)
                input_widget.setValue(float(current_value) if current_value is not None else 0.0)
                input_widget.valueChanged.connect(
                    lambda val, name=param_name, node=node_item: self._on_param_value_changed(node, name, val)
                )
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

    def get_all_nodes(self):
        from core.graphics.simple_node_item import SimpleNodeItem
        return [item for item in self.scene.items() if isinstance(item, SimpleNodeItem)]

    def run_graph(self):
        nodes = self.get_all_nodes()
        execute_graph(nodes)

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
        graph_data = {"nodes": [], "connections": []}

        from core.graphics.simple_node_item import SimpleNodeItem
        from core.graphics.connection_item import ConnectionItem

        for item in self.scene.items():
            if isinstance(item, SimpleNodeItem):
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

            # 清空当前场景
            self.scene.clear()

            # 创建节点
            node_map = {}  # id -> node对象
            from core.graphics.simple_node_item import SimpleNodeItem

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
            from core.graphics.connection_item import ConnectionItem
            from core.graphics.port_item import PortItem

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

            print(f"已从 {filepath} 加载图表")
            QMessageBox.information(self, "加载成功", f"已成功加载图表，共 {len(node_map)} 个节点")

        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载 JSON 文件失败:\n{e}")
            print(f"加载图表失败: {e}")
