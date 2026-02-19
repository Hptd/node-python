"""代码安全沙箱检查器

用于检查自定义节点代码的安全性，防止执行危险操作。
支持 AST 级别的代码分析和白名单机制。
"""

import ast
import builtins
import re
from typing import List, Set, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class SecurityCheckResult:
    """安全检查结果"""
    is_safe: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    
    def __bool__(self):
        return self.is_safe


class SandboxChecker(ast.NodeVisitor):
    """代码沙箱检查器
    
    通过 AST 分析检查代码安全性，包括：
    - 禁止导入危险模块
    - 禁止调用危险函数
    - 限制文件系统操作
    - 限制网络操作
    """
    
    # 危险模块（完全禁止导入）
    FORBIDDEN_MODULES: Set[str] = {
        'os', 'sys', 'subprocess', 'socket', 'ctypes', 'mmap',
        'urllib', 'http', 'ftplib', 'smtplib', 'telnetlib',
        'pickle', 'cPickle', 'marshal', 'shelve',
        'multiprocessing', 'threading', '_thread',
        'imp', 'importlib', 'runpy', 'modulefinder',
        'site', 'builtins', '__builtin__',
    }
    
    # 需要警告的模块（可能危险，但某些场景有用）
    WARNING_MODULES: Set[str] = {
        'requests', 'urllib3', 'httpx',  # 网络请求
        'pymongo', 'psycopg2', 'mysql',  # 数据库
        'paramiko', 'fabric',  # SSH
        'pyautogui',  # 自动化控制
    }
    
    # 危险内置函数
    FORBIDDEN_BUILTINS: Set[str] = {
        'eval', 'exec', 'compile', '__import__',
        'open', 'input', 'raw_input',
        'exit', 'quit',
        'help', 'copyright', 'credits', 'license',
    }
    
    # 允许的标准库模块（白名单模式）
    ALLOWED_MODULES: Set[str] = {
        # 基础类型
        'abc', 'array', 'bisect', 'collections', 'copy', 'dataclasses',
        'enum', 'functools', 'heapq', 'itertools', 'json', 'math',
        'numbers', 'operator', 'pprint', 'random', 're', 'statistics',
        'string', 'time', 'datetime', 'decimal', 'fractions', 'typing',
        'uuid', 'hashlib', 'base64', 'binascii', 'struct',
        
        # 数据结构
        'csv', 'html', 'xml', 'xml.etree.ElementTree',
        
        # 算法
        'difflib', 'graphlib', 'zoneinfo',
    }
    
    # 允许的内置函数
    ALLOWED_BUILTINS: Set[str] = {
        'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
        'callable', 'chr', 'classmethod', 'complex', 'delattr', 'dict',
        'dir', 'divmod', 'enumerate', 'filter', 'float', 'format',
        'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'hex',
        'id', 'int', 'isinstance', 'issubclass', 'iter', 'len', 'list',
        'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object',
        'oct', 'ord', 'pow', 'print', 'property', 'range', 'repr',
        'reversed', 'round', 'set', 'setattr', 'slice', 'sorted',
        'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars',
        'zip', 'True', 'False', 'None',
    }
    
    def __init__(self, allowed_extra_modules: Optional[List[str]] = None):
        """初始化检查器
        
        Args:
            allowed_extra_modules: 额外允许的模块列表
        """
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.imports: List[str] = []
        self.allowed_modules = self.ALLOWED_MODULES.copy()
        
        if allowed_extra_modules:
            self.allowed_modules.update(allowed_extra_modules)
    
    def check_code(self, code: str) -> SecurityCheckResult:
        """检查代码安全性
        
        Args:
            code: Python 代码字符串
        
        Returns:
            SecurityCheckResult 包含检查结果
        """
        self.errors = []
        self.warnings = []
        self.imports = []
        
        try:
            # 解析 AST
            tree = ast.parse(code)
            
            # 检查是否包含多个顶层函数
            functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            if len(functions) > 1:
                self.errors.append(f"代码中包含 {len(functions)} 个函数，只允许定义一个函数")
            
            if len(functions) == 0:
                self.errors.append("代码中未找到函数定义")
            
            # 遍历 AST
            self.visit(tree)
            
        except SyntaxError as e:
            self.errors.append(f"语法错误: {e}")
        except Exception as e:
            self.errors.append(f"解析错误: {e}")
        
        return SecurityCheckResult(
            is_safe=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            imports=self.imports
        )
    
    def visit_Import(self, node: ast.Import):
        """检查 import 语句"""
        for alias in node.names:
            module_name = alias.name.split('.')[0]
            self._check_module(module_name, node)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """检查 from ... import 语句"""
        if node.module:
            module_name = node.module.split('.')[0]
            self._check_module(module_name, node)
            
            # 记录导入
            for alias in node.names:
                self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)
    
    def _check_module(self, module_name: str, node: ast.AST):
        """检查模块是否允许导入"""
        # 检查是否在禁止列表
        if module_name in self.FORBIDDEN_MODULES:
            self.errors.append(f"禁止导入危险模块: {module_name}")
            return
        
        # 检查是否在警告列表
        if module_name in self.WARNING_MODULES:
            self.warnings.append(f"导入的模块 '{module_name}' 可能包含危险操作，请谨慎使用")
        
        # 检查是否在白名单
        if module_name not in self.allowed_modules:
            self.warnings.append(f"导入的模块 '{module_name}' 未在允许列表中，可能需要管理员审核")
        
        # 记录导入
        self.imports.append(module_name)
    
    def visit_Call(self, node: ast.Call):
        """检查函数调用"""
        # 检查是否调用了危险内置函数
        if isinstance(node.func, ast.Name):
            if node.func.id in self.FORBIDDEN_BUILTINS:
                self.errors.append(f"禁止调用危险函数: {node.func.id}()")
        
        # 检查是否调用了 open() 等文件操作
        if isinstance(node.func, ast.Name) and node.func.id == 'open':
            self.warnings.append("代码中使用了 open() 函数，可能涉及文件系统操作")
        
        self.generic_visit(node)
    
    def visit_Expr(self, node: ast.Expr):
        """检查表达式语句"""
        # 检查是否是单独的函数调用（可能产生副作用）
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name):
                func_name = node.value.func.id
                # 检查是否是危险的函数
                if func_name in ('eval', 'exec'):
                    self.errors.append(f"禁止直接调用 {func_name}()")
        
        self.generic_visit(node)
    
    def visit_Exec(self, node: ast.Exec):
        """检查 exec 语句（Python 2）"""
        self.errors.append("禁止使用 exec 语句")
        self.generic_visit(node)


