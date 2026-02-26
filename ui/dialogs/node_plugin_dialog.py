"""节点插件导出/导入对话框

功能特性：
1. 导出节点插件：自动解析源代码中的第三方库依赖
2. 导入节点插件：检测第三方库安装状态，支持一键安装缺失库
"""

import json
import os
import ast
import sys
from datetime import datetime
from typing import Dict, List, Any, Set, Tuple
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox,
    QCheckBox, QGroupBox, QScrollArea, QWidget, QFrame,
    QSplitter, QLineEdit, QTextEdit, QProgressDialog
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor

from core.nodes.node_library import (
    NODE_LIBRARY_CATEGORIZED, LOCAL_NODE_LIBRARY,
    CUSTOM_CATEGORIES, get_node_source_code
)
from utils.theme_manager import theme_manager


# Python 标准库列表（不需要安装）
PYTHON_STDLIB = {
    # 常用标准库
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
    'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect',
    'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd',
    'code', 'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
    'concurrent', 'configparser', 'contextlib', 'contextvars', 'copy', 'copyreg',
    'cProfile', 'crypt', 'csv', 'ctypes', 'curses', 'dataclasses', 'datetime',
    'dbm', 'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email',
    'encodings', 'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput',
    'fnmatch', 'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass',
    'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac',
    'html', 'http', 'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib', 'inspect',
    'io', 'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache',
    'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal', 'math',
    'mimetypes', 'mmap', 'modulefinder', 'multiprocessing', 'netrc', 'nis',
    'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev', 'pathlib',
    'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib',
    'poplib', 'posix', 'posixpath', 'pprint', 'profile', 'pstats', 'pty', 'pwd',
    'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 're', 'readline',
    'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 'secrets', 'select',
    'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtpd', 'smtplib',
    'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3', 'ssl', 'stat',
    'statistics', 'string', 'stringprep', 'struct', 'subprocess', 'sunau',
    'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile', 'telnetlib',
    'tempfile', 'termios', 'test', 'textwrap', 'threading', 'time', 'timeit',
    'tkinter', 'token', 'tokenize', 'trace', 'traceback', 'tracemalloc', 'tty',
    'turtle', 'turtledemo', 'types', 'typing', 'unicodedata', 'unittest', 'urllib',
    'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg',
    'winsound', 'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp', 'zipfile',
    'zipimport', 'zlib', 'zoneinfo',
    # 常用子模块
    'collections.abc', 'concurrent.futures', 'email.mime', 'http.client',
    'http.server', 'http.cookies', 'http.cookiejar', 'logging.config',
    'logging.handlers', 'os.path', 'urllib.request', 'urllib.parse',
    'urllib.error', 'urllib.robotparser', 'xml.etree', 'xml.dom', 'xml.sax',
}


def extract_imports_from_source(source_code: str) -> Set[str]:
    """从源代码中提取导入的第三方库名称
    
    Args:
        source_code: Python 源代码
        
    Returns:
        第三方库名称集合
    """
    imports = set()
    
    try:
        tree = ast.parse(source_code)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                # import xxx
                for alias in node.names:
                    module_name = alias.name.split('.')[0]  # 只取顶层模块名
                    imports.add(module_name)
                    
            elif isinstance(node, ast.ImportFrom):
                # from xxx import yyy
                if node.module:
                    module_name = node.module.split('.')[0]  # 只取顶层模块名
                    imports.add(module_name)
    
    except SyntaxError:
        pass  # 语法错误时返回空集合
    
    return imports


def filter_third_party_packages(imports: Set[str]) -> Set[str]:
    """过滤出第三方库（排除标准库和相对导入）
    
    Args:
        imports: 导入的模块名集合
        
    Returns:
        第三方库名称集合
    """
    third_party = set()
    
    for module_name in imports:
        # 排除空名称和相对导入
        if not module_name or module_name.startswith('.'):
            continue
        
        # 排除标准库
        if module_name in PYTHON_STDLIB:
            continue
        
        third_party.add(module_name)
    
    return third_party


