"""数据提取路径选择对话框"""

import json
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QPlainTextEdit, QTreeWidget, QTreeWidgetItem,
                               QPushButton, QLineEdit, QMessageBox, QSplitter,
                               QWidget, QApplication)
from PySide6.QtCore import Qt


class PathSelectorDialog(QDialog):
    """
    数据提取路径选择对话框。
    允许用户粘贴示例数据，可视化浏览并选择提取路径。
    """
    
    def __init__(self, parent=None, current_path=""):
        super().__init__(parent)
        self.setWindowTitle("数据提取路径选择器")
        self.resize(800, 420)
        
        self.selected_path = current_path
        
        layout = QVBoxLayout(self)
        
        # 顶部说明
        info_label = QLabel("粘贴示例数据到左侧，在右侧树形结构中点击选择要提取的路径")
        info_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info_label)
        
        # 分割器：左侧数据输入，右侧路径浏览
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：数据输入区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("📋 示例数据（JSON格式）："))
        
        self.data_input = QPlainTextEdit()
        self.data_input.setPlaceholderText('''粘贴示例JSON数据，例如：
{
    "model": "wan2.6-i2v",
    "input": {
        "prompt": "",
        "img_url": ["url1", "url2"]
    },
    "parameters": {
        "resolution": "720P"
    }
}''')
        self.data_input.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; font-family: Consolas; font-size: 12px;"
        )
        left_layout.addWidget(self.data_input)
        
        # 解析按钮
        parse_btn = QPushButton("🔍 解析数据结构")
        parse_btn.setStyleSheet("background: #2196F3; color: white; padding: 8px;")
        parse_btn.clicked.connect(self._parse_data)
        left_layout.addWidget(parse_btn)
        
        splitter.addWidget(left_widget)
        
        # 右侧：路径浏览区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        right_layout.addWidget(QLabel("🌲 数据结构（点击选择路径）："))
        
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["字段", "类型", "预览值"])
        self.tree_widget.setColumnWidth(0, 200)
        self.tree_widget.setColumnWidth(1, 80)
        self.tree_widget.itemClicked.connect(self._on_tree_item_clicked)
        self.tree_widget.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        right_layout.addWidget(self.tree_widget)
        
        # 路径显示
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("📍 选中路径："))
        self.path_display = QLineEdit()
        self.path_display.setText(current_path)
        self.path_display.setStyleSheet(
            "background-color: #2b2b2b; color: #4CAF50; font-family: Consolas; font-size: 13px; padding: 5px;"
        )
        path_layout.addWidget(self.path_display)
        right_layout.addLayout(path_layout)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([350, 450])
        
        layout.addWidget(splitter)
        
        # 底部按钮
        btn_layout = QHBoxLayout()
        
        preview_btn = QPushButton("👁️ 预览提取结果")
        preview_btn.setStyleSheet("background: #FF9800; color: white;")
        preview_btn.clicked.connect(self._preview_result)
        btn_layout.addWidget(preview_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        confirm_btn = QPushButton("✓ 确认选择")
        confirm_btn.setStyleSheet("background: #4CAF50; color: white; font-weight: bold;")
        confirm_btn.clicked.connect(self._confirm_selection)
        btn_layout.addWidget(confirm_btn)
        
        layout.addLayout(btn_layout)
        
        # 存储解析后的数据
        self.parsed_data = None
    
    def _parse_data(self):
        """解析输入的数据并构建树形结构"""
        text = self.data_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先粘贴示例数据")
            return
        
        try:
            # 尝试解析为JSON
            self.parsed_data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试作为Python字面量解析
            try:
                import ast
                self.parsed_data = ast.literal_eval(text)
            except Exception as e:
                QMessageBox.critical(self, "解析错误", f"无法解析数据格式：\n{e}")
                return
        
        # 构建树形结构
        self.tree_widget.clear()
        self._build_tree(self.parsed_data, self.tree_widget)
        self.tree_widget.expandToDepth(1)
        
        QMessageBox.information(self, "解析成功", "数据结构已加载，请点击选择要提取的路径")
    
    def _build_tree(self, data, parent, key="", path=""):
        """递归构建树形结构"""
        if isinstance(data, dict):
            item = QTreeWidgetItem(parent)
            display_key = key if key else "(根对象)"
            item.setText(0, display_key)
            item.setText(1, "dict")
            item.setText(2, f"{{{len(data)}个字段}}")
            item.setData(0, Qt.UserRole, path)
            
            for k, v in data.items():
                new_path = f"{path}.{k}" if path else k
                self._build_tree(v, item, k, new_path)
                
        elif isinstance(data, list):
            item = QTreeWidgetItem(parent)
            display_key = key if key else "(根数组)"
            item.setText(0, display_key)
            item.setText(1, "list")
            item.setText(2, f"[{len(data)}个元素]")
            item.setData(0, Qt.UserRole, path)
            
            # 只显示前5个元素作为示例
            for i, v in enumerate(data[:5]):
                # 使用方括号格式 [i] 而不是 .i
                new_path = f"{path}[{i}]" if path else f"[{i}]"
                self._build_tree(v, item, f"[{i}]", new_path)
            
            if len(data) > 5:
                more_item = QTreeWidgetItem(item)
                more_item.setText(0, "...")
                more_item.setText(1, "")
                more_item.setText(2, f"还有 {len(data) - 5} 个元素")
                
        else:
            item = QTreeWidgetItem(parent)
            item.setText(0, key)
            item.setText(1, type(data).__name__)
            # 截断过长的值
            value_str = str(data)
            if len(value_str) > 50:
                value_str = value_str[:50] + "..."
            item.setText(2, value_str)
            item.setData(0, Qt.UserRole, path)
    
    def _on_tree_item_clicked(self, item, column):
        """点击树节点时更新路径显示"""
        path = item.data(0, Qt.UserRole)
        if path:
            self.path_display.setText(path)
            self.selected_path = path
    
    def _on_tree_item_double_clicked(self, item, column):
        """双击树节点时确认选择"""
        path = item.data(0, Qt.UserRole)
        if path:
            self.path_display.setText(path)
            self.selected_path = path
            self._preview_result()
    
    def _preview_result(self):
        """预览提取结果"""
        if self.parsed_data is None:
            QMessageBox.warning(self, "提示", "请先解析示例数据")
            return
        
        path = self.path_display.text().strip()
        if not path:
            QMessageBox.warning(self, "提示", "请先选择或输入提取路径")
            return
        
        # 使用节点的提取逻辑
        from core.nodes.base_nodes import extract_data
        result = extract_data(self.parsed_data, path)
        
        # 显示结果
        if result is None:
            QMessageBox.warning(self, "提取结果", "路径无效或提取结果为 None")
        else:
            result_type = type(result).__name__
            if isinstance(result, (dict, list)):
                result_str = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                result_str = str(result)
            
            msg = f"类型: {result_type}\n\n结果:\n{result_str}"
            QMessageBox.information(self, "提取结果预览", msg)
    
    def _confirm_selection(self):
        """确认选择"""
        self.selected_path = self.path_display.text().strip()
        if not self.selected_path:
            QMessageBox.warning(self, "提示", "请先选择或输入提取路径")
            return
        self.accept()
    
    def get_selected_path(self):
        """获取选中的路径"""
        return self.selected_path


# 便捷函数，用于在主窗口中调用
def show_path_selector(parent=None, current_path=""):
    """显示路径选择对话框，返回选中的路径或None"""
    dialog = PathSelectorDialog(parent, current_path)
    if dialog.exec() == QDialog.Accepted:
        return dialog.get_selected_path()
    return None