def check_code_safety(
    code: str, 
    allowed_modules: Optional[List[str]] = None
) -> SecurityCheckResult:
    """便捷函数：检查代码安全性
    
    Args:
        code: Python 代码字符串
        allowed_modules: 额外允许的模块列表
    
    Returns:
        SecurityCheckResult
    
    示例:
        >>> result = check_code_safety("import requests\ndef test(): pass")
        >>> if not result.is_safe:
        ...     print("错误:", result.errors)
    """
    checker = SandboxChecker(allowed_modules)
    return checker.check_code(code)


def extract_imports(code: str) -> List[str]:
    """提取代码中导入的模块
    
    Args:
        code: Python 代码字符串
    
    Returns:
        导入的模块列表
    """
    try:
        tree = ast.parse(code)
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split('.')[0])
        
        return list(set(imports))
    
    except SyntaxError:
        return []


def execute_in_sandbox(
    code: str,
    args: Dict[str, Any],
    allowed_modules: Optional[List[str]] = None,
    timeout: int = 30
) -> Any:
    """在沙箱中执行代码（简单版本，用于内置节点）
    
    注意：此函数在当前进程中执行，仅适用于可信代码。
    对于不可信代码，请使用 embedded_executor 在子进程中执行。
    
    Args:
        code: 函数代码
        args: 函数参数
        allowed_modules: 允许的模块
        timeout: 超时时间（仅作参考，实际无法强制超时）
    
    Returns:
        函数执行结果
    """
    # 安全检查
    result = check_code_safety(code, allowed_modules)
    if not result.is_safe:
        raise SecurityError(f"代码安全检查失败: {result.errors}")
    
    # 提取函数名
    tree = ast.parse(code)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if not functions:
        raise ValueError("代码中未找到函数定义")
    
    func_name = functions[0].name
    
    # 创建受限环境
    safe_builtins = {
        name: getattr(builtins, name)
        for name in SandboxChecker.ALLOWED_BUILTINS
        if hasattr(builtins, name)
    }
    
    namespace = {'__builtins__': safe_builtins}
    
    # 导入允许的模块
    if allowed_modules:
        for mod_name in allowed_modules:
            try:
                namespace[mod_name] = __import__(mod_name)
            except ImportError:
                pass
    
    # 执行代码
    exec(code, namespace)
    
    # 调用函数
    if func_name not in namespace:
        raise ValueError(f"函数 {func_name} 未定义")
    
    return namespace[func_name](**args)