def check_package_installed(package_name: str) -> bool:
    """检查包是否已安装
    
    Args:
        package_name: 包名
        
    Returns:
        是否已安装
    """
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def normalize_package_name(name: str) -> str:
    """规范化包名（处理 pip 包名和 import 名不同的情况）
    
    例如：
    - PIL -> Pillow
    - cv2 -> opencv-python
    - yaml -> pyyaml
    """
    # 常见的包名映射
    package_mappings = {
        'PIL': 'Pillow',
        'cv2': 'opencv-python',
        'yaml': 'PyYAML',
        'sklearn': 'scikit-learn',
        'bs4': 'beautifulsoup4',
        'dateutil': 'python-dateutil',
        'Crypto': 'pycryptodome',
        'OpenSSL': 'pyOpenSSL',
        'dotenv': 'python-dotenv',
        'selenium': 'selenium',
        'requests': 'requests',
        'numpy': 'numpy',
        'pandas': 'pandas',
        'matplotlib': 'matplotlib',
        'flask': 'Flask',
        'django': 'Django',
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'pydantic': 'pydantic',
        'sqlalchemy': 'SQLAlchemy',
        'tqdm': 'tqdm',
        'click': 'click',
        'jinja2': 'Jinja2',
        'lxml': 'lxml',
        'pillow': 'Pillow',
        'scipy': 'scipy',
        'sympy': 'sympy',
        'pytest': 'pytest',
        'aiohttp': 'aiohttp',
        'httpx': 'httpx',
        'redis': 'redis',
        'celery': 'celery',
        'boto3': 'boto3',
        'pymongo': 'pymongo',
        'mysql': 'mysql-connector-python',
        'psycopg2': 'psycopg2-binary',
        'playwright': 'playwright',
    }
    
    # 先检查是否在映射表中
    if name in package_mappings:
        return package_mappings[name]
    
    # 否则返回原始名称（小写）
    return name.lower()


