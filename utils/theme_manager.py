"""主题管理器 - 管理应用的黑白配色方案"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor


class ThemeManager(QObject):
    """主题管理器单例类"""
    _instance = None
    theme_changed = Signal(str)  # 主题切换信号，传递主题名称

    # 主题定义
    THEMES = {
        "dark": {
            "name": "暗黑模式",
            "icon": "🌙",
            # 节点颜色
            "node_bg": "#4CAF50",
            "node_bg_selected": "#66BB6A",
            "node_border": "#2E7D32",
            "node_text": "#FFFFFF",
            # 端口颜色
            "input_port": "#2196F3",
            "output_port": "#FF9800",
            "port_border": "#FFFFFF",
            # 连接线颜色
            "connection": "#2AB835",
            "connection_selected": "#00BFFF",
            # 选择框颜色
            "selection": "#00BFFF",
            "selection_fill": "rgba(0, 191, 255, 40)",
            # 背景颜色
            "canvas_bg": "#1e1e1e",
            "panel_bg": "#2b2b2b",
            # 控制台颜色
            "console_bg": "#1e1e1e",
            "console_text": "#5669c2",
            # 代码编辑器颜色
            "code_editor_bg": "#1e1e1e",
            "code_editor_text": "#a9b7c6",
            # UI 控件颜色
            "button_primary": "#4CAF50",
            "button_primary_hover": "#388E3C",
            "button_secondary": "#2196F3",
            "button_secondary_hover": "#1976D2",
            "button_danger": "#f44336",
            "button_danger_hover": "#d32f2f",
            "button_warning": "#FF9800",
            "button_ai": "#9C27B0",
            # 文本颜色
            "text_primary": "#FFFFFF",
            "text_secondary": "#B0B0B0",
            "text_disabled": "#666666",
            # 边框颜色
            "border": "#555555",
            "border_light": "#777777",
            # 菜单颜色
            "menu_bg": "#2b2b2b",
            "menu_hover": "#4CAF50",
            # 悬停背景
            "hover_bg": "#3c3c3c",
            # 主色调
            "primary": "#4CAF50",
            # 输入框颜色
            "input_bg": "#3c3c3c",
            "input_text": "#FFFFFF",
            "input_placeholder": "#888888",
            # 节点组颜色
            "group_bg": "rgba(120, 120, 120, 60)",
            "group_border": "#888888",
            "group_header_bg": "rgba(80, 80, 80, 180)",
            "group_header_text": "#FFFFFF",
            # 调试状态颜色
            "node_running": "#FFD700",  # 正在运行 - 金黄色
            "node_running_border": "#FFA500",  # 运行边框 - 橙色
            "node_error": "#FFCDD2",  # 错误节点背景 - 浅红色
            "node_error_border": "#F44336",  # 错误节点边框 - 红色
            "node_error_text": "#B71C1C",  # 错误节点文本 - 深红色
            # 控制台输出类型颜色
            "console_error": "#FF5555",  # 错误信息 - 红色
            "console_warning": "#FFAA00",  # 警告信息 - 橙色
            "console_info": "#55AAFF",  # 提示信息 - 蓝色
            "console_success": "#437a2e",  # 成功信息 - 绿色
            "console_debug": "#AA88FF",  # 调试信息 - 紫色
            "console_system": "#AAAAAA",  # 系统信息 - 灰色
        },
        "light": {
            "name": "明亮模式",
            "icon": "☀️",
            # 节点颜色
            "node_bg": "#81C784",
            "node_bg_selected": "#66BB6A",
            "node_border": "#4CAF50",
            "node_text": "#212121",
            # 端口颜色
            "input_port": "#42A5F5",
            "output_port": "#FFA726",
            "port_border": "#424242",
            # 连接线颜色
            "connection": "#4CAF50",
            "connection_selected": "#2196F3",
            # 选择框颜色
            "selection": "#2196F3",
            "selection_fill": "rgba(33, 150, 243, 40)",
            # 背景颜色
            "canvas_bg": "#F5F5F5",
            "panel_bg": "#FFFFFF",
            # 控制台颜色
            "console_bg": "#FAFAFA",
            "console_text": "#5669c2",
            # 代码编辑器颜色
            "code_editor_bg": "#FAFAFA",
            "code_editor_text": "#333333",
            # UI 控件颜色
            "button_primary": "#4CAF50",
            "button_primary_hover": "#388E3C",
            "button_secondary": "#2196F3",
            "button_secondary_hover": "#1976D2",
            "button_danger": "#f44336",
            "button_danger_hover": "#d32f2f",
            "button_warning": "#FF9800",
            "button_ai": "#9C27B0",
            # 文本颜色
            "text_primary": "#212121",
            "text_secondary": "#757575",
            "text_disabled": "#BDBDBD",
            # 边框颜色
            "border": "#E0E0E0",
            "border_light": "#BDBDBD",
            # 菜单颜色
            "menu_bg": "#FFFFFF",
            "menu_hover": "#E3F2FD",
            # 悬停背景
            "hover_bg": "#EEEEEE",
            # 主色调
            "primary": "#2196F3",
            # 输入框颜色
            "input_bg": "#FFFFFF",
            "input_text": "#212121",
            "input_placeholder": "#9E9E9E",
            # 节点组颜色
            "group_bg": "rgba(200, 200, 200, 80)",
            "group_border": "#9E9E9E",
            "group_header_bg": "rgba(180, 180, 180, 200)",
            "group_header_text": "#424242",
            # 调试状态颜色
            "node_running": "#FFF59D",  # 正在运行 - 浅黄色
            "node_running_border": "#FFA726",  # 运行边框 - 橙色
            "node_error": "#FFCDD2",  # 错误节点背景 - 浅红色
            "node_error_border": "#E53935",  # 错误节点边框 - 红色
            "node_error_text": "#B71C1C",  # 错误节点文本 - 深红色
            # 控制台输出类型颜色
            "console_error": "#D32F2F",  # 错误信息 - 红色
            "console_warning": "#F57C00",  # 警告信息 - 橙色
            "console_info": "#1976D2",  # 提示信息 - 蓝色
            "console_success": "#437a2e",  # 成功信息 - 绿色
            "console_debug": "#764b88",  # 调试信息 - 紫色
            "console_system": "#757575",  # 系统信息 - 灰色
        }
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._current_theme = "dark"
        return cls._instance

    def __init__(self):
        super().__init__()
        # 确保只初始化一次
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._current_theme = "dark"

    @property
    def current_theme(self) -> str:
        """获取当前主题名称"""
        return self._current_theme

    def get_color(self, key: str) -> str:
        """获取指定键的颜色值"""
        theme = self.THEMES.get(self._current_theme, self.THEMES["dark"])
        return theme.get(key, "#000000")

    def get_qcolor(self, key: str) -> QColor:
        """获取指定键的 QColor 对象"""
        return QColor(self.get_color(key))

    def set_theme(self, theme_name: str):
        """设置主题"""
        if theme_name in self.THEMES and theme_name != self._current_theme:
            self._current_theme = theme_name
            self.theme_changed.emit(theme_name)
            return True
        return False

    def toggle_theme(self) -> str:
        """切换主题，返回切换后的主题名称"""
        new_theme = "light" if self._current_theme == "dark" else "dark"
        self.set_theme(new_theme)
        return new_theme

    def get_theme_names(self) -> list:
        """获取所有可用主题名称列表"""
        return list(self.THEMES.keys())

    def get_theme_info(self, theme_name: str = None) -> dict:
        """获取主题信息"""
        name = theme_name or self._current_theme
        theme = self.THEMES.get(name, self.THEMES["dark"])
        return {
            "name": theme["name"],
            "icon": theme["icon"]
        }

    def get_stylesheet(self) -> str:
        """获取当前主题的 QSS 样式表"""
        t = self.get_color
        return f"""
        QMainWindow {{
            background-color: {t('panel_bg')};
        }}

        QDockWidget {{
            background-color: {t('panel_bg')};
            color: {t('text_primary')};
        }}

        QDockWidget::title {{
            background-color: {t('panel_bg')};
            color: {t('text_primary')};
            padding: 5px;
        }}

        QWidget {{
            background-color: {t('panel_bg')};
            color: {t('text_primary')};
        }}

        QPushButton {{
            background-color: {t('button_primary')};
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
        }}

        QPushButton:hover {{
            background-color: {t('button_primary_hover')};
        }}

        QPushButton:disabled {{
            background-color: {t('text_disabled')};
        }}

        /* 次要按钮 */
        QPushButton#btn_secondary {{
            background-color: {t('button_secondary')};
        }}

        QPushButton#btn_secondary:hover {{
            background-color: {t('button_secondary_hover')};
        }}

        /* 警告按钮 */
        QPushButton#btn_warning {{
            background-color: {t('button_warning')};
        }}

        QPushButton#btn_warning:hover {{
            background-color: #F57C00;
        }}

        /* AI 按钮 */
        QPushButton#btn_ai {{
            background-color: {t('button_ai')};
            font-weight: bold;
        }}

        QPushButton#btn_ai:hover {{
            background-color: #7B1FA2;
        }}

        /* 危险按钮 */
        QPushButton#btn_danger {{
            background-color: {t('button_danger')};
        }}

        QPushButton#btn_danger:hover {{
            background-color: {t('button_danger_hover')};
        }}

        /* 小按钮 */
        QPushButton#btn_primary_small {{
            background-color: {t('button_primary')};
            padding: 3px 8px;
            font-size: 11px;
        }}

        QPushButton#btn_primary_small:hover {{
            background-color: {t('button_primary_hover')};
        }}

        QPushButton#btn_secondary_small {{
            background-color: {t('button_secondary')};
            padding: 3px 8px;
            font-size: 11px;
        }}

        QPushButton#btn_secondary_small:hover {{
            background-color: {t('button_secondary_hover')};
        }}

        QPushButton#btn_danger_small {{
            background-color: {t('button_danger')};
            padding: 3px 8px;
            font-size: 11px;
        }}

        QPushButton#btn_danger_small:hover {{
            background-color: {t('button_danger_hover')};
        }}

        QLineEdit {{
            background-color: {t('input_bg')};
            color: {t('input_text')};
            border: 1px solid {t('border')};
            padding: 4px;
            border-radius: 3px;
        }}

        QLineEdit::placeholder {{
            color: {t('input_placeholder')};
        }}

        QTextEdit {{
            background-color: {t('code_editor_bg')};
            color: {t('code_editor_text')};
            border: 1px solid {t('border')};
            font-family: Consolas;
        }}

        /* 代码编辑器 */
        QTextEdit#code_editor {{
            background-color: {t('code_editor_bg')};
            color: {t('code_editor_text')};
            border: 1px solid {t('border')};
            font-family: Consolas;
        }}

        /* 控制台 */
        QTextEdit#console {{
            background-color: {t('console_bg')};
            color: {t('console_text')};
            border: 1px solid {t('border')};
            font-family: Consolas;
        }}

        QSpinBox, QDoubleSpinBox {{
            background-color: {t('input_bg')};
            color: {t('input_text')};
            border: 1px solid {t('border')};
            padding: 4px;
            padding-right: 28px;  /* 为右侧按钮预留空间，防止文本与按钮重叠 */
        }}

        QSpinBox::up-button, QDoubleSpinBox::up-button {{
            background-color: rgba(255, 255, 255, 0.2);
            border: 1px solid {t('border')};
            border-left: 1px solid {t('border')};
            width: 24px;
            margin: 2px;
            margin-right: 2px;
            border-radius: 3px;
        }}

        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {{
            background-color: rgba(255, 255, 255, 0.3);
        }}

        QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {{
            background-color: rgba(255, 255, 255, 0.4);
        }}

        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            width: 10px;
            height: 10px;
        }}

        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: rgba(255, 255, 255, 0.2);
            border: 1px solid {t('border')};
            border-left: 1px solid {t('border')};
            width: 24px;
            margin: 2px;
            margin-right: 2px;
            margin-top: 1px;
            border-radius: 3px;
        }}

        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: rgba(255, 255, 255, 0.3);
        }}

        QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {{
            background-color: rgba(255, 255, 255, 0.4);
        }}

        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            width: 10px;
            height: 10px;
        }}

        QCheckBox {{
            color: {t('text_primary')};
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
        }}

        QLabel {{
            color: {t('text_primary')};
        }}

        QTreeWidget {{
            background-color: {t('panel_bg')};
            color: {t('text_primary')};
            border: 1px solid {t('border')};
        }}

        QTreeWidget::item {{
            padding: 4px;
        }}

        QTreeWidget::item:selected {{
            background-color: {t('button_primary')};
        }}

        QMenu {{
            background-color: {t('menu_bg')};
            color: {t('text_primary')};
            padding: 5px;
            border: 1px solid {t('border')};
        }}

        QMenu::item {{
            padding: 5px 20px;
        }}

        QMenu::item:selected {{
            background-color: {t('menu_hover')};
        }}

        QToolBar {{
            background-color: {t('panel_bg')};
            border: none;
            padding: 5px;
        }}

        QToolButton {{
            background-color: transparent;
            color: {t('text_primary')};
            padding: 5px;
        }}

        QToolButton:hover {{
            background-color: {t('menu_hover')};
        }}

        QScrollBar:vertical {{
            background-color: {t('panel_bg')};
            width: 12px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {t('border_light')};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {t('text_secondary')};
        }}

        QScrollBar:horizontal {{
            background-color: {t('panel_bg')};
            height: 12px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {t('border_light')};
            border-radius: 6px;
            min-width: 20px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {t('text_secondary')};
        }}

        QInputDialog {{
            background-color: {t('panel_bg')};
        }}

        QMessageBox {{
            background-color: {t('panel_bg')};
        }}

        QDialog {{
            background-color: {t('panel_bg')};
        }}
        """


# 全局主题管理器实例
theme_manager = ThemeManager()
