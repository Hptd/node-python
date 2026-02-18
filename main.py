"""应用入口"""

import sys
import atexit

from PySide6.QtWidgets import QApplication

from ui.main_window import SimplePyFlowWindow
from storage.custom_node_storage import load_custom_nodes, save_custom_nodes
from config.settings import settings


def setup_application() -> bool:
    """设置应用程序"""
    print("=" * 50)
    print("启动简易中文节点编辑器")
    print("=" * 50)
    
    # 加载设置
    settings.load()
    
    # 加
    if settings.get("nodes.auto_load_custom_nodes", True):
        print("正在加载自定义节点...")
        load_custom_nodes()
    else:
        print("已禁用自动加载自定义节点")
    
    return True


def cleanup_application() -> None:
    """清理应用程序"""
    print("正在清理应用程序...")
    
    # 保存自定义节点
    if settings.get("nodes.auto_save_custom_nodes", True):
        print("正在保存自定义节点...")
        save_custom_nodes()
    
    # 保存设置
    print("正在保存设置...")
    settings.save()
    
    print("应用程序清理完成")
    print("=" * 50)


def main() -> int:
    """主函数"""
    # 设置应用程序
    if not setup_application():
        return 1
    
    # 注册退出处理函数
    atexit.register(cleanup_application)
    
    # 创建Qt应用
    app = QApplication(sys.argv)
    app.setApplicationName("简易中文节点编辑器")
    app.setOrganizationName("NodePython")
    
    # 创建主窗口
    window = SimplePyFlowWindow()
    
    # 应用窗口设置
    window_width = settings.get("window.width", 1000)
    window_height = settings.get("window.height", 700)
    window.resize(window_width, window_height)
    
    window_x = settings.get("window.x")
    window_y = settings.get("window.y")
    if window_x is not None and window_y is not None:
        window.move(window_x, window_y)
    
    if settings.get("window.maximized", False):
        window.showMaximized()
    else:
        window.show()
    
    # 运行应用
    exit_code = app.exec()
    
    # 保存窗口状态
    if not window.isMaximized():
        settings.set("window.width", window.width())
        settings.set("window.height", window.height())
        settings.set("window.x", window.x())
        settings.set("window.y", window.y())
    settings.set("window.maximized", window.isMaximized())
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())