class NodePluginExportDialog(QDialog):
    """节点插件导出对话框
    
    功能：
    - 显示本地节点库中的所有自定义节点（按分类分组）
    - 支持多选节点导出
    - 自动解析节点源代码中的第三方库依赖
    - 导出为JSON格式的插件包
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出节点插件")
        self.setMinimumSize(650, 550)
        self.resize(750, 600)
        
        self._selected_nodes: Dict[str, List[str]] = {}  # category -> [node_names]
        
        self._setup_ui()
        self._load_nodes()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 说明标签
        info_label = QLabel("选择要导出的自定义节点：")
        info_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(info_label)
        
        # 分类说明
        hint_label = QLabel("提示：节点将按分类结构导出，导入时会保留分类层级关系。第三方库依赖将自动解析。")
        hint_label.setStyleSheet("color: #888; font-size: 11px;")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
        
        # 节点树（按分类显示）
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderLabels(["节点名称", "类型", "依赖库"])
        self.node_tree.setColumnWidth(0, 200)
        self.node_tree.setColumnWidth(1, 80)
        self.node_tree.setColumnWidth(2, 150)
        self.node_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #444;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background-color: #3a3a4a;
            }
        """)
        layout.addWidget(self.node_tree)
        
        # 选择统计
        self.stats_label = QLabel("已选择 0 个节点")
        self.stats_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(self.stats_label)
        
        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(deselect_all_btn)
        
        btn_layout.addStretch()
        
        export_btn = QPushButton("📦 导出插件包")
        export_btn.setObjectName("btn_primary")
        export_btn.clicked.connect(self._export_plugin)
        btn_layout.addWidget(export_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _load_nodes(self):
        """加载自定义节点到树中"""
        self.node_tree.clear()
        self._category_items = {}  # category -> QTreeWidgetItem
        self._node_items = {}  # (category, node_name) -> QTreeWidgetItem
        
        for category in CUSTOM_CATEGORIES:
            if category not in NODE_LIBRARY_CATEGORIZED:
                continue
            
            nodes = NODE_LIBRARY_CATEGORIZED[category]
            if not nodes:
                continue
            
            # 创建分类项
            cat_item = QTreeWidgetItem(self.node_tree, [category, "分类", ""])
            cat_item.setFlags(cat_item.flags() | Qt.ItemIsUserCheckable)
            cat_item.setCheckState(0, Qt.Unchecked)
            cat_item.setData(0, Qt.UserRole, "category")
            cat_item.setData(0, Qt.UserRole + 1, category)
            cat_item.setExpanded(True)
            
            self._category_items[category] = cat_item
            
            # 添加节点
            for node_name in nodes:
                # 获取源代码并解析依赖
                source_code = get_node_source_code(node_name)
                imports = extract_imports_from_source(source_code)
                third_party = filter_third_party_packages(imports)
                deps_str = ", ".join(sorted(third_party)) if third_party else "无"
                
                node_item = QTreeWidgetItem(cat_item, [node_name, "自定义节点", deps_str])
                node_item.setFlags(node_item.flags() | Qt.ItemIsUserCheckable)
                node_item.setCheckState(0, Qt.Unchecked)
                node_item.setData(0, Qt.UserRole, "node")
                node_item.setData(0, Qt.UserRole + 1, category)
                node_item.setData(0, Qt.UserRole + 2, node_name)
                node_item.setData(0, Qt.UserRole + 3, list(third_party))  # 存储依赖列表
                
                self._node_items[(category, node_name)] = node_item
        
        # 连接点击事件
        self.node_tree.itemClicked.connect(self._on_item_clicked)
        
        # 如果没有自定义节点
        if not self._category_items:
            empty_item = QTreeWidgetItem(self.node_tree, ["暂无自定义节点可导出", "", ""])
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEnabled)
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """处理项目点击事件"""
        item_type = item.data(0, Qt.UserRole)
        
        if item_type == "category":
            # 分类项：同步子节点的选中状态
            check_state = item.checkState(0)
            for i in range(item.childCount()):
                child = item.child(i)
                child.setCheckState(0, check_state)
        
        self._update_stats()
    
    def _update_stats(self):
        """更新选择统计"""
        count = 0
        for (category, node_name), item in self._node_items.items():
            if item.checkState(0) == Qt.Checked:
                count += 1
        
        self.stats_label.setText(f"已选择 {count} 个节点")
    
    def _select_all(self):
        """全选"""
        for item in self._node_items.values():
            item.setCheckState(0, Qt.Checked)
        for item in self._category_items.values():
            item.setCheckState(0, Qt.Checked)
        self._update_stats()
    
    def _deselect_all(self):
        """取消全选"""
        for item in self._node_items.values():
            item.setCheckState(0, Qt.Unchecked)
        for item in self._category_items.values():
            item.setCheckState(0, Qt.Unchecked)
        self._update_stats()
    
    def _get_selected_nodes(self) -> Dict[str, List[str]]:
        """获取选中的节点"""
        selected = {}
        for (category, node_name), item in self._node_items.items():
            if item.checkState(0) == Qt.Checked:
                if category not in selected:
                    selected[category] = []
                selected[category].append(node_name)
        return selected
    
    def _export_plugin(self):
        """导出节点插件包"""
        selected_nodes = self._get_selected_nodes()
        
        if not selected_nodes:
            QMessageBox.warning(self, "提示", "请至少选择一个节点进行导出。")
            return
        
        # 计算总节点数
        total_count = sum(len(nodes) for nodes in selected_nodes.values())
        
        # 收集所有依赖
        all_dependencies = set()
        for (category, node_name), item in self._node_items.items():
            if item.checkState(0) == Qt.Checked:
                deps = item.data(0, Qt.UserRole + 3) or []
                all_dependencies.update(deps)
        
        # 选择保存路径
        default_name = f"node_plugin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "保存节点插件包",
            default_name,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not filepath:
            return
        
        # 确保文件扩展名
        if not filepath.endswith('.json'):
            filepath += '.json'
        
        # 构建插件数据
        plugin_data = {
            "plugin_type": "node_plugin",
            "version": "1.1",  # 版本升级，支持依赖
            "created_at": datetime.now().isoformat(),
            "node_count": total_count,
            "dependencies": sorted(list(all_dependencies)),  # 第三方库依赖列表
            "categories": {}
        }
        
        for category, node_names in selected_nodes.items():
            plugin_data["categories"][category] = {
                "nodes": []
            }
            
            for node_name in node_names:
                func = LOCAL_NODE_LIBRARY.get(node_name)
                if not func:
                    continue
                
                # 获取源代码
                source_code = get_node_source_code(node_name)
                
                # 解析依赖
                imports = extract_imports_from_source(source_code)
                third_party = filter_third_party_packages(imports)
                
                # 获取函数签名信息
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                return_type = str(sig.return_annotation) if sig.return_annotation != inspect.Parameter.empty else ""
                
                node_data = {
                    "name": node_name,
                    "source_code": source_code,
                    "parameters": params,
                    "return_type": return_type,
                    "docstring": inspect.getdoc(func) or "",
                    "dependencies": list(third_party)  # 单个节点的依赖
                }
                
                plugin_data["categories"][category]["nodes"].append(node_data)
        
        # 保存文件
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(plugin_data, f, ensure_ascii=False, indent=2)
            
            dep_info = f"\n\n包含 {len(all_dependencies)} 个第三方库依赖：{', '.join(sorted(all_dependencies))}" if all_dependencies else ""
            
            QMessageBox.information(
                self, "导出成功",
                f"已成功导出 {total_count} 个节点到:\n{filepath}{dep_info}"
            )
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出失败:\n{e}")


