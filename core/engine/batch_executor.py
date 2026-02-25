"""批量执行引擎

将所有节点汇总成一个完整的 Python 脚本，只调用一次 python.exe 执行。
解决每次启动 python.exe 导致的卡顿和黑窗问题。
"""

import subprocess
import json
import tempfile
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from ..graphics.simple_node_item import SimpleNodeItem


class BatchGraphExecutor:
    """批量图表执行器
    
    将图表中的所有节点汇总成一个完整的 Python 脚本，
    只调用一次 python.exe 执行，大幅提升执行效率。
    """
    
    def __init__(self, python_path: Optional[str] = None):
        """初始化执行器
        
        Args:
            python_path: Python 解释器路径，None 则自动查找
        """
        self.python_exe = python_path or self._find_python()
        self._check_environment()
    
    def _find_python(self) -> str:
        """查找 Python 解释器路径"""
        import sys
        
        # 检查是否是 PyInstaller 打包环境
        is_bundled = hasattr(sys, '_MEIPASS') or getattr(sys, 'frozen', False)
        
        # 1. 可执行文件同级目录（打包后的主要使用场景）
        if is_bundled:
            exe_dir = Path(sys.executable).parent
            embedded_path = exe_dir / "python_embedded" / "python.exe"
            if embedded_path.exists():
                return str(embedded_path.resolve())
        
        # 2. 环境变量
        env_path = os.environ.get("NODE_PYTHON_EMBEDDED")
        if env_path and Path(env_path).exists():
            return str(Path(env_path).resolve())
        
        # 3. 项目目录（仅打包环境使用，避免开发环境版本冲突）
        if is_bundled:
            project_dir = Path(__file__).parent.parent.parent
            embedded_path = project_dir / "python_embedded" / "python.exe"
            if embedded_path.exists():
                return str(embedded_path.resolve())
        
        # 4. 使用当前运行的 Python 解释器（开发环境）
        return sys.executable
    
    def _check_environment(self):
        """检查环境是否就绪"""
        if not Path(self.python_exe).exists():
            raise RuntimeError(f"Python 解释器不存在: {self.python_exe}")
    
    def execute_graph(
        self,
        nodes: List[SimpleNodeItem],
        timeout: int = 300
    ) -> Tuple[bool, Dict[str, Any], str]:
        """批量执行图表
        
        Args:
            nodes: 节点列表
            timeout: 执行超时时间（秒）
        
        Returns:
            (成功标志, 节点结果字典, 输出日志)
        """
        if not nodes:
            return True, {}, "没有节点可执行"
        
        # 拓扑排序
        sorted_nodes = self._topological_sort(nodes)
        
        # 构建完整执行脚本
        script = self._build_execution_script(sorted_nodes)
        
        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, encoding='utf-8'
        ) as f:
            f.write(script)
            script_path = f.name
        
        try:
            # 执行脚本（隐藏窗口）
            result = self._run_script_hidden(script_path, timeout)
            
            if result.returncode != 0:
                # 执行失败
                error_msg = self._parse_error(result.stdout, result.stderr)
                return False, {}, error_msg
            
            # 解析执行结果
            success, results, logs = self._parse_results(result.stdout)
            return success, results, logs
            
        except subprocess.TimeoutExpired:
            return False, {}, f"执行超时（{timeout}秒）"
        except Exception as e:
            return False, {}, f"执行失败: {str(e)}"
        finally:
            # 清理临时文件
            try:
                os.unlink(script_path)
            except:
                pass
    
    def _topological_sort(self, nodes: List[SimpleNodeItem]) -> List[SimpleNodeItem]:
        """拓扑排序"""
        in_degree = {node: 0 for node in nodes}
        for node in nodes:
            for port in node.input_ports:
                if port.connections:
                    in_degree[node] += 1
        
        queue = [node for node in nodes if in_degree[node] == 0]
        sorted_nodes = []
        
        while queue:
            node = queue.pop(0)
            sorted_nodes.append(node)
            for port in node.output_ports:
                for conn in port.connections:
                    if conn.end_port:
                        target_node = conn.end_port.parent_node
                        in_degree[target_node] -= 1
                        if in_degree[target_node] == 0:
                            queue.append(target_node)
        
        return sorted_nodes
    
    def _build_execution_script(
        self,
        sorted_nodes: List[SimpleNodeItem]
    ) -> str:
        """构建完整执行脚本
        
        生成的脚本包含：
        1. 所有节点函数定义
        2. 按拓扑顺序执行节点
        3. 处理节点间的数据传递
        4. 输出 JSON 格式的结果
        """
        # 收集所有节点代码和导入
        node_functions = []
        all_imports = set()
        node_calls = []
        
        for idx, node in enumerate(sorted_nodes):
            # 获取节点函数代码
            func_code, func_name = self._get_node_code(node)
            
            # 提取导入
            imports = self._extract_imports(func_code)
            all_imports.update(imports)
            
            # 构建节点函数（添加唯一后缀避免重名）
            unique_func_name = f"{func_name}_{idx}"
            node_functions.append({
                'original_name': func_name,
                'unique_name': unique_func_name,
                'code': func_code.replace(f"def {func_name}(", f"def {unique_func_name}("),
                'node': node,
                'node_name': node.name,
                'index': idx
            })

            # 构建调用代码
            call_code = self._build_node_call(node, idx, sorted_nodes, unique_func_name)
            node_calls.append({
                'index': idx,
                'call': call_code,
                'node_name': node.name
            })
        
        # 构建完整脚本
        script_parts = []
        
        # 1. 文件头
        script_parts.append("# -*- coding: utf-8 -*-")
        script_parts.append("# 批量执行脚本 - 由 NodePython 自动生成")
        script_parts.append("")
        
        # 2. 导入模块
        script_parts.append("import sys")
        script_parts.append("import json")
        script_parts.append("import traceback")
        script_parts.append("")
        
        # 添加节点所需的导入
        for imp in sorted(all_imports):
            script_parts.append(f"import {imp}")
        if all_imports:
            script_parts.append("")
        
        # 3. 节点函数定义
        script_parts.append("# ==================== 节点函数定义 ====================")
        script_parts.append("")
        
        for node_func in node_functions:
            script_parts.append(f"# 节点 {node_func['index']}: {node_func['node_name']}")
            script_parts.append(node_func['code'])
            script_parts.append("")
        
        # 4. 执行主函数
        script_parts.append("# ==================== 执行主函数 ====================")
        script_parts.append("")
        script_parts.append("def main():")
        script_parts.append('    """主执行函数"""')
        script_parts.append("    results = {}")
        script_parts.append("    logs = []")
        script_parts.append("")
        
        # 添加节点调用
        for call_info in node_calls:
            script_parts.append(f"    # 执行节点 {call_info['index']}: {call_info['node_name']}")
            script_parts.append(f"    try:")
            for line in call_info['call'].split('\n'):
                script_parts.append(f"        {line}")
            script_parts.append(f"    except Exception as e:")
            script_parts.append(f"        error_msg = f'节点 {call_info['node_name']} 执行出错: {{str(e)}}'")
            script_parts.append(f"        results['node_{call_info['index']}'] = {{'success': False, 'error': error_msg}}")
            script_parts.append(f"        logs.append(error_msg)")
            script_parts.append("")
        
        # 输出结果
        script_parts.append("    # 输出执行结果")
        script_parts.append("    output = {")
        script_parts.append("        'success': True,")
        script_parts.append("        'results': results,")
        script_parts.append("        'logs': logs")
        script_parts.append("    }")
        script_parts.append("    print('__BATCH_RESULT_START__')")
        script_parts.append("    print(json.dumps(output, ensure_ascii=False, default=str))")
        script_parts.append("    print('__BATCH_RESULT_END__')")
        script_parts.append("")
        
        script_parts.append("if __name__ == '__main__':")
        script_parts.append("    try:")
        script_parts.append("        main()")
        script_parts.append("    except Exception as e:")
        script_parts.append("        error_output = {")
        script_parts.append("            'success': False,")
        script_parts.append("            'error': str(e),")
        script_parts.append("            'traceback': traceback.format_exc()")
        script_parts.append("        }")
        script_parts.append("        print('__BATCH_ERROR_START__', file=sys.stderr)")
        script_parts.append("        print(json.dumps(error_output, ensure_ascii=False), file=sys.stderr)")
        script_parts.append("        print('__BATCH_ERROR_END__', file=sys.stderr)")
        script_parts.append("        sys.exit(1)")
        script_parts.append("")
        
        return '\n'.join(script_parts)
    
    def _get_node_code(self, node: SimpleNodeItem) -> Tuple[str, str]:
        """获取节点的函数代码和函数名"""
        # 内置节点源代码映射
        BUILTIN_NODE_SOURCE = {
            "打印节点": '''def node_print(data):
    """打印输出节点"""
    print(f"执行结果: {data}")
    return data''',
            "字符串": '''def const_string(value: str = "") -> str:
    """字符串常量节点"""
    return value''',
            "整数": '''def const_int(value: int = 0) -> int:
    """整数常量节点"""
    return value''',
            "浮点数": '''def const_float(value: float = 0.0) -> float:
    """浮点数常量节点"""
    return value''',
            "布尔": '''def const_bool(value: bool = True) -> bool:
    """布尔常量节点"""
    return value''',
            "列表": '''def const_list(value: list = None) -> list:
    """列表常量节点"""
    if value is None:
        return []
    return value''',
            "字典": '''def const_dict(value: dict = None) -> dict:
    """字典常量节点"""
    if value is None:
        return {}
    return value''',
            "数据提取": '''def extract_data(data: dict, path: str = "") -> any:
    """数据提取节点"""
    if not data or not path:
        return None

    if not isinstance(data, dict):
        try:
            import json
            data = json.loads(data) if isinstance(data, str) else data
        except Exception:
            return None

    # 解析路径（支持点号和方括号两种格式）
    import re
    # 将 "items[0].name" 或 "items.0.name" 统一处理
    tokens = re.findall(r'([^\\.\\[\\]]+)|\\[(\\d+)\\]', path)
    keys = []
    for token in tokens:
        if token[0]:  # 字段名
            keys.append(token[0])
        elif token[1]:  # 数组索引
            keys.append(int(token[1]))

    # 如果没有解析到任何key，尝试直接按点号分割
    if not keys:
        keys = path.split('.')

    # 遍历路径
    current = data
    try:
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                if isinstance(key, int) and 0 <= key < len(current):
                    current = current[key]
                else:
                    return None
            else:
                return None
            if current is None:
                return None
        return current
    except Exception:
        return None''',
            "数据类型检测": '''def type_test(data) -> None:
    """数据类型检测节点"""
    result = f"输入数据类型为：{type(data)}"
    print(result)
    return result''',
            "文件选择器": '''def file_picker(file_filter: str = "全部文件 (*)", selected_file_path: str = "") -> str:
    """文件选择器节点 - 返回已选择的文件路径"""
    return selected_file_path''',
            "文件夹选择器": '''def folder_picker(folder_path: str = "") -> str:
    """文件夹选择器节点 - 返回已选择的文件夹路径"""
    return folder_path'''
        }
        
        # 获取节点源代码
        if hasattr(node, 'is_custom_node') and node.is_custom_node:
            # 自定义节点
            if hasattr(node, 'source_code') and node.source_code:
                source = node.source_code
            else:
                raise RuntimeError(f"自定义节点 {node.name} 没有源代码")
        else:
            # 内置节点
            if node.name in BUILTIN_NODE_SOURCE:
                source = BUILTIN_NODE_SOURCE[node.name]
            elif hasattr(node, 'func') and hasattr(node.func, '_source'):
                source = node.func._source
            else:
                raise RuntimeError(f"节点 {node.name} 没有可用的源代码")
        
        # 提取函数名
        func_name = self._extract_func_name(source)
        return source, func_name
    
    def _extract_func_name(self, code: str) -> str:
        """从代码中提取函数名"""
        pattern = r'^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, code, re.MULTILINE)
        
        if not matches:
            raise ValueError("代码中未找到函数定义")
        
        return matches[0]
    
    def _extract_imports(self, code: str) -> List[str]:
        """从代码中提取导入的模块"""
        imports = []
        
        # 匹配 import xxx
        import_pattern = r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        imports.extend(re.findall(import_pattern, code, re.MULTILINE))
        
        # 匹配 from xxx import
        from_pattern = r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        imports.extend(re.findall(from_pattern, code, re.MULTILINE))
        
        return list(set(imports))
    
    def _build_node_call(
        self,
        node: SimpleNodeItem,
        node_index: int,
        all_nodes: List[SimpleNodeItem],
        func_name: str
    ) -> str:
        """构建节点调用代码"""
        # func_name 应该是 unique_func_name 格式（如 const_dict_0）

        # 收集参数
        kwargs = {}
        extra_vars = []  # 额外变量定义（用于特殊节点）

        for port in node.input_ports:
            param_name = port.port_name

            if port.connections:
                # 如果有连接，使用连接节点的结果
                conn = port.connections[0]
                source_node = conn.start_port.parent_node
                source_idx = all_nodes.index(source_node)
                kwargs[param_name] = f"results.get('node_{source_idx}', {{}}).get('result')"
            else:
                # 如果没有连接，使用预设的参数值
                if hasattr(node, 'param_values') and param_name in node.param_values:
                    value = node.param_values[param_name]
                    kwargs[param_name] = repr(value)
                else:
                    kwargs[param_name] = "None"

        # 特殊处理：文件选择器节点
        if node.name == "文件选择器":
            # 添加 selected_file_path 变量
            selected_path = node.param_values.get("selected_file_path", "")
            extra_vars.append(f"selected_file_path = {repr(selected_path)}")
            # 确保 file_filter 参数也被传递
            if "file_filter" not in kwargs:
                file_filter = node.param_values.get("file_filter", "全部文件 (*)")
                kwargs["file_filter"] = repr(file_filter)

        # 特殊处理：文件夹选择器节点
        if node.name == "文件夹选择器":
            # 添加 folder_path 变量
            folder_path = node.param_values.get("folder_path", "")
            extra_vars.append(f"folder_path = {repr(folder_path)}")

        # 构建参数字符串
        args_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])

        # 构建调用代码
        lines = []

        # 添加额外变量定义
        for var_def in extra_vars:
            lines.append(var_def)

        lines.append(f"result_{node_index} = {func_name}({args_str})")
        lines.append(f"results['node_{node_index}'] = {{")
        lines.append(f"    'success': True,")
        lines.append(f"    'result': result_{node_index},")
        lines.append(f"    'node_name': '{node.name}'")
        lines.append(f"}}")
        lines.append(f"logs.append(f'节点 {node.name} 执行完成: {{result_{node_index}}}')")

        return '\n'.join(lines)
    
    def _run_script_hidden(
        self,
        script_path: str,
        timeout: int
    ) -> subprocess.CompletedProcess:
        """运行脚本（隐藏窗口）"""
        import sys
        import os
        
        # 设置环境变量强制使用 UTF-8 编码，防止中文乱码
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # Windows 平台隐藏窗口
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
            
            return subprocess.run(
                [self.python_exe, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
                startupinfo=startupinfo,
                env=env
            )
        else:
            return subprocess.run(
                [self.python_exe, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace',
                env=env
            )
    
    def _parse_results(
        self,
        stdout: str
    ) -> Tuple[bool, Dict[str, Any], str]:
        """解析执行结果"""
        # 查找结果标记
        start_marker = "__BATCH_RESULT_START__"
        end_marker = "__BATCH_RESULT_END__"
        
        start_idx = stdout.find(start_marker)
        end_idx = stdout.find(end_marker)
        
        if start_idx == -1 or end_idx == -1:
            return False, {}, f"无法解析执行结果: 未找到结果标记"
        
        # 提取 JSON 内容
        json_str = stdout[start_idx + len(start_marker):end_idx].strip()
        
        try:
            data = json.loads(json_str)
            success = data.get('success', False)
            results = data.get('results', {})
            logs = '\n'.join(data.get('logs', []))
            return success, results, logs
        except json.JSONDecodeError as e:
            return False, {}, f"无法解析执行结果 JSON: {e}"
    
    def _parse_error(
        self,
        stdout: str,
        stderr: str
    ) -> str:
        """解析错误信息"""
        # 查找错误标记
        start_marker = "__BATCH_ERROR_START__"
        end_marker = "__BATCH_ERROR_END__"
        
        combined = stdout + "\n" + stderr
        start_idx = combined.find(start_marker)
        end_idx = combined.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            json_str = combined[start_idx + len(start_marker):end_idx].strip()
            try:
                data = json.loads(json_str)
                error = data.get('error', '未知错误')
                traceback_info = data.get('traceback', '')
                if traceback_info:
                    return f"{traceback_info}"
                return error
            except:
                pass
        
        # 返回原始输出
        return stderr.strip() or stdout.strip() or "执行失败（无错误信息）"


# 全局执行器实例（懒加载）
_batch_executor: Optional[BatchGraphExecutor] = None

def get_batch_executor() -> BatchGraphExecutor:
    """获取全局批量执行器实例"""
    global _batch_executor
    if _batch_executor is None:
        _batch_executor = BatchGraphExecutor()
    return _batch_executor

def reset_batch_executor():
    """重置执行器"""
    global _batch_executor
    _batch_executor = None
