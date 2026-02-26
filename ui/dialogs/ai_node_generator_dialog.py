"""AI生成自定义节点对话框

用户通过填写参数设定、核心需求、输出要求，
生成提示词后交给AI大模型，再将返回的代码粘贴生成节点。
"""

import ast
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPlainTextEdit, QPushButton, QComboBox, QMessageBox, 
    QApplication, QScrollArea, QWidget, QFrame, QGroupBox,
    QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.nodes.node_library import (
    LOCAL_NODE_LIBRARY, add_node_to_library, 
    remove_node_from_library, CUSTOM_CATEGORIES
)
from ui.dialogs.category_dialog import CategorySelectDialog


# 默认内置提示词模板
DEFAULT_PROMPT_TEMPLATE = """请根据输入的参数设定、核心需求描述、最终输出结果要求，生成一个python函数代码，代码格式参考标准节点代码输出模板进行生成，返回结果仅需要包含：
1.函数代码本身；
2.需要安装的第三方库名称；

标准节点代码输出模板：
def function_name(save_path: str, file_name: str) -> None:
    \"\"\"
    (函数的标准说明注释)
    生成填充随机数的Excel文件并保存到指定路径
    
    参数:
        save_path (str): 文件保存路径（如 "./excel_files"）
        file_name (str): 文件名（需包含.xlsx后缀，如 "random_data.xlsx"）

    输出：在本地保存一个xlsx文件
    \"\"\"
    # 模块引入部分使用函数内部引用
    import os
    import random
    from openpyxl import Workbook

    # 核心算法部分
    xxxxxxxxxx...

    # 函数返回部分（如果需要输出确定形式、标准结果的值）
    return xxxx

---

用户输入信息如下：

【参数设定】
{parameters}

【核心需求描述】
{requirement}

【最终输出结果要求】
{output_requirement}

请生成符合要求的Python函数代码。"""


# 参数类型选项
PARAM_TYPES = [
    ("str", "字符串 (str)"),
    ("int", "整数 (int)"),
    ("float", "浮点数 (float)"),
    ("bool", "布尔值 (bool)"),
    ("list", "列表 (list)"),
    ("dict", "字典 (dict)"),
    ("any", "任意类型 (any)"),
]


class ParameterInputRow(QWidget):
    """参数输入行组件"""
    
    removed = Signal(object)  # 删除信号，传递自身引用
    
    def __init__(self, parent=None, row_num=1):
        super().__init__(parent)
        self.row_num = row_num
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)
        
        # 序号标签
        self.num_label = QLabel(f"{self.row_num}.")
        self.num_label.setFixedWidth(20)
        self.num_label.setStyleSheet("color: #888;")
        layout.addWidget(self.num_label)
        
        # 参数名称输入
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("参数名（如：file_path）")
        self.name_edit.setStyleSheet(
            "background-color: #2b2b2b; color: #a9b7c6; "
            "padding: 5px; border: 1px solid #555; border-radius: 3px;"
        )
        layout.addWidget(self.name_edit, 2)
        
        # 参数类型下拉选择
        self.type_combo = QComboBox()
        self.type_combo.addItems([label for _, label in PARAM_TYPES])
        self.type_combo.setStyleSheet(
            "background-color: #2b2b2b; color: #a9b7c6; "
            "padding: 5px; border: 1px solid #555; border-radius: 3px;"
        )
        layout.addWidget(self.type_combo, 1)
        
        # 参数说明输入
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("参数说明（可选）")
        self.desc_edit.setStyleSheet(
            "background-color: #2b2b2b; color: #a9b7c6; "
            "padding: 5px; border: 1px solid #555; border-radius: 3px;"
        )
        layout.addWidget(self.desc_edit, 3)
        
        # 删除按钮
        self.remove_btn = QPushButton("×")
        self.remove_btn.setFixedSize(28, 28)
        self.remove_btn.setStyleSheet(
            "background-color: #dc3545; color: white; "
            "border: none; border-radius: 3px; font-weight: bold;"
        )
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.clicked.connect(self._on_remove)
        layout.addWidget(self.remove_btn)
    
    def _on_remove(self):
        self.removed.emit(self)
    
    def set_row_num(self, num):
        """更新序号"""
        self.row_num = num
        self.num_label.setText(f"{num}.")
    
    def get_data(self):
        """获取参数数据"""
        name = self.name_edit.text().strip()
        if not name:
            return None
        
        type_index = self.type_combo.currentIndex()
        type_value = PARAM_TYPES[type_index][0]
        description = self.desc_edit.text().strip()
        
        return {
            "name": name,
            "type": type_value,
            "description": description
        }


