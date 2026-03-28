"""设置对话框"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QPushButton, QGroupBox, QFileDialog,
    QSpinBox, QDialogButtonBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from config.settings import settings


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        
        # 创建选项卡
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # 添加各个设置页面
        self.tabs.addTab(self._create_window_page(), "窗口")
        self.tabs.addTab(self._create_graphics_page(), "画布")
        self.tabs.addTab(self._create_nodes_page(), "节点")
        self.tabs.addTab(self._create_execution_page(), "执行")
        self.tabs.addTab(self._create_embedded_python_page(), "嵌入式环境")
        self.tabs.addTab(self._create_ui_page(), "界面")
        self.tabs.addTab(self._create_logging_page(), "日志")
        
        # 按钮
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_window_page(self) -> QWidget:
        """创建窗口设置页面"""
        page = QWidget()
        layout = QFormLayout(page)
        
        # 宽度
        self.window_width_spin = QSpinBox()
        self.window_width_spin.setRange(400, 3840)
        self.window_width_spin.setSuffix(" 像素")
        layout.addRow("窗口宽度:", self.window_width_spin)
        
        # 高度
        self.window_height_spin = QSpinBox()
        self.window_height_spin.setRange(300, 2160)
        self.window_height_spin.setSuffix(" 像素")
        layout.addRow("窗口高度:", self.window_height_spin)
        
        # X 坐标
        self.window_x_spin = QSpinBox()
        self.window_x_spin.setRange(-1000, 3840)
        self.window_x_spin.setSpecialValueText("自动")
        layout.addRow("窗口 X 坐标:", self.window_x_spin)
        
        # Y 坐标
        self.window_y_spin = QSpinBox()
        self.window_y_spin.setRange(-1000, 2160)
        self.window_y_spin.setSpecialValueText("自动")
        layout.addRow("窗口 Y 坐标:", self.window_y_spin)
        
        # 最大化
        self.window_maximized_check = QCheckBox()
        self.window_maximized_check.setText("启动时最大化")
        layout.addRow("", self.window_maximized_check)
        
        # 说明
        note_label = QLabel("注意：窗口位置和尺寸设置将在下次启动时生效")
        note_label.setStyleSheet("color: gray; font-size: 9px;")
        note_label.setWordWrap(True)
        layout.addRow("", note_label)
        
        return page

    def _create_graphics_page(self) -> QWidget:
        """创建画布设置页面"""
        page = QWidget()
        layout = QFormLayout(page)
        
        # 缩放速度
        self.graphics_zoom_spin = QDoubleSpinBox()
        self.graphics_zoom_spin.setRange(1.05, 1.30)
        self.graphics_zoom_spin.setSingleStep(0.01)
        self.graphics_zoom_spin.setDecimals(2)
        layout.addRow("缩放速度:", self.graphics_zoom_spin)
        
        # 显示网格
        self.graphics_grid_check = QCheckBox()
        self.graphics_grid_check.setText("显示背景网格")
        layout.addRow("", self.graphics_grid_check)
        
        # 网格大小
        self.graphics_grid_size_spin = QSpinBox()
        self.graphics_grid_size_spin.setRange(5, 100)
        self.graphics_grid_size_spin.setSuffix(" 像素")
        layout.addRow("网格间距:", self.graphics_grid_size_spin)
        
        # 吸附到网格
        self.graphics_snap_check = QCheckBox()
        self.graphics_snap_check.setText("节点自动吸附到网格")
        layout.addRow("", self.graphics_snap_check)
        
        # 说明
        note_label = QLabel("注意：部分画布设置可能需要重启后生效")
        note_label.setStyleSheet("color: gray; font-size: 9px;")
        note_label.setWordWrap(True)
        layout.addRow("", note_label)
        
        return page

    def _create_nodes_page(self) -> QWidget:
        """创建节点设置页面"""
        page = QWidget()
        layout = QFormLayout(page)
        
        # 自动保存自定义节点
        self.nodes_auto_save_check = QCheckBox()
        self.nodes_auto_save_check.setText("创建自定义节点后自动保存")
        layout.addRow("", self.nodes_auto_save_check)
        
        # 自动加载自定义节点
        self.nodes_auto_load_check = QCheckBox()
        self.nodes_auto_load_check.setText("启动时自动加载自定义节点")
        layout.addRow("", self.nodes_auto_load_check)
        
        # 确认删除节点
        self.nodes_confirm_delete_check = QCheckBox()
        self.nodes_confirm_delete_check.setText("删除节点前显示确认对话框")
        layout.addRow("", self.nodes_confirm_delete_check)
        
        return page

    def _create_execution_page(self) -> QWidget:
        """创建执行设置页面"""
        page = QWidget()
        layout = QFormLayout(page)
        
        # 自动运行
        self.execution_auto_run_check = QCheckBox()
        self.execution_auto_run_check.setText("参数改变后自动执行（实验性）")
        layout.addRow("", self.execution_auto_run_check)
        
        # 显示执行时间
        self.execution_show_time_check = QCheckBox()
        self.execution_show_time_check.setText("执行后显示耗时")
        layout.addRow("", self.execution_show_time_check)
        
        # 出错时停止
        self.execution_stop_on_error_check = QCheckBox()
        self.execution_stop_on_error_check.setText("节点执行出错时停止后续执行")
        layout.addRow("", self.execution_stop_on_error_check)
        
        # 调试模式
        self.execution_debug_check = QCheckBox()
        self.execution_debug_check.setText("调试模式（输出详细执行日志）")
        layout.addRow("", self.execution_debug_check)
        
        return page

    def _create_embedded_python_page(self) -> QWidget:
        """创建嵌入式 Python 环境设置页面"""
        page = QWidget()
        layout = QFormLayout(page)
        
        # Python 路径
        python_path_layout = QHBoxLayout()
        self.embedded_python_path_edit = QLineEdit()
        self.embedded_python_path_edit.setPlaceholderText("留空则使用默认路径")
        python_path_layout.addWidget(self.embedded_python_path_edit)
        
        self.embedded_python_path_btn = QPushButton("浏览...")
        self.embedded_python_path_btn.clicked.connect(self._select_python_path)
        python_path_layout.addWidget(self.embedded_python_path_btn)
        layout.addRow("Python 解释器路径:", python_path_layout)
        
        # 自动初始化
        self.embedded_auto_init_check = QCheckBox()
        self.embedded_auto_init_check.setText("启动时自动检查并初始化嵌入式环境")
        layout.addRow("", self.embedded_auto_init_check)
        
        # 使用嵌入式环境执行自定义节点
        self.embedded_use_check = QCheckBox()
        self.embedded_use_check.setText("自定义节点使用嵌入式环境执行")
        layout.addRow("", self.embedded_use_check)
        
        # 说明
        note_label = QLabel("注意：嵌入式环境设置将在下次启动时生效")
        note_label.setStyleSheet("color: gray; font-size: 9px;")
        note_label.setWordWrap(True)
        layout.addRow("", note_label)
        
        return page

    def _select_python_path(self):
        """选择 Python 解释器路径"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Python 解释器",
            "",
            "Python 可执行文件 (python.exe);;所有文件 (*)"
        )
        if file_path:
            self.embedded_python_path_edit.setText(file_path)

    def _create_ui_page(self) -> QWidget:
        """创建界面设置页面"""
        page = QWidget()
        layout = QFormLayout(page)
        
        # 主题
        self.ui_theme_combo = QComboBox()
        self.ui_theme_combo.addItem("暗黑", "dark")
        self.ui_theme_combo.addItem("明亮", "light")
        layout.addRow("界面主题:", self.ui_theme_combo)
        
        # 字体大小
        self.ui_font_spin = QSpinBox()
        self.ui_font_spin.setRange(8, 20)
        self.ui_font_spin.setSuffix(" 像素")
        layout.addRow("字体大小:", self.ui_font_spin)
        
        # 语言
        self.ui_language_combo = QComboBox()
        self.ui_language_combo.addItem("简体中文", "zh_CN")
        self.ui_language_combo.addItem("English", "en_US")
        layout.addRow("界面语言:", self.ui_language_combo)
        
        # 显示提示
        self.ui_tooltips_check = QCheckBox()
        self.ui_tooltips_check.setText("显示节点和控件的悬浮提示")
        layout.addRow("", self.ui_tooltips_check)
        
        # 说明
        note_label = QLabel("注意：主题和语言切换将立即生效，字体大小需要重启后生效")
        note_label.setStyleSheet("color: gray; font-size: 9px;")
        note_label.setWordWrap(True)
        layout.addRow("", note_label)
        
        return page

    def _create_logging_page(self) -> QWidget:
        """创建日志设置页面"""
        page = QWidget()
        layout = QFormLayout(page)
        
        # 日志目录
        log_dir_layout = QHBoxLayout()
        self.logging_dir_edit = QLineEdit()
        self.logging_dir_edit.setPlaceholderText("output_logs")
        log_dir_layout.addWidget(self.logging_dir_edit)
        
        self.logging_dir_btn = QPushButton("浏览...")
        self.logging_dir_btn.clicked.connect(self._select_log_dir)
        log_dir_layout.addWidget(self.logging_dir_btn)
        layout.addRow("日志目录:", log_dir_layout)
        
        # 日志文件名
        self.logging_filename_edit = QLineEdit()
        self.logging_filename_edit.setPlaceholderText("output_log.txt")
        layout.addRow("日志文件名:", self.logging_filename_edit)
        
        # 启用日志
        self.logging_enabled_check = QCheckBox()
        self.logging_enabled_check.setText("启用日志记录")
        layout.addRow("", self.logging_enabled_check)
        
        # 说明
        note_label = QLabel("注意：日志设置将在下次启动时生效")
        note_label.setStyleSheet("color: gray; font-size: 9px;")
        note_label.setWordWrap(True)
        layout.addRow("", note_label)
        
        return page

    def _select_log_dir(self):
        """选择日志目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择日志目录",
            ""
        )
        if dir_path:
            self.logging_dir_edit.setText(dir_path)

    def _load_settings(self):
        """从设置加载值到 UI 控件"""
        # 窗口
        self.window_width_spin.setValue(settings.get("window.width", 1000))
        self.window_height_spin.setValue(settings.get("window.height", 700))
        x_val = settings.get("window.x")
        self.window_x_spin.setValue(x_val if x_val is not None else 0)
        y_val = settings.get("window.y")
        self.window_y_spin.setValue(y_val if y_val is not None else 0)
        self.window_maximized_check.setChecked(settings.get("window.maximized", False))
        
        # 画布
        self.graphics_zoom_spin.setValue(settings.get("graphics.zoom_speed", 1.15))
        self.graphics_grid_check.setChecked(settings.get("graphics.grid_enabled", False))
        self.graphics_grid_size_spin.setValue(settings.get("graphics.grid_size", 20))
        self.graphics_snap_check.setChecked(settings.get("graphics.snap_to_grid", False))
        
        # 节点
        self.nodes_auto_save_check.setChecked(settings.get("nodes.auto_save_custom_nodes", True))
        self.nodes_auto_load_check.setChecked(settings.get("nodes.auto_load_custom_nodes", True))
        self.nodes_confirm_delete_check.setChecked(settings.get("nodes.confirm_node_deletion", True))
        
        # 执行
        self.execution_auto_run_check.setChecked(settings.get("execution.auto_run_on_change", False))
        self.execution_show_time_check.setChecked(settings.get("execution.show_execution_time", True))
        self.execution_stop_on_error_check.setChecked(settings.get("execution.stop_on_error", True))
        self.execution_debug_check.setChecked(settings.get("execution.debug_mode", False))
        
        # 嵌入式 Python
        python_path = settings.get("embedded_python.path")
        self.embedded_python_path_edit.setText(python_path if python_path else "")
        self.embedded_auto_init_check.setChecked(settings.get("embedded_python.auto_init", False))
        self.embedded_use_check.setChecked(settings.get("embedded_python.use_for_custom_nodes", True))
        
        # UI
        theme = settings.get("ui.theme", "dark")
        theme_index = self.ui_theme_combo.findData(theme)
        self.ui_theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self.ui_font_spin.setValue(settings.get("ui.font_size", 10))
        language = settings.get("ui.language", "zh_CN")
        language_index = self.ui_language_combo.findData(language)
        self.ui_language_combo.setCurrentIndex(language_index if language_index >= 0 else 0)
        self.ui_tooltips_check.setChecked(settings.get("ui.show_tooltips", True))
        
        # 日志
        self.logging_dir_edit.setText(settings.get("logging.log_dir", "output_logs"))
        self.logging_filename_edit.setText(settings.get("logging.log_filename", "output_log.txt"))
        self.logging_enabled_check.setChecked(settings.get("logging.enabled", True))

    def _save_settings(self):
        """从 UI 控件保存值到设置"""
        # 窗口
        settings.set("window.width", self.window_width_spin.value())
        settings.set("window.height", self.window_height_spin.value())
        x_val = self.window_x_spin.value()
        settings.set("window.x", x_val if x_val != 0 else None)
        y_val = self.window_y_spin.value()
        settings.set("window.y", y_val if y_val != 0 else None)
        settings.set("window.maximized", self.window_maximized_check.isChecked())
        
        # 画布
        settings.set("graphics.zoom_speed", self.graphics_zoom_spin.value())
        settings.set("graphics.grid_enabled", self.graphics_grid_check.isChecked())
        settings.set("graphics.grid_size", self.graphics_grid_size_spin.value())
        settings.set("graphics.snap_to_grid", self.graphics_snap_check.isChecked())
        
        # 节点
        settings.set("nodes.auto_save_custom_nodes", self.nodes_auto_save_check.isChecked())
        settings.set("nodes.auto_load_custom_nodes", self.nodes_auto_load_check.isChecked())
        settings.set("nodes.confirm_node_deletion", self.nodes_confirm_delete_check.isChecked())
        
        # 执行
        settings.set("execution.auto_run_on_change", self.execution_auto_run_check.isChecked())
        settings.set("execution.show_execution_time", self.execution_show_time_check.isChecked())
        settings.set("execution.stop_on_error", self.execution_stop_on_error_check.isChecked())
        settings.set("execution.debug_mode", self.execution_debug_check.isChecked())
        
        # 嵌入式 Python
        python_path = self.embedded_python_path_edit.text().strip()
        settings.set("embedded_python.path", python_path if python_path else None)
        settings.set("embedded_python.auto_init", self.embedded_auto_init_check.isChecked())
        settings.set("embedded_python.use_for_custom_nodes", self.embedded_use_check.isChecked())
        
        # UI
        settings.set("ui.theme", self.ui_theme_combo.currentData())
        settings.set("ui.font_size", self.ui_font_spin.value())
        settings.set("ui.language", self.ui_language_combo.currentData())
        settings.set("ui.show_tooltips", self.ui_tooltips_check.isChecked())
        
        # 日志
        settings.set("logging.log_dir", self.logging_dir_edit.text().strip() or "output_logs")
        settings.set("logging.log_filename", self.logging_filename_edit.text().strip() or "output_log.txt")
        settings.set("logging.enabled", self.logging_enabled_check.isChecked())
        
        # 保存
        settings.save()

    def accept(self):
        """点击确定按钮时"""
        self._save_settings()
        super().accept()
