"""自定义节点代码编辑对话框"""

import ast
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPlainTextEdit, 
                               QPushButton, QHBoxLayout, QMessageBox, QApplication,
                               QLineEdit)
from PySide6.QtCore import Qt, Signal

from core.nodes.node_library import (LOCAL_NODE_LIBRARY, add_node_to_library,
                                      remove_node_from_library, CUSTOM_CATEGORIES)
from core.nodes.base_nodes import NODE_CODE_EXAMPLE
from ui.dialogs.category_dialog import CategorySelectDialog


class CustomNodeCodeDialog(QDialog):
    # 信号：节点创建成功时发射，携带节点名称和分类
    node_created = Signal(str, str)
    # 信号：节点更新成功时发射，携带原节点名称、新节点名称和分类
    node_updated = Signal(str, str, str)
    
    def __init__(self, parent=None, edit_mode=False, original_name=None, 
                 original_code=None, original_display_name=None, original_category=None):
        super().__init__(parent)
        
        # 编辑模式参数
        self.edit_mode = edit_mode
        self.original_name = original_name  # 原节点名称
        self.original_category = original_category  # 原分类
        
        if edit_mode:
            self.setWindowTitle(f"编辑自定义节点 - {original_name}")
        else:
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
        
        # 编辑模式下预填充代码
        if edit_mode and original_code:
            self.code_edit.setPlainText(original_code)
        else:
            self.code_edit.setPlaceholderText(NODE_CODE_EXAMPLE)
        
        layout.addWidget(self.code_edit)

        # 节点名称输入框
        layout.addWidget(QLabel("节点显示名称（可选，留空则使用函数名）："))
        self.node_name_edit = QLineEdit()
        
        # 编辑模式下预填充节点名称
        if edit_mode and original_display_name:
            self.node_name_edit.setText(original_display_name)
        else:
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

        if edit_mode:
            gen_btn = QPushButton("更新节点")
            gen_btn.setStyleSheet("background: #2196F3; color: white; font-weight: bold;")
            gen_btn.clicked.connect(self._update_node)
        else:
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

    def _validate_code(self, code):
        """验证代码，返回 (tree, func_name, error_message)"""
        if not code:
            return None, None, "代码不能为空！"

        # 1. 语法检查
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return None, None, f"代码存在语法错误：\n{e}\n\n标准示例：\n{NODE_CODE_EXAMPLE}"

        # 2. 检查是否恰好有一个顶层函数定义
        func_defs = [node for node in ast.iter_child_nodes(tree) if isinstance(node, ast.FunctionDef)]
        if len(func_defs) != 1:
            return None, None, f"代码中必须定义且仅定义一个顶层函数（def），当前找到 {len(func_defs)} 个。\n\n标准示例：\n{NODE_CODE_EXAMPLE}"

        return tree, func_defs[0].name, None

    def _compile_function(self, tree, func_name, code):
        """编译函数，返回 (func, error_message)"""
        try:
            namespace = {}
            exec(compile(tree, "<custom_node>", "exec"), namespace)
            func = namespace[func_name]
        except Exception as e:
            return None, f"代码执行失败：\n{e}\n\n标准示例：\n{NODE_CODE_EXAMPLE}"

        if not callable(func):
            return None, "定义的对象不是可调用函数。"

        # 保存源代码到函数上
        func._custom_source = code
        func._original_func_name = func_name
        
        return func, None

    def _generate_node(self):
        """创建新节点"""
        code = self.code_edit.toPlainText().strip()
        
        tree, func_name, error = self._validate_code(code)
        if error:
            QMessageBox.critical(self, "错误", error)
            return

        # 获取用户自定义的节点显示名称
        custom_name = self.node_name_edit.text().strip()
        display_name = custom_name if custom_name else func_name

        # 检查是否与已有节点重名
        if display_name in LOCAL_NODE_LIBRARY:
            QMessageBox.critical(self, "命名冲突", f"节点名 '{display_name}' 已存在，请修改节点名称。")
            return

        # 编译执行
        func, error = self._compile_function(tree, func_name, code)
        if error:
            QMessageBox.critical(self, "错误", error)
            return

        # 弹出分类选择对话框
        dlg = CategorySelectDialog(self)
        if dlg.exec() == QDialog.Accepted:
            category = dlg.selected_category()
            if not category:
                return
            self.generated_func = func
            self.generated_name = display_name
            self.selected_category_name = category
            add_node_to_library(display_name, func, category)
            self.node_created.emit(display_name, category)
            QMessageBox.information(self, "成功", f"节点 '{display_name}' 已生成到分类 '{category}'！")
            self.accept()

    def _update_node(self):
        """更新现有节点（编辑模式）"""
        code = self.code_edit.toPlainText().strip()
        
        tree, func_name, error = self._validate_code(code)
        if error:
            QMessageBox.critical(self, "错误", error)
            return

        # 获取用户自定义的节点显示名称
        custom_name = self.node_name_edit.text().strip()
        display_name = custom_name if custom_name else func_name

        # 如果名称改变了，检查新名称是否已存在
        if display_name != self.original_name and display_name in LOCAL_NODE_LIBRARY:
            QMessageBox.critical(self, "命名冲突", f"节点名 '{display_name}' 已存在，请修改节点名称。")
            return

        # 编译执行
        func, error = self._compile_function(tree, func_name, code)
        if error:
            QMessageBox.critical(self, "错误", error)
            return

        # 编辑模式下，使用原分类或选择新分类
        if self.original_category:
            # 询问是否更改分类
            reply = QMessageBox.question(
                self, "更改分类", 
                f"当前分类为 '{self.original_category}'。\n是否更改分类？",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                return
            elif reply == QMessageBox.Yes:
                dlg = CategorySelectDialog(self)
                if dlg.exec() == QDialog.Accepted:
                    category = dlg.selected_category()
                    if not category:
                        return
                else:
                    return
            else:
                category = self.original_category
        else:
            # 弹出分类选择对话框
            dlg = CategorySelectDialog(self)
            if dlg.exec() == QDialog.Accepted:
                category = dlg.selected_category()
                if not category:
                    return
            else:
                return

        # 如果名称改变了，先删除旧节点
        if display_name != self.original_name:
            remove_node_from_library(self.original_name)

        # 添加/更新节点到库
        self.generated_func = func
        self.generated_name = display_name
        self.selected_category_name = category
        add_node_to_library(display_name, func, category)
        
        # 发射更新信号
        self.node_updated.emit(self.original_name, display_name, category)
        
        QMessageBox.information(self, "成功", f"节点 '{self.original_name}' 已更新为 '{display_name}'！")
        self.accept()