class SecurityError(Exception):
    """安全错误异常"""
    pass


# ==================== 便捷函数 ====================

def is_safe_code(code: str, allowed_modules: Optional[List[str]] = None) -> bool:
    """快速检查代码是否安全
    
    示例:
        >>> if is_safe_code(user_code):
        ...     execute(user_code)
        ... else:
        ...     print("代码不安全")
    """
    result = check_code_safety(code, allowed_modules)
    return result.is_safe


def get_code_warnings(code: str, allowed_modules: Optional[List[str]] = None) -> List[str]:
    """获取代码警告信息"""
    result = check_code_safety(code, allowed_modules)
    return result.warnings


def validate_node_code(
    code: str,
    require_single_function: bool = True,
    allowed_modules: Optional[List[str]] = None
) -> Tuple[bool, List[str]]:
    """验证节点代码
    
    Args:
        code: 代码字符串
        require_single_function: 是否要求只能有一个函数
        allowed_modules: 允许的模块
    
    Returns:
        (是否有效, 错误信息列表)
    """
    errors = []
    
    # 1. 语法检查
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"语法错误: {e}"]
    
    # 2. 函数数量检查
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if require_single_function:
        if len(functions) == 0:
            return False, ["代码中必须包含一个函数定义"]
        if len(functions) > 1:
            return False, [f"代码中只能包含一个函数定义，当前有 {len(functions)} 个"]
    
    # 3. 安全检查
    result = check_code_safety(code, allowed_modules)
    if not result.is_safe:
        errors.extend(result.errors)
    
    return len(errors) == 0, errors


# ==================== 测试 ====================

if __name__ == '__main__':
    # 测试代码
    test_cases = [
        # 安全代码
        ("""
def hello(name: str) -> str:
    import json
    return f"Hello, {name}!"
""", True),
        
        # 危险代码 - 导入 os
        ("""
def bad():
    import os
    os.system('rm -rf /')
""", False),
        
        # 危险代码 - 使用 eval
        ("""
def bad2():
    eval('__import__("os").system("ls")')
""", False),
        
        # 警告代码 - 使用 requests
        ("""
def fetch(url: str):
    import requests
    return requests.get(url).text
""", True),  # 安全但会有警告
    ]
    
    print("=" * 60)
    print("沙箱检查器测试")
    print("=" * 60)
    
    for i, (code, expected_safe) in enumerate(test_cases, 1):
        print(f"\n测试 {i}:")
        print("-" * 40)
        result = check_code_safety(code)
        print(f"期望安全: {expected_safe}")
        print(f"实际安全: {result.is_safe}")
        if result.errors:
            print(f"错误: {result.errors}")
        if result.warnings:
            print(f"警告: {result.warnings}")
        if result.imports:
            print(f"导入: {result.imports}")
        print(f"结果: {'✓ 通过' if result.is_safe == expected_safe else '✗ 失败'}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