class DependencyCheckThread(QThread):
    """依赖检查后台线程"""
    finished_signal = Signal(dict)  # {package_name: is_installed}
    
    def __init__(self, packages: list):
        super().__init__()
        self.packages = packages
    
    def run(self):
        result = {}
        for pkg in self.packages:
            result[pkg] = check_package_installed(pkg)
        self.finished_signal.emit(result)


class PackageInstallThread(QThread):
    """批量包安装后台线程"""
    progress_signal = Signal(str)
    finished_signal = Signal(bool, str, list)  # 成功标志, 输出信息, 成功安装的包列表
    
    def __init__(self, packages: list, executor=None):
        super().__init__()
        self.packages = packages
        self.executor = executor
        self.installed_packages = []
    
    def run(self):
        if not self.packages:
            self.finished_signal.emit(True, "没有需要安装的包", [])
            return
        
        self.progress_signal.emit(f"准备安装 {len(self.packages)} 个依赖包...")
        
        if self.executor:
            # 使用嵌入式 Python 执行器安装
            for pkg in self.packages:
                pip_name = normalize_package_name(pkg)
                self.progress_signal.emit(f"正在安装 {pkg} ({pip_name})...")
                
                try:
                    success, output = self.executor.install_package(pip_name)
                    if success:
                        self.installed_packages.append(pkg)
                        self.progress_signal.emit(f"✓ {pkg} 安装成功")
                    else:
                        self.progress_signal.emit(f"✗ {pkg} 安装失败: {output}")
                except Exception as e:
                    self.progress_signal.emit(f"✗ {pkg} 安装异常: {str(e)}")
            
            result_msg = f"完成！成功安装 {len(self.installed_packages)}/{len(self.packages)} 个包"
            self.finished_signal.emit(len(self.installed_packages) > 0, result_msg, self.installed_packages)
        else:
            # 没有执行器
            self.finished_signal.emit(False, "未提供执行器实例", [])


