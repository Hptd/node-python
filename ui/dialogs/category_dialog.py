"""分类选择对话框"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QComboBox, 
                               QLineEdit, QHBoxLayout, QPushButton, QMessageBox)
from PySide6.QtCore import Qt

from core.nodes.node_library import NODE_LIBRARY_CATEGORIZED


class CategorySelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择节点保存分类")
        self.resize(350, 180)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("选择分类（或新建）："))

        self.combo = QComboBox()
        all_cats = list(NODE_LIBRARY_CATEGORIZED.keys())
        self.combo.addItems(all_cats)
        self.combo.addItem("── 新建分类 ──")
        layout.addWidget(self.combo)

        self.new_cat_edit = QLineEdit()
        self.new_cat_edit.setPlaceholderText("输入新分类名称...")
        self.new_cat_edit.setVisible(False)
        layout.addWidget(self.new_cat_edit)

        self.combo.currentTextChanged.connect(self._on_combo_changed)

        btn_layout = QHBoxLayout()
        gen_btn = QPushButton("生成")
        gen_btn.setStyleSheet("background: #4CAF50; color: white; font-weight: bold;")
        gen_btn.clicked.connect(self._on_accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(gen_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_combo_changed(self, text):
        self.new_cat_edit.setVisible(text == "── 新建分类 ──")

    def _on_accept(self):
        cat = self.selected_category()
        if not cat:
            QMessageBox.warning(self, "提示", "请选择或输入一个分类名称。")
            return
        self.accept()

    def selected_category(self):
        if self.combo.currentText() == "── 新建分类 ──":
            return self.new_cat_edit.text().strip()
        return self.combo.currentText()