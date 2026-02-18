"""自定义节点代码编辑对话框"""

import ast
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPlainTextEdit, 
                               QPushButton, QHBoxLayout, QMessageBox, QApplication,
                               QLineEdit)
from PySide6.QtCore import Qt, Signal

from core.nodes.node_library import LOCAL_NODE_LIBRARY, add_node_to_library
from core.nodes.base_nodes import NODE_CODE_EXAMPLE
from ui.dialogs.category_dialog import CategorySelectDialog


class CustomNodeCodeDialog(QDialog):
    # 信号：节点创建成功时发射，携带节点名称和分类
    node_created = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义节点 - 代码编辑器")
        self.resize(600, 550)
        self.generated_func = None
        self.generated_name = None
        self.selected_category_name = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("请输入 Python 节点函数代码："))

        self.code_edit = QPlainTextEdit()
        self.code_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; font-family: Consolas; font-size: 13px;"
        )
        self.code_edit.setPlaceholderText(NODE_CODE_EXAMPLE)
        layout.addWidget(self.code_edit)

        # 节点名称输入框
        layout.addWidget(QLabel("节点显示名称（可选，留空则使用函数名）："))
        self.node_name_edit = QLineEdit()
        self.node_name_edit.setPlaceholderText("输入自定义节点名称...")
        self.node_name_edit.setStyleSheet(
            "background-color: #2b2b2b; color: #a9b7c6; padding: 5px; border: 1px solid #555;"
        )
        layout.addWidget(self.node_name_edit)

        btn_layout = QHBoxLayout()

        paste_btn = QPushButton("粘贴")
        paste_btn.clicked.connect(self._paste)
        btn_layout.addWidget(paste_btn)

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(clear_btn)

        gen_btn = QPushButton("生成节点")
        gen_btn.setStyleSheet("background: #4CAF50; color: white; font-weight: bold;")
        gen_btn.clicked.connect(self._generate_node)
        btn_layout.addWidget(gen_btn)

        layout.addLayout(btn_layout)

    def _paste(self):
        clipboard = QApplication.clipboard()
        self.code_edit.insertPlainText(clipboard.text())

    def _clear_all(self):
        """清空所有输入"""
        self.code_edit.clear()
        self.node_name_edit.clear()

    def _generate_node(self):
        code = self.code_edit.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "错误", "代码不能为空！")
            return

        # 1. 语法检查
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            QMessageBox.critical(
                self, "语法错误",
                f"代码存在语法错误：\n{e}\n\n标准示例：\n{NODE_CODE_EXAMPLE}"
            )
            return

        # 2. 检查是否恰好有一个顶层函数定义
        func_defs = [node for node in ast.iter_child_nodes(tree) if isinstance(node, ast.FunctionDef)]
        if len(func_defs) != 1:
            QMessageBox.critical(
                self, "结构错误",
                f"代码中必须定义且仅定义一个顶层函数（def），当前找到 {len(func_defs)} 个。\n\n标准示例：\n{NODE_CODE_EXAMPLE}"
            )
            return

        func_name = func_defs[0].name
        
        # 3. 获取用户自定义的节点显示名称
        custom_name = self.node_name_edit.text().strip()
        display_name = custom_name if custom_name else func_name

        # 4. 检查是否与已有节点重名（使用显示名称检查）
        if display_name in LOCAL_NODE_LIBRARY:
            QMessageBox.critical(self, "命名冲突", f"节点名 '{display_name}' 已存在，请修改节点名称。")
            return

        # 5. 编译执行
        try:
            namespace = {}
            exec(compile(tree, "<custom_node>", "exec"), namespace)
            func = namespace[func_name]
        except Exception as e:
            QMessageBox.critical(
                self, "执行错误",
                f"代码执行失败：\n{e}\n\n标准示例：\n{NODE_CODE_EXAMPLE}"
            )
            return

        if not callable(func):
            QMessageBox.critical(self, "错误", "定义的对象不是可调用函数。")
            return

        # 6. 弹出分类选择对话框
        dlg = CategorySelectDialog(self)
        if dlg.exec() == QDialog.Accepted:
            category = dlg.selected_category()
            if not category:
                return
            self.generated_func = func
            self.generated_name = display_name
            self.selected_category_name = category
            # 保存源代码到函数上，以便后续 inspect 可用
            func._custom_source = code
            # 保存原始函数名到函数属性（用于代码执行时找到正确的函数）
            func._original_func_name = func_name
            add_node_to_library(display_name, func, category)
            # 发射信号通知主窗口刷新节点列表
            self.node_created.emit(display_name, category)
            QMessageBox.information(self, "成功", f"节点 '{display_name}' 已生成到分类 '{category}'！")
            self.accept()
