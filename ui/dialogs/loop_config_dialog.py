"""循环节点配置对话框"""

import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QTextEdit, QGroupBox, QWidget,
    QFormLayout, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils.theme_manager import theme_manager


class LoopConfigDialog(QDialog):
    """循环节点配置对话框"""

    def __init__(self, loop_node=None, parent=None):
        super().__init__(parent)
        self.loop_node = loop_node
        self.setWindowTitle("配置循环节点")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)

        self._setup_ui()
        self._load_config()
        self._apply_theme()

    def _setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 循环名称
        name_group = QGroupBox("循环名称")
        name_layout = QVBoxLayout()
        self.name_input = QTextEdit()
        self.name_input.setPlaceholderText("输入循环名称")
        self.name_input.setMaximumHeight(50)
        name_layout.addWidget(self.name_input)
        name_group.setLayout(name_layout)
        layout.addWidget(name_group)

        # 循环模式选择
        mode_group = QGroupBox("循环模式")
        mode_layout = QVBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🔢 数字范围 (Range) - 类似 range(start, end, step)", "range")
        self.mode_combo.addItem("📋 列表迭代 (List) - 遍历列表中的每个元素", "list")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)

        # 说明标签
        self.mode_label = QLabel()
        self.mode_label.setWordWrap(True)
        self.mode_label.setStyleSheet("color: #888; font-size: 12px;")
        mode_layout.addWidget(self.mode_label)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Range 模式参数
        self.range_group = QGroupBox("Range 参数设置")
        range_layout = QFormLayout()
        range_layout.setSpacing(10)

        self.start_spin = QSpinBox()
        self.start_spin.setRange(-100000, 100000)
        self.start_spin.setValue(0)
        self.start_spin.setToolTip("循环起始值（包含）")
        range_layout.addRow("起始值 (start):", self.start_spin)

        self.end_spin = QSpinBox()
        self.end_spin.setRange(-100000, 100000)
        self.end_spin.setValue(10)
        self.end_spin.setToolTip("循环结束值（不包含）")
        range_layout.addRow("结束值 (end):", self.end_spin)

        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 10000)
        self.step_spin.setValue(1)
        self.step_spin.setToolTip("每次迭代的增量")
        range_layout.addRow("步长 (step):", self.step_spin)

        self.range_preview = QLabel()
        self.range_preview.setStyleSheet("color: #4CAF50; font-weight: bold;")
        range_layout.addRow("预览:", self.range_preview)

        self.range_group.setLayout(range_layout)
        layout.addWidget(self.range_group)

        # List 模式参数
        self.list_group = QGroupBox("List 数据设置")
        list_layout = QVBoxLayout()

        list_label = QLabel("输入 JSON 格式的列表数据：")
        list_layout.addWidget(list_label)

        self.list_text = QTextEdit()
        self.list_text.setPlaceholderText('例如：["apple", "banana", "orange"]\n或：[1, 2, 3, 4, 5]\n或：[{"name": "A"}, {"name": "B"}]')
        self.list_text.setMaximumHeight(150)
        self.list_text.textChanged.connect(self._on_list_data_changed)
        list_layout.addWidget(self.list_text)

        self.list_preview = QLabel()
        self.list_preview.setWordWrap(True)
        self.list_preview.setStyleSheet("color: #2196F3; font-size: 12px;")
        list_layout.addWidget(self.list_preview)

        self.list_group.setLayout(list_layout)
        layout.addWidget(self.list_group)

        # 迭代变量名
        var_group = QGroupBox("迭代变量")
        var_layout = QFormLayout()

        self.iterator_name_input = QTextEdit()
        self.iterator_name_input.setPlaceholderText("iterator")
        self.iterator_name_input.setMaximumHeight(50)
        self.iterator_name_input.setToolTip("内部节点通过此端口名接收迭代值")
        var_layout.addRow("迭代端口名:", self.iterator_name_input)

        var_group.setLayout(var_layout)
        layout.addWidget(var_group)

        layout.addStretch()

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("btn_secondary")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("确定")
        self.ok_btn.setObjectName("btn_primary")
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _on_mode_changed(self, index):
        """模式切换"""
        mode = self.mode_combo.itemData(index)
        
        if mode == "range":
            self.mode_label.setText("数字范围模式：按照 start, end, step 生成数字序列进行循环")
            self.range_group.setVisible(True)
            self.list_group.setVisible(False)
            self._update_range_preview()
        else:
            self.mode_label.setText("列表迭代模式：遍历 JSON 列表中的每个元素进行循环")
            self.range_group.setVisible(False)
            self.list_group.setVisible(True)
            self._update_list_preview()

    def _on_list_data_changed(self):
        """列表数据变化"""
        self._update_list_preview()

    def _update_range_preview(self):
        """更新 Range 预览"""
        start = self.start_spin.value()
        end = self.end_spin.value()
        step = self.step_spin.value()
        
        try:
            preview_list = list(range(start, end, step))
            if len(preview_list) > 10:
                preview_text = f"{preview_list[:5]} ... (共 {len(preview_list)} 项)"
            else:
                preview_text = str(preview_list)
            self.range_preview.setText(f"将生成：{preview_text}")
        except Exception as e:
            self.range_preview.setText(f"错误：{e}")

    def _update_list_preview(self):
        """更新 List 预览"""
        text = self.list_text.toPlainText().strip()
        
        if not text:
            self.list_preview.setText("预览：空列表")
            return
        
        try:
            data = json.loads(text)
            if isinstance(data, list):
                if len(data) > 5:
                    preview_text = f"{data[:3]} ... (共 {len(data)} 项)"
                else:
                    preview_text = str(data)
                self.list_preview.setText(f"有效列表：{preview_text}")
            else:
                self.list_preview.setText("⚠ 请输入列表格式的 JSON 数据")
        except json.JSONDecodeError as e:
            self.list_preview.setText(f"⚠ JSON 格式错误：{e}")
        except Exception as e:
            self.list_preview.setText(f"错误：{e}")

    def _load_config(self):
        """加载配置"""
        if self.loop_node:
            self.name_input.setText(self.loop_node.loop_name)
            
            # 设置模式
            if self.loop_node.mode == "range":
                self.mode_combo.setCurrentIndex(0)
                self.start_spin.setValue(self.loop_node.range_start)
                self.end_spin.setValue(self.loop_node.range_end)
                self.step_spin.setValue(self.loop_node.range_step)
                self._update_range_preview()
            else:
                self.mode_combo.setCurrentIndex(1)
                self.list_text.setText(self.loop_node.list_data)
                self._update_list_preview()
        else:
            # 默认模式
            self.mode_combo.setCurrentIndex(0)
            self._update_range_preview()

    def _apply_theme(self):
        """应用主题"""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme_manager.get_color("dialog_bg")};
                color: {theme_manager.get_color("dialog_text")};
            }}
            QGroupBox {{
                font-weight: bold;
                margin-top: 10px;
                padding-top: 10px;
                border: 1px solid {theme_manager.get_color("node_border")};
                border-radius: 5px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QTextEdit, QComboBox, QSpinBox {{
                background-color: {theme_manager.get_color("input_bg")};
                color: {theme_manager.get_color("input_text")};
                border: 1px solid {theme_manager.get_color("node_border")};
                border-radius: 3px;
                padding: 5px;
            }}
            QLabel {{
                color: {theme_manager.get_color("node_text")};
            }}
        """)

    def get_config(self):
        """获取配置"""
        mode = self.mode_combo.itemData(self.mode_combo.currentIndex())
        
        return {
            "name": self.name_input.toPlainText().strip() or "循环",
            "mode": mode,
            "range_start": self.start_spin.value(),
            "range_end": self.end_spin.value(),
            "range_step": self.step_spin.value(),
            "list_data": self.list_text.toPlainText().strip(),
            "iterator_name": self.iterator_name_input.toPlainText().strip() or "iterator"
        }

    def accept(self):
        """验证并接受配置"""
        config = self.get_config()
        
        # 验证 List 模式数据
        if config["mode"] == "list":
            try:
                data = json.loads(config["list_data"])
                if not isinstance(data, list):
                    QMessageBox.warning(
                        self,
                        "格式错误",
                        "列表数据必须是 JSON 数组格式，例如：[1, 2, 3]"
                    )
                    return
            except json.JSONDecodeError:
                QMessageBox.warning(
                    self,
                    "格式错误",
                    "请输入有效的 JSON 列表数据"
                )
                return
        
        super().accept()