class AINodeGeneratorDialog(QDialog):
    """AI节点生成器对话框"""
    
    # 信号：节点创建成功时发射
    node_created = Signal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI生成自定义节点")
        self.resize(800, 700)
        self.generated_func = None
        self.generated_name = None
        self.selected_category_name = None
        
        # 存储参数输入行
        self.param_rows = []
        
        self._setup_ui()
        self._add_default_param_row()
    
    def _setup_ui(self):
        """设置UI布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        # 滚动内容容器
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(0, 0, 10, 0)
        
        # ========== 1. 参数设定区域 ==========
        param_group = QGroupBox("📋 参数设定（输入参数）")
        param_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #4CAF50; "
            "border: 1px solid #4CAF50; border-radius: 5px; margin-top: 10px; "
            "padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        param_layout = QVBoxLayout(param_group)
        param_layout.setSpacing(8)
        
        # 参数列表容器
        self.params_container = QWidget()
        self.params_layout = QVBoxLayout(self.params_container)
        self.params_layout.setContentsMargins(0, 0, 0, 0)
        self.params_layout.setSpacing(4)
        self.params_layout.addStretch()
        param_layout.addWidget(self.params_container)
        
        # 添加参数按钮
        add_param_btn = QPushButton("+ 添加参数")
        add_param_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 8px; "
            "border: none; border-radius: 3px; font-weight: bold;"
        )
        add_param_btn.setCursor(Qt.PointingHandCursor)
        add_param_btn.clicked.connect(self._add_param_row)
        param_layout.addWidget(add_param_btn)
        
        scroll_layout.addWidget(param_group)
        
        # ========== 2. 核心需求描述区域 ==========
        req_group = QGroupBox("🎯 核心需求描述")
        req_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #2196F3; "
            "border: 1px solid #2196F3; border-radius: 5px; margin-top: 10px; "
            "padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        req_layout = QVBoxLayout(req_group)
        
        self.requirement_edit = QPlainTextEdit()
        self.requirement_edit.setPlaceholderText(
            "请详细描述节点需要完成的核心任务...\n"
            "例如：读取一个CSV文件，对其中的数值列进行归一化处理，"
            "并将结果保存为新的CSV文件"
        )
        self.requirement_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; "
            "border: 1px solid #444; border-radius: 3px; padding: 8px;"
        )
        self.requirement_edit.setMinimumHeight(100)
        req_layout.addWidget(self.requirement_edit)
        
        scroll_layout.addWidget(req_group)
        
        # ========== 3. 输出要求区域 ==========
        output_group = QGroupBox("📤 最终输出结果要求（可选）")
        output_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #FF9800; "
            "border: 1px solid #FF9800; border-radius: 5px; margin-top: 10px; "
            "padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        output_layout = QVBoxLayout(output_group)
        
        self.output_edit = QPlainTextEdit()
        self.output_edit.setPlaceholderText(
            "描述节点执行后需要返回的结果类型和格式...\n"
            "例如：返回处理后的DataFrame对象\n"
            "如果不需返回值（仅执行操作），可留空或填写'无返回值'"
        )
        self.output_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; "
            "border: 1px solid #444; border-radius: 3px; padding: 8px;"
        )
        self.output_edit.setMinimumHeight(80)
        output_layout.addWidget(self.output_edit)
        
        scroll_layout.addWidget(output_group)
        
        # ========== 4. 提示词生成区域 ==========
        prompt_group = QGroupBox("🤖 AI提示词（点击复制后粘贴给AI大模型）")
        prompt_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #9C27B0; "
            "border: 1px solid #9C27B0; border-radius: 5px; margin-top: 10px; "
            "padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        prompt_layout = QVBoxLayout(prompt_group)
        
        self.prompt_preview = QPlainTextEdit()
        self.prompt_preview.setPlaceholderText('点击"生成提示词"按钮后，此处将显示完整的AI提示词...')
        self.prompt_preview.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; "
            "border: 1px solid #444; border-radius: 3px; padding: 8px;"
        )
        self.prompt_preview.setMinimumHeight(150)
        self.prompt_preview.setReadOnly(True)
        prompt_layout.addWidget(self.prompt_preview)
        
        # 提示词操作按钮
        prompt_btn_layout = QHBoxLayout()
        
        self.gen_prompt_btn = QPushButton("🔄 生成提示词")
        self.gen_prompt_btn.setStyleSheet(
            "background-color: #9C27B0; color: white; padding: 10px 20px; "
            "border: none; border-radius: 3px; font-weight: bold; font-size: 13px;"
        )
        self.gen_prompt_btn.setCursor(Qt.PointingHandCursor)
        self.gen_prompt_btn.clicked.connect(self._generate_prompt)
        prompt_btn_layout.addWidget(self.gen_prompt_btn)
        
        self.copy_prompt_btn = QPushButton("📋 复制提示词")
        self.copy_prompt_btn.setStyleSheet(
            "background-color: #607D8B; color: white; padding: 10px 20px; "
            "border: none; border-radius: 3px; font-weight: bold; font-size: 13px;"
        )
        self.copy_prompt_btn.setCursor(Qt.PointingHandCursor)
        self.copy_prompt_btn.clicked.connect(self._copy_prompt)
        self.copy_prompt_btn.setEnabled(False)
        prompt_btn_layout.addWidget(self.copy_prompt_btn)
        
        prompt_layout.addLayout(prompt_btn_layout)
        
        scroll_layout.addWidget(prompt_group)
        
        # ========== 5. AI返回结果粘贴区域 ==========
        result_group = QGroupBox("📥 AI返回结果粘贴区（将AI生成的代码粘贴到这里）")
        result_group.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #00BCD4; "
            "border: 1px solid #00BCD4; border-radius: 5px; margin-top: 10px; "
            "padding-top: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        result_layout = QVBoxLayout(result_group)
        
        self.ai_result_edit = QPlainTextEdit()
        self.ai_result_edit.setPlaceholderText(
            "将AI大模型返回的Python代码粘贴到这里...\n"
            "代码应该包含完整的函数定义和必要的导入语句"
        )
        self.ai_result_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; "
            "border: 1px solid #444; border-radius: 3px; padding: 8px;"
        )
        self.ai_result_edit.setMinimumHeight(150)
        result_layout.addWidget(self.ai_result_edit)
        
        # 节点名称输入
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("节点显示名称："))
        self.node_name_edit = QLineEdit()
        self.node_name_edit.setPlaceholderText("输入自定义节点名称（可选，留空则使用函数名）")
        self.node_name_edit.setStyleSheet(
            "background-color: #2b2b2b; color: #a9b7c6; "
            "padding: 5px; border: 1px solid #555; border-radius: 3px;"
        )
        name_layout.addWidget(self.node_name_edit, 1)
        result_layout.addLayout(name_layout)
        
        scroll_layout.addWidget(result_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)
        
        # ========== 底部按钮区域 ==========
        bottom_layout = QHBoxLayout()
        
        # 清空按钮
        clear_btn = QPushButton("🗑️ 清空所有")
        clear_btn.setStyleSheet(
            "background-color: #f44336; color: white; padding: 10px 20px; "
            "border: none; border-radius: 3px;"
        )
        clear_btn.clicked.connect(self._clear_all)
        bottom_layout.addWidget(clear_btn)
        
        bottom_layout.addStretch()
        
        # 粘贴代码按钮
        paste_btn = QPushButton("📋 粘贴代码")
        paste_btn.setStyleSheet(
            "background-color: #607D8B; color: white; padding: 10px 20px; "
            "border: none; border-radius: 3px;"
        )
        paste_btn.clicked.connect(self._paste_code)
        bottom_layout.addWidget(paste_btn)
        
        # 生成节点按钮
        self.create_node_btn = QPushButton("✅ 生成节点")
        self.create_node_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; padding: 10px 30px; "
            "border: none; border-radius: 3px; font-weight: bold; font-size: 14px;"
        )
        self.create_node_btn.setCursor(Qt.PointingHandCursor)
        self.create_node_btn.clicked.connect(self._create_node)
        bottom_layout.addWidget(self.create_node_btn)
        
        # 取消按钮
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.setStyleSheet(
            "background-color: #757575; color: white; padding: 10px 20px; "
            "border: none; border-radius: 3px;"
        )
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(bottom_layout)
    
    def _add_default_param_row(self):
        """添加默认的参数行"""
        self._add_param_row()
    
    def _add_param_row(self):
        """添加参数输入行"""
        row = ParameterInputRow(self, len(self.param_rows) + 1)
        row.removed.connect(self._remove_param_row)
        
        # 插入到stretch之前
        self.params_layout.insertWidget(
            self.params_layout.count() - 1, row
        )
        self.param_rows.append(row)
    
    def _remove_param_row(self, row):
        """删除参数输入行"""
        if row in self.param_rows:
            self.param_rows.remove(row)
            row.deleteLater()
            
            # 重新编号
            for i, r in enumerate(self.param_rows, 1):
                r.set_row_num(i)
    
    def _get_parameters_text(self):
        """获取格式化的参数描述文本"""
        params = []
        for row in self.param_rows:
            data = row.get_data()
            if data:
                param_desc = f"- {data['name']} ({data['type']})"
                if data['description']:
                    param_desc += f": {data['description']}"
                params.append(param_desc)
        
        if not params:
            return "无输入参数"
        
        return "\n".join(params)
    
    def _generate_prompt(self):
        """生成AI提示词"""
        parameters = self._get_parameters_text()
        requirement = self.requirement_edit.toPlainText().strip()
        output_requirement = self.output_edit.toPlainText().strip()
        
        if not requirement:
            QMessageBox.warning(self, "提示", "请填写核心需求描述！")
            return
        
        if not output_requirement:
            output_requirement = "根据核心需求确定返回值，如果不需要返回具体值则返回None"
        
        # 组装提示词
        prompt = DEFAULT_PROMPT_TEMPLATE.format(
            parameters=parameters,
            requirement=requirement,
            output_requirement=output_requirement
        )
        
        self.prompt_preview.setPlainText(prompt)
        self.copy_prompt_btn.setEnabled(True)
        
        # 自动复制到剪贴板
        clipboard = QApplication.clipboard()
        clipboard.setText(prompt)
        
        QMessageBox.information(
            self, "提示词已生成", 
            "提示词已生成并自动复制到剪贴板！\n\n"
            "请粘贴到任意AI大模型（豆包、DeepSeek、Gemini、Qwen等）获取代码。"
        )
    
    def _copy_prompt(self):
        """复制提示词到剪贴板"""
        prompt = self.prompt_preview.toPlainText()
        if not prompt:
            QMessageBox.warning(self, "提示", "请先生成提示词！")
            return
        
        clipboard = QApplication.clipboard()
        clipboard.setText(prompt)
        
        QMessageBox.information(self, "复制成功", "提示词已复制到剪贴板！")
    
    def _paste_code(self):
        """粘贴代码"""
        clipboard = QApplication.clipboard()
        code = clipboard.text()
        if code:
            self.ai_result_edit.insertPlainText(code)
        else:
            QMessageBox.warning(self, "提示", "剪贴板为空！")
    
    def _clear_all(self):
        """清空所有输入"""
        # 清空参数
        for row in self.param_rows[:]:
            self._remove_param_row(row)
        self._add_param_row()
        
        # 清空其他输入
        self.requirement_edit.clear()
        self.output_edit.clear()
        self.prompt_preview.clear()
        self.ai_result_edit.clear()
        self.node_name_edit.clear()
        
        self.copy_prompt_btn.setEnabled(False)
    
    def _validate_code(self, code):
        """验证代码，返回 (tree, func_name, error_message)"""
        if not code:
            return None, None, "代码不能为空！"
        
        # 1. 语法检查
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return None, None, f"代码存在语法错误：\n{e}"
        
        # 2. 检查是否恰好有一个顶层函数定义
        func_defs = [node for node in ast.iter_child_nodes(tree) 
                     if isinstance(node, ast.FunctionDef)]
        if len(func_defs) != 1:
            return None, None, (
                f"代码中必须定义且仅定义一个顶层函数（def），"
                f"当前找到 {len(func_defs)} 个。"
            )
        
        return tree, func_defs[0].name, None
    
    def _compile_function(self, tree, func_name, code):
        """编译函数，返回 (func, error_message)"""
        try:
            # 注意：必须提供 __builtins__，否则 import 语句在某些环境下会失败
            namespace = {'__builtins__': __builtins__}
            exec(compile(tree, "<ai_generated_node>", "exec"), namespace)
            func = namespace[func_name]
        except Exception as e:
            return None, f"代码执行失败：\n{e}"
        
        if not callable(func):
            return None, "定义的对象不是可调用函数。"
        
        # 保存源代码到函数上
        func._custom_source = code
        func._original_func_name = func_name
        
        return func, None
    
    def _create_node(self):
        """创建节点"""
        code = self.ai_result_edit.toPlainText().strip()
        
        tree, func_name, error = self._validate_code(code)
        if error:
            QMessageBox.critical(self, "代码错误", error)
            return
        
        # 获取用户自定义的节点显示名称
        custom_name = self.node_name_edit.text().strip()
        display_name = custom_name if custom_name else func_name
        
        # 检查是否与已有节点重名
        if display_name in LOCAL_NODE_LIBRARY:
            QMessageBox.critical(
                self, "命名冲突", 
                f"节点名 '{display_name}' 已存在，请修改节点名称。"
            )
            return
        
        # 编译执行
        func, error = self._compile_function(tree, func_name, code)
        if error:
            QMessageBox.critical(self, "编译错误", error)
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
            
            QMessageBox.information(
                self, "成功", 
                f"节点 '{display_name}' 已生成到分类 '{category}'！"
            )
            self.accept()