class NodePluginImportDialog(QDialog):
    """节点插件导入对话框
    
    功能：
    - 选择并读取JSON格式的插件包
    - 显示插件包中的分类和节点信息
    - 自动检测第三方库依赖并显示安装状态
    - 支持一键安装缺失的依赖库
    - 支持查重：已存在的节点灰色显示，不可勾选
    - 支持选择性导入：可勾选单个节点或全部导入
    """
    
    # 信号：导入完成后发送，通知刷新节点树
    import_completed = Signal()
    
    def __init__(self, parent=None, plugin_path: str = None, executor=None):
        super().__init__(parent)
        self.setWindowTitle("导入节点插件")
        self.setMinimumSize(800, 700)
        self.resize(900, 750)
        
        self._plugin_path = plugin_path
        self._plugin_data = None
        self._existing_nodes: Set[str] = set()  # 已存在的节点名称
        self._executor = executor  # 嵌入式 Python 执行器
        self._dependency_status: Dict[str, bool] = {}  # 依赖包安装状态
        self._install_thread: PackageInstallThread = None
        self._check_thread: DependencyCheckThread = None
        
        self._setup_ui()
        
        # 如果提供了插件路径，自动加载
        if plugin_path:
            self._load_plugin_file(plugin_path)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 插件文件选择
        file_group = QGroupBox("插件文件")
        file_layout = QHBoxLayout(file_group)
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        self.file_path_edit.setPlaceholderText("请选择插件包文件...")
        file_layout.addWidget(self.file_path_edit)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_plugin_file)
        file_layout.addWidget(browse_btn)
        
        layout.addWidget(file_group)
        
        # 插件信息
        self.info_frame = QFrame()
        info_layout = QVBoxLayout(self.info_frame)
        
        self.plugin_info_label = QLabel("请先选择插件包文件")
        self.plugin_info_label.setStyleSheet("color: #888;")
        info_layout.addWidget(self.plugin_info_label)
        
        layout.addWidget(self.info_frame)
        
        # ============ 依赖库区域 ============
        self.dep_group = QGroupBox("📦 第三方库依赖")
        dep_layout = QVBoxLayout(self.dep_group)
        
        # 依赖状态标签
        self.dep_status_label = QLabel("加载插件后显示依赖信息...")
        self.dep_status_label.setStyleSheet("font-weight: bold;")
        self.dep_status_label.setWordWrap(True)
        dep_layout.addWidget(self.dep_status_label)
        
        # 依赖列表
        self.dep_tree = QTreeWidget()
        self.dep_tree.setHeaderLabels(["库名称", "安装状态", "安装包名"])
        self.dep_tree.setColumnWidth(0, 200)
        self.dep_tree.setColumnWidth(1, 100)
        self.dep_tree.setMaximumHeight(150)
        self.dep_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #444;
                border-radius: 4px;
            }
        """)
        dep_layout.addWidget(self.dep_tree)
        
        # 依赖安装按钮
        dep_btn_layout = QHBoxLayout()
        
        self.install_deps_btn = QPushButton("🔧 现在安装缺失依赖")
        self.install_deps_btn.setObjectName("btn_primary")
        self.install_deps_btn.setToolTip("安装所有未安装的第三方库依赖")
        self.install_deps_btn.clicked.connect(self._install_missing_dependencies)
        self.install_deps_btn.setEnabled(False)
        dep_btn_layout.addWidget(self.install_deps_btn)
        
        self.skip_deps_btn = QPushButton("⏭ 稍后安装")
        self.skip_deps_btn.setToolTip("跳过依赖安装，仅导入节点")
        self.skip_deps_btn.clicked.connect(self._skip_dependencies)
        dep_btn_layout.addWidget(self.skip_deps_btn)
        
        dep_btn_layout.addStretch()
        
        dep_layout.addLayout(dep_btn_layout)
        
        layout.addWidget(self.dep_group)
        
        # ============ 节点列表区域 ============
        node_group = QGroupBox("📋 节点列表")
        node_layout = QVBoxLayout(node_group)
        
        list_label = QLabel("插件内容预览（灰色表示已存在的节点）:")
        list_label.setStyleSheet("font-size: 11px; color: #888;")
        node_layout.addWidget(list_label)
        
        # 节点树
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderLabels(["节点名称", "状态", "分类"])
        self.node_tree.setColumnWidth(0, 200)
        self.node_tree.setColumnWidth(1, 100)
        self.node_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #444;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:selected {
                background-color: #3a3a4a;
            }
        """)
        node_layout.addWidget(self.node_tree)
        
        # 选择统计
        self.stats_label = QLabel("已选择 0 个节点进行导入")
        self.stats_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        node_layout.addWidget(self.stats_label)
        
        layout.addWidget(node_group, 1)  # 节点区域可扩展
        
        # ============ 按钮行 ============
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        select_all_btn = QPushButton("全选可用")
        select_all_btn.setToolTip("选择所有可导入的节点（排除已存在的）")
        select_all_btn.clicked.connect(self._select_all_available)
        btn_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(self._deselect_all)
        btn_layout.addWidget(deselect_all_btn)
        
        btn_layout.addStretch()
        
        import_btn = QPushButton("📥 导入选中节点")
        import_btn.setObjectName("btn_primary")
        import_btn.clicked.connect(self._import_selected)
        btn_layout.addWidget(import_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _browse_plugin_file(self):
        """浏览选择插件文件"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "选择节点插件包",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filepath:
            self._load_plugin_file(filepath)
    
    def _load_plugin_file(self, filepath: str):
        """加载插件文件"""
        self.file_path_edit.setText(filepath)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 验证插件格式
            if data.get("plugin_type") != "node_plugin":
                QMessageBox.warning(self, "格式错误", "所选文件不是有效的节点插件包。")
                return
            
            self._plugin_data = data
            
            # 更新插件信息
            created_at = data.get("created_at", "未知")
            node_count = data.get("node_count", 0)
            categories_count = len(data.get("categories", {}))
            version = data.get("version", "1.0")
            
            self.plugin_info_label.setText(
                f"📦 插件包信息\n"
                f"版本: {version} | 创建时间: {created_at}\n"
                f"包含分类: {categories_count} 个 | 节点总数: {node_count} 个"
            )
            self.plugin_info_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            # 加载依赖信息
            self._load_dependencies()
            
            # 加载节点树
            self._load_nodes_to_tree()
            
        except json.JSONDecodeError:
            QMessageBox.critical(self, "读取失败", "文件不是有效的 JSON 格式。")
        except Exception as e:
            QMessageBox.critical(self, "读取失败", f"读取文件失败:\n{e}")
    
    def _load_dependencies(self):
        """加载并检查依赖"""
        self.dep_tree.clear()
        self._dependency_status.clear()
        
        if not self._plugin_data:
            return
        
        dependencies = self._plugin_data.get("dependencies", [])
        
        if not dependencies:
            self.dep_status_label.setText("✓ 此插件没有第三方库依赖")
            self.dep_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.install_deps_btn.setEnabled(False)
            return
        
        # 显示依赖列表（初始状态为检查中）
        for dep in dependencies:
            item = QTreeWidgetItem(self.dep_tree, [dep, "检查中...", normalize_package_name(dep)])
            item.setForeground(1, QColor("#888888"))
        
        # 在后台线程中检查依赖安装状态
        self._check_thread = DependencyCheckThread(dependencies)
        self._check_thread.finished_signal.connect(self._on_dependency_check_finished)
        self._check_thread.start()
    
    def _on_dependency_check_finished(self, status: dict):
        """依赖检查完成回调"""
        self._dependency_status = status
        
        installed_count = sum(1 for installed in status.values() if installed)
        missing_count = len(status) - installed_count
        
        # 更新依赖列表显示
        self.dep_tree.clear()
        for dep, is_installed in status.items():
            item = QTreeWidgetItem(self.dep_tree, [dep, "已安装" if is_installed else "未安装", normalize_package_name(dep)])
            
            if is_installed:
                item.setForeground(1, QColor("#4CAF50"))
            else:
                item.setForeground(1, QColor("#FF5555"))
        
        # 更新状态标签
        if missing_count == 0:
            self.dep_status_label.setText(f"✓ 所有依赖已安装 ({installed_count}/{len(status)})")
            self.dep_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.install_deps_btn.setEnabled(False)
        else:
            self.dep_status_label.setText(
                f"⚠ 缺少 {missing_count} 个依赖库，是否一键安装？\n"
                f"已安装: {installed_count}/{len(status)}"
            )
            self.dep_status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
            self.install_deps_btn.setEnabled(True)
    
    def _install_missing_dependencies(self):
        """安装缺失的依赖"""
        if not self._dependency_status:
            QMessageBox.warning(self, "提示", "请先选择插件包文件。")
            return
        
        # 获取未安装的依赖
        missing_packages = [pkg for pkg, installed in self._dependency_status.items() if not installed]
        
        if not missing_packages:
            QMessageBox.information(self, "提示", "所有依赖已安装，无需操作。")
            return
        
        # 确认安装
        reply = QMessageBox.question(
            self, "确认安装",
            f"将安装以下 {len(missing_packages)} 个依赖库：\n\n"
            f"{', '.join(missing_packages)}\n\n"
            "是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 检查是否有执行器
        if not self._executor:
            # 尝试获取执行器
            try:
                from core.engine.embedded_executor import get_executor
                self._executor = get_executor()
            except RuntimeError as e:
                QMessageBox.warning(
                    self, "环境未初始化",
                    f"嵌入式 Python 环境未初始化。\n\n{e}\n\n"
                    "请先在主界面点击'初始化环境'按钮。"
                )
                return
        
        # 禁用按钮
        self.install_deps_btn.setEnabled(False)
        self.skip_deps_btn.setEnabled(False)
        
        # 创建安装线程
        self._install_thread = PackageInstallThread(missing_packages, self._executor)
        self._install_thread.progress_signal.connect(self._on_install_progress)
        self._install_thread.finished_signal.connect(self._on_install_finished)
        self._install_thread.start()
    
    def _on_install_progress(self, message: str):
        """安装进度回调"""
        print(message)
    
    def _on_install_finished(self, success: bool, message: str, installed_packages: list):
        """安装完成回调"""
        # 启用按钮
        self.install_deps_btn.setEnabled(True)
        self.skip_deps_btn.setEnabled(True)
        
        print(message)
        
        if success:
            QMessageBox.information(self, "安装完成", message)
            # 重新检查依赖状态
            dependencies = self._plugin_data.get("dependencies", [])
            if dependencies:
                self._check_thread = DependencyCheckThread(dependencies)
                self._check_thread.finished_signal.connect(self._on_dependency_check_finished)
                self._check_thread.start()
        else:
            QMessageBox.warning(self, "安装失败", message)
        
        self._install_thread = None
    
    def _skip_dependencies(self):
        """跳过依赖安装"""
        reply = QMessageBox.question(
            self, "确认跳过",
            "跳过依赖安装可能导致部分节点无法正常使用。\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 直接进入节点导入流程
            pass
    
    def _load_nodes_to_tree(self):
        """加载节点到树中"""
        self.node_tree.clear()
        self._category_items = {}
        self._node_items = {}
        self._existing_nodes.clear()
        
        if not self._plugin_data:
            return
        
        # 获取当前已存在的节点
        self._existing_nodes = set(LOCAL_NODE_LIBRARY.keys())
        
        categories = self._plugin_data.get("categories", {})
        
        for category, category_data in categories.items():
            nodes = category_data.get("nodes", [])
            
            # 创建分类项
            cat_item = QTreeWidgetItem(self.node_tree, [category, "", ""])
            cat_item.setData(0, Qt.UserRole, "category")
            cat_item.setData(0, Qt.UserRole + 1, category)
            cat_item.setExpanded(True)
            
            self._category_items[category] = cat_item
            
            # 添加节点
            for node_data in nodes:
                node_name = node_data.get("name", "未知")
                is_existing = node_name in self._existing_nodes
                
                node_item = QTreeWidgetItem(cat_item)
                node_item.setText(0, node_name)
                
                if is_existing:
                    node_item.setText(1, "已存在")
                    node_item.setForeground(0, QColor("#888888"))
                    node_item.setForeground(1, QColor("#FF5555"))
                    node_item.setForeground(2, QColor("#888888"))
                    node_item.setFlags(node_item.flags() & ~Qt.ItemIsUserCheckable)
                    node_item.setToolTip(0, f"节点 '{node_name}' 已存在于本地节点库中")
                else:
                    node_item.setText(1, "可导入")
                    node_item.setForeground(1, QColor("#4CAF50"))
                    node_item.setFlags(node_item.flags() | Qt.ItemIsUserCheckable)
                    node_item.setCheckState(0, Qt.Unchecked)
                
                node_item.setText(2, category)
                node_item.setData(0, Qt.UserRole, "node")
                node_item.setData(0, Qt.UserRole + 1, category)
                node_item.setData(0, Qt.UserRole + 2, node_name)
                node_item.setData(0, Qt.UserRole + 3, node_data)  # 存储完整节点数据
                
                self._node_items[(category, node_name)] = node_item
            
            # 更新分类项的状态
            existing_count = sum(
                1 for i in range(cat_item.childCount())
                if cat_item.child(i).text(1) == "已存在"
            )
            total_count = cat_item.childCount()
            cat_item.setText(1, f"{total_count - existing_count}/{total_count}")
        
        self._update_stats()
    
    def _update_stats(self):
        """更新选择统计"""
        count = 0
        for (category, node_name), item in self._node_items.items():
            if item.flags() & Qt.ItemIsUserCheckable and item.checkState(0) == Qt.Checked:
                count += 1
        
        self.stats_label.setText(f"已选择 {count} 个节点进行导入")
    
    def _select_all_available(self):
        """全选所有可导入的节点"""
        for item in self._node_items.values():
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(0, Qt.Checked)
        self._update_stats()
    
    def _deselect_all(self):
        """取消全选"""
        for item in self._node_items.values():
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(0, Qt.Unchecked)
        self._update_stats()
    
    def _get_selected_nodes(self) -> List[Dict[str, Any]]:
        """获取选中的节点数据"""
        selected = []
        for (category, node_name), item in self._node_items.items():
            if item.flags() & Qt.ItemIsUserCheckable and item.checkState(0) == Qt.Checked:
                node_data = item.data(0, Qt.UserRole + 3)
                if node_data:
                    selected.append({
                        "category": category,
                        "data": node_data
                    })
        return selected
    
    def _import_selected(self):
        """导入选中的节点"""
        selected_nodes = self._get_selected_nodes()
        
        if not selected_nodes:
            QMessageBox.warning(self, "提示", "请至少选择一个节点进行导入。")
            return
        
        # 检查依赖状态
        missing_deps = [pkg for pkg, installed in self._dependency_status.items() if not installed]
        if missing_deps:
            reply = QMessageBox.question(
                self, "依赖警告",
                f"以下依赖库尚未安装：\n{', '.join(missing_deps)}\n\n"
                "部分节点可能无法正常使用。是否继续导入？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        # 确认导入
        reply = QMessageBox.question(
            self, "确认导入",
            f"确定要导入 {len(selected_nodes)} 个节点吗？\n\n"
            "导入后会自动保存到本地节点库。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 执行导入
        success_count = 0
        fail_count = 0
        
        for node_info in selected_nodes:
            category = node_info["category"]
            node_data = node_info["data"]
            
            try:
                node_name = node_data.get("name")
                source_code = node_data.get("source_code", "")
                
                # 验证和编译源代码
                import ast
                import inspect
                
                tree = ast.parse(source_code)
                func_defs = [node for node in ast.iter_child_nodes(tree) 
                           if isinstance(node, ast.FunctionDef)]
                
                if len(func_defs) != 1:
                    raise ValueError("源代码必须定义且仅定义一个函数")
                
                func_name = func_defs[0].name

                # 编译执行
                # 注意：必须提供 __builtins__，否则 import 语句在某些环境下会失败
                namespace = {'__builtins__': __builtins__}
                exec(compile(tree, f"<plugin_node_{node_name}>", "exec"), namespace)
                func = namespace[func_name]
                
                if not callable(func):
                    raise ValueError("定义的不是可调用函数")
                
                # 保存源代码到函数属性
                func._custom_source = source_code
                
                # 添加到库中
                from core.nodes.node_library import add_node_to_library
                add_node_to_library(node_name, func, category)
                
                success_count += 1
                
            except Exception as e:
                print(f"导入节点 '{node_data.get('name', '未知')}' 失败: {e}")
                fail_count += 1
        
        # 保存到持久化存储
        if success_count > 0:
            from storage.custom_node_storage import save_custom_nodes
            save_custom_nodes()
        
        # 显示结果
        if fail_count == 0:
            QMessageBox.information(
                self, "导入成功",
                f"成功导入 {success_count} 个节点！"
            )
            self.import_completed.emit()
            self.accept()
        else:
            QMessageBox.warning(
                self, "导入完成",
                f"成功导入 {success_count} 个节点\n"
                f"失败 {fail_count} 个节点\n\n"
                "请查看控制台了解失败详情。"
            )
            if success_count > 0:
                self.import_completed.emit()
                self.accept()
    
    def closeEvent(self, event):
        """关闭事件"""
        # 清理线程
        if self._check_thread and self._check_thread.isRunning():
            self._check_thread.terminate()
            self._check_thread.wait()
        
        if self._install_thread and self._install_thread.isRunning():
            reply = QMessageBox.question(
                self, "确认关闭",
                "依赖安装正在进行中，确定要关闭吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._install_thread.terminate()
                self._install_thread.wait()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()