"""依赖包管理对话框

用于管理嵌入式 Python 环境中的第三方库。
支持安装、卸载、查看已安装的包。
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QTextEdit,
    QMessageBox, QProgressDialog, QMenu, QGroupBox,
    QFileDialog, QSplitter, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction

import os
from pathlib import Path
from typing import Optional


class PackageInstallThread(QThread):
    """包安装后台线程"""
    finished_signal = Signal(bool, str)  # 成功标志, 输出信息
    progress_signal = Signal(str)  # 进度消息
    
    def __init__(self, executor, package_name: str, action: str = "install"):
        super().__init__()
        self.executor = executor
        self.package_name = package_name
        self.action = action  # install, uninstall
    
    def run(self):
        try:
            self.progress_signal.emit(f"正在{self.action} {self.package_name}...")
            
            if self.action == "install":
                success, output = self.executor.install_package(self.package_name)
            else:  # uninstall
                success, output = self.executor.uninstall_package(self.package_name)
            
            self.finished_signal.emit(success, output)
        except Exception as e:
            self.finished_signal.emit(False, str(e))


class PackageManagerDialog(QDialog):
    """包管理器对话框"""
    
    def __init__(self, parent=None, executor=None):
        super().__init__(parent)
        self.executor = executor
        self.install_thread: Optional[PackageInstallThread] = None
        
        self.setWindowTitle("依赖包管理")
        self.setMinimumSize(700, 500)
        
        self._setup_ui()
        self._load_packages()
    
    def _setup_ui(self):
        """设置界面"""
        layout = QVBoxLayout(self)
        
        # 环境信息
        info_group = QGroupBox("环境信息")
        info_layout = QVBoxLayout(info_group)
        self.info_label = QLabel("正在加载...")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        layout.addWidget(info_group)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 安装区域
        install_group = QGroupBox("安装/卸载包")
        install_layout = QHBoxLayout(install_group)
        
        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("输入包名，如: requests 或 requests==2.28.0")
        self.package_input.returnPressed.connect(self._on_install)
        
        self.install_btn = QPushButton("安装")
        self.install_btn.clicked.connect(self._on_install)
        
        self.uninstall_btn = QPushButton("卸载")
        self.uninstall_btn.clicked.connect(self._on_uninstall)
        self.uninstall_btn.setEnabled(False)
        
        install_layout.addWidget(QLabel("包名:"))
        install_layout.addWidget(self.package_input, 1)
        install_layout.addWidget(self.install_btn)
        install_layout.addWidget(self.uninstall_btn)
        
        layout.addWidget(install_group)
        
        # 包列表
        list_group = QGroupBox("已安装的包")
        list_layout = QVBoxLayout(list_group)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._load_packages)
        
        self.import_req_btn = QPushButton("从 requirements.txt 导入")
        self.import_req_btn.clicked.connect(self._on_import_requirements)
        
        self.export_req_btn = QPushButton("导出到 requirements.txt")
        self.export_req_btn.clicked.connect(self._on_export_requirements)
        
        toolbar_layout.addWidget(self.refresh_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.import_req_btn)
        toolbar_layout.addWidget(self.export_req_btn)
        
        list_layout.addLayout(toolbar_layout)
        
        # 列表
        self.package_list = QListWidget()
        self.package_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.package_list.customContextMenuRequested.connect(self._show_context_menu)
        self.package_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.package_list.itemDoubleClicked.connect(self._on_package_info)
        
        list_layout.addWidget(self.package_list)
        
        layout.addWidget(list_group, 1)
        
        # 输出区域
        output_group = QGroupBox("操作输出")
        output_layout = QVBoxLayout(output_group)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(150)
        
        output_layout.addWidget(self.output_text)
        layout.addWidget(output_group)
        
        # 关闭按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
        
        # 加载环境信息
        self._load_environment_info()
    
    def _load_environment_info(self):
        """加载环境信息"""
        if not self.executor:
            self.info_label.setText("错误: 未提供执行器实例")
            return
        
        try:
            info = self.executor.get_environment_info()
            text = f"""
            <b>Python 解释器:</b> {info.get('python_exe', '未知')}<br>
            <b>Python 版本:</b> {info.get('python_version', '未知')}<br>
            <b>Site-packages:</b> {info.get('site_packages', '未知')}<br>
            <b>已安装包数:</b> {info.get('installed_packages_count', 0)}
            """
            self.info_label.setText(text)
        except Exception as e:
            self.info_label.setText(f"加载环境信息失败: {e}")
    
    def _load_packages(self):
        """加载已安装的包列表"""
        if not self.executor:
            return
        
        self.package_list.clear()
        
        try:
            packages = self.executor.list_installed_packages()
            
            for pkg in packages:
                name = pkg.get('name', 'Unknown')
                version = pkg.get('version', 'Unknown')
                
                item = QListWidgetItem(f"{name} ({version})")
                item.setData(Qt.UserRole, pkg)
                self.package_list.addItem(item)
            
            self._log(f"已加载 {len(packages)} 个包")
            
        except Exception as e:
            self._log(f"加载包列表失败: {e}")
            QMessageBox.warning(self, "错误", f"加载包列表失败: {e}")
    
    def _on_selection_changed(self):
        """选择改变时更新按钮状态"""
        has_selection = len(self.package_list.selectedItems()) > 0
        self.uninstall_btn.setEnabled(has_selection)
        
        if has_selection:
            item = self.package_list.selectedItems()[0]
            pkg = item.data(Qt.UserRole)
            if pkg:
                self.package_input.setText(pkg.get('name', ''))
    
    def _on_install(self):
        """安装包"""
        package_name = self.package_input.text().strip()
        if not package_name:
            QMessageBox.warning(self, "警告", "请输入包名")
            return
        
        self._run_package_action(package_name, "install")
    
    def _on_uninstall(self):
        """卸载包"""
        package_name = self.package_input.text().strip()
        if not package_name:
            QMessageBox.warning(self, "警告", "请选择要卸载的包")
            return
        
        # 确认对话框
        reply = QMessageBox.question(
            self, "确认卸载",
            f"确定要卸载 {package_name} 吗？\n这可能会影响依赖此包的功能。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self._run_package_action(package_name, "uninstall")
    
    def _run_package_action(self, package_name: str, action: str):
        """运行包操作（安装/卸载）"""
        if not self.executor:
            QMessageBox.critical(self, "错误", "未提供执行器实例")
            return
        
        # 禁用按钮
        self.install_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        
        # 清空输出
        self.output_text.clear()
        self._log(f"开始{action}: {package_name}")
        
        # 创建后台线程
        self.install_thread = PackageInstallThread(self.executor, package_name, action)
        self.install_thread.progress_signal.connect(self._log)
        self.install_thread.finished_signal.connect(self._on_action_finished)
        self.install_thread.start()
    
    def _on_action_finished(self, success: bool, output: str):
        """操作完成回调"""
        # 启用按钮
        self.install_btn.setEnabled(True)
        self.uninstall_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        
        # 显示输出
        self._log(output)
        
        if success:
            self._log("✓ 操作成功")
            QMessageBox.information(self, "成功", "操作完成")
            # 刷新列表
            self._load_packages()
            # 刷新环境信息
            self._load_environment_info()
        else:
            self._log("✗ 操作失败")
            QMessageBox.critical(self, "失败", f"操作失败:\n{output}")
        
        # 清理线程
        self.install_thread = None
    
    def _on_import_requirements(self):
        """从 requirements.txt 导入"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 requirements.txt",
            "",
            "Requirements Files (requirements.txt);;All Files (*)"
        )
        
        if not file_path:
            return
        
        # 确认
        reply = QMessageBox.question(
            self, "确认导入",
            f"确定要从 {file_path} 导入依赖吗？\n这将安装文件中列出的所有包。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 禁用按钮
        self.install_btn.setEnabled(False)
        self.uninstall_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.import_req_btn.setEnabled(False)
        self.export_req_btn.setEnabled(False)
        
        self._log(f"开始导入: {file_path}")
        
        # 在后台线程中执行
        class ImportThread(QThread):
            finished_signal = Signal(bool, str)
            progress_signal = Signal(str)
            
            def __init__(self, executor, file_path):
                super().__init__()
                self.executor = executor
                self.file_path = file_path
            
            def run(self):
                try:
                    self.progress_signal.emit("正在安装依赖...")
                    success, output = self.executor.install_requirements(self.file_path)
                    self.finished_signal.emit(success, output)
                except Exception as e:
                    self.finished_signal.emit(False, str(e))
        
        self.import_thread = ImportThread(self.executor, file_path)
        self.import_thread.progress_signal.connect(self._log)
        self.import_thread.finished_signal.connect(
            lambda success, output: self._on_import_finished(success, output, file_path)
        )
        self.import_thread.start()
    
    def _on_import_finished(self, success: bool, output: str, file_path: str):
        """导入完成回调"""
        # 启用按钮
        self.install_btn.setEnabled(True)
        self.uninstall_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.import_req_btn.setEnabled(True)
        self.export_req_btn.setEnabled(True)
        
        self._log(output)
        
        if success:
            self._log(f"✓ 导入成功: {file_path}")
            QMessageBox.information(self, "成功", "依赖导入完成")
            self._load_packages()
            self._load_environment_info()
        else:
            self._log(f"✗ 导入失败")
            QMessageBox.critical(self, "失败", f"导入失败:\n{output}")
    
    def _on_export_requirements(self):
        """导出到 requirements.txt"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 requirements.txt",
            "requirements.txt",
            "Requirements Files (requirements.txt);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            if self.executor.export_requirements(file_path):
                self._log(f"✓ 已导出到: {file_path}")
                QMessageBox.information(self, "成功", f"已导出到:\n{file_path}")
            else:
                QMessageBox.critical(self, "失败", "导出失败")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
    
    def _on_package_info(self, item: QListWidgetItem):
        """显示包详细信息"""
        pkg = item.data(Qt.UserRole)
        if not pkg:
            return
        
        name = pkg.get('name', 'Unknown')
        
        try:
            info = self.executor.get_package_info(name)
            if info:
                text = f"""
                <b>包名:</b> {info.get('name', 'N/A')}<br>
                <b>版本:</b> {info.get('version', 'N/A')}<br>
                <b>摘要:</b> {info.get('summary', 'N/A')}<br>
                <b>主页:</b> {info.get('home-page', 'N/A')}<br>
                <b>作者:</b> {info.get('author', 'N/A')}<br>
                <b>许可证:</b> {info.get('license', 'N/A')}<br>
                <b>位置:</b> {info.get('location', 'N/A')}
                """
                QMessageBox.information(self, f"包信息: {name}", text)
            else:
                QMessageBox.information(self, f"包信息: {name}", "无法获取详细信息")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"获取信息失败: {e}")
    
    def _show_context_menu(self, position):
        """显示右键菜单"""
        item = self.package_list.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        info_action = QAction("查看信息", self)
        info_action.triggered.connect(lambda: self._on_package_info(item))
        menu.addAction(info_action)
        
        menu.addSeparator()
        
        uninstall_action = QAction("卸载", self)
        uninstall_action.triggered.connect(self._on_uninstall)
        menu.addAction(uninstall_action)
        
        menu.exec(self.package_list.mapToGlobal(position))
    
    def _log(self, message: str):
        """添加日志"""
        self.output_text.append(message)
        # 滚动到底部
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def closeEvent(self, event):
        """关闭事件"""
        # 如果有正在进行的操作，询问是否取消
        if self.install_thread and self.install_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭",
                "有操作正在进行中，确定要关闭吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.install_thread.terminate()
                self.install_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


if __name__ == '__main__':
    # 测试
    import sys
    from PySide6.QtWidgets import QApplication
    from core.engine.embedded_executor import EmbeddedPythonExecutor
    
    app = QApplication(sys.argv)
    
    try:
        executor = EmbeddedPythonExecutor()
        dialog = PackageManagerDialog(executor=executor)
        dialog.exec()
    except RuntimeError as e:
        QMessageBox.critical(None, "错误", str(e))
    
    sys.exit(app.exec())