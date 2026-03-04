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
from ..graphics.loop_node_item import LoopNodeItem


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
        """查找 Python 解释器路径
        
        查找顺序：
        1. 环境变量 NODE_PYTHON_EMBEDDED（最高优先级）
        2. 项目目录下的 python_embedded（开发环境和打包后通用）
        3. 可执行文件同级目录的 python_embedded（打包后主要使用）
        4. 当前运行的 Python 解释器（兜底方案）
        """
        import sys

        # 1. 环境变量（最高优先级）
        env_path = os.environ.get("NODE_PYTHON_EMBEDDED")
        if env_path and Path(env_path).exists():
            return str(Path(env_path).resolve())

        # 2. 项目目录下的 python_embedded（开发环境和打包后通用）
        project_dir = Path(__file__).parent.parent.parent
        embedded_path = project_dir / "python_embedded" / "python.exe"
        if embedded_path.exists():
            return str(embedded_path.resolve())

        # 3. 可执行文件同级目录（打包后的主要使用场景）
        if hasattr(sys, '_MEIPASS') or getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            embedded_path = exe_dir / "python_embedded" / "python.exe"
            if embedded_path.exists():
                return str(embedded_path.resolve())

        # 4. 使用当前运行的 Python 解释器（兜底方案）
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
        from ..graphics.loop_node_item import LoopNodeItem

        # 计算入度：只计算来自 nodes 列表内部的连接
        in_degree = {node: 0 for node in nodes}
        nodes_set = set(nodes)  # 用于快速查找
        
        for node in nodes:
            for port in node.input_ports:
                if port.connections:
                    for conn in port.connections:
                        if conn.start_port:
                            source_node = conn.start_port.parent_node
                            # 只计算来自 nodes 列表内部的连接
                            if source_node in nodes_set:
                                in_degree[node] += 1
                                break  # 一个端口只计一次

        queue = [node for node in nodes if in_degree[node] == 0]
        sorted_nodes = []

        while queue:
            node = queue.pop(0)
            sorted_nodes.append(node)
            for port in node.output_ports:
                for conn in port.connections:
                    if conn.end_port:
                        target_node = conn.end_port.parent_node
                        # 只处理在 nodes 列表中的目标节点
                        if target_node in nodes_set:
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
        script_parts.append("import os")
        script_parts.append("")
        
        # 添加项目根目录到 sys.path（以便导入 utils 等模块）
        # 使用环境变量或根据 python_exe 位置推断项目路径
        script_parts.append(f"# 添加项目根目录到路径")
        script_parts.append(f"python_exe_dir = os.path.dirname(os.path.abspath(sys.executable))")
        script_parts.append(f"possible_paths = [")
        script_parts.append(f"    os.environ.get('NODE_PYTHON_PROJECT_DIR', ''),")
        script_parts.append(f"    python_exe_dir,")
        script_parts.append(f"    os.path.dirname(python_exe_dir),")
        script_parts.append(f"    os.path.dirname(os.path.dirname(python_exe_dir)),")
        script_parts.append(f"]")
        script_parts.append(f"for path in possible_paths:")
        script_parts.append(f"    if path and os.path.isdir(path) and os.path.isdir(os.path.join(path, 'utils')):")
        script_parts.append(f"        sys.path.insert(0, path)")
        script_parts.append(f"        break")
        script_parts.append(f"else:")
        script_parts.append(f"    # 如果上述路径都找不到，尝试使用 __file__ 所在目录的父目录")
        script_parts.append(f"    script_dir = os.path.dirname(os.path.abspath(__file__))")
        script_parts.append(f"    # 尝试 script_dir 的各级父目录")
        script_parts.append(f"    for parent in [script_dir] + [os.path.dirname(script_dir)] + [os.path.dirname(os.path.dirname(script_dir))]:")
        script_parts.append(f"        if os.path.isdir(os.path.join(parent, 'utils')):")
        script_parts.append(f"            sys.path.insert(0, parent)")
        script_parts.append(f"            break")
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
            "字符串": '''def const_string(value= "") -> str:
    """
    字符串常量节点。
    将任意输入转换为字符串值。

    转换规则:
    - None → 空字符串
    - 其他类型 → 使用 str() 转换
    """
    if value is None:
        return ""
    return str(value)''',
            "整数": '''def const_int(value= 0) -> int:
    """
    整数常量节点。
    将任意输入转换为整数值。

    转换规则:
    - 数字类型 (int/float) → 截断取整
    - 布尔类型 → True=1, False=0
    - 字符串 → 尝试解析为数字，失败返回 0
    - 其他类型 → 返回 0
    """
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            try:
                return int(float(value.strip()))
            except ValueError:
                return 0
    return 0''',
            "浮点数": '''def const_float(value= 0.0) -> float:
    """
    浮点数常量节点。
    将任意输入转换为浮点数值。

    转换规则:
    - 数字类型 (int/float) → 直接转换
    - 布尔类型 → True=1.0, False=0.0
    - 字符串 → 尝试解析为 float，失败返回 0.0
    - 其他类型 → 返回 0.0
    """
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return 0.0
    return 0.0''',
            "布尔": '''def const_bool(value= True) -> bool:
    """
    布尔常量节点。
    将任意输入转换为布尔值。

    转换规则:
    - 字符串 "false", "0", "no", "off" (不区分大小写) → False
    - 空值 (None, "", [], {}) → False
    - 数字 0, 0.0 → False
    - 其他情况 → True
    """
    if isinstance(value, str):
        lower_val = value.strip().lower()
        if lower_val in ('false', '0', 'no', 'off', 'none'):
            return False
        if lower_val in ('true', '1', 'yes', 'on'):
            return True
    return bool(value)''',
            "列表": '''def const_list(value= None) -> list:
    """
    列表常量节点。
    将任意输入转换为列表值。

    转换规则:
    - None → 空列表
    - list/tuple/set → 直接转换
    - dict → 转为键值对列表
    - 字符串 → 尝试 JSON 解析，失败则逗号分割，再失败则单元素列表
    - 其他标量类型 → 包装为单元素列表
    """
    import json
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, dict):
        return list(value.items())
    if isinstance(value, str):
        # 尝试 JSON 解析
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        # 尝试逗号分割
        if ',' in value:
            return [item.strip() for item in value.split(',')]
        # 单元素列表
        return [value]
    # 其他类型包装为列表
    return [value]''',
            "字典": '''def const_dict(value= None) -> dict:
    """
    字典常量节点。
    将任意输入转换为字典值。

    转换规则:
    - None → 空字典
    - dict → 原样返回
    - 字符串 → 尝试 JSON 解析，失败则尝试键值对格式，再失败返回空字典
    - 列表 → 如果是键值对列表则转换，否则转为索引字典
    - 其他类型 → 返回空字典
    """
    import json
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        # 尝试 JSON 解析
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        # 尝试键值对格式 (a=1,b=2)
        try:
            result = {}
            for pair in value.split(','):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    result[k.strip()] = v.strip()
            if result:
                return result
        except Exception:
            pass
        return {}
    if isinstance(value, list):
        # 检查是否为键值对列表
        if all(isinstance(item, (tuple, list)) and len(item) == 2 for item in value):
            return dict(value)
        # 否则转为索引字典
        return {i: v for i, v in enumerate(value)}
    return {}''',
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
                # 如果有连接，检查源节点类型
                conn = port.connections[0]
                source_node = conn.start_port.parent_node
                source_port_name = conn.start_port.port_name

                # 检查源节点是否是循环节点的"迭代值"端口
                if isinstance(source_node, LoopNodeItem) and source_port_name == '迭代值':
                    # 使用迭代值（从 param_values 中获取，由 loop_executor 提前设置）
                    if hasattr(node, 'param_values') and param_name in node.param_values:
                        value = node.param_values[param_name]
                        kwargs[param_name] = repr(value)
                    else:
                        kwargs[param_name] = "None"
                elif source_node in all_nodes:
                    # 普通节点连接，使用连接节点的结果
                    source_idx = all_nodes.index(source_node)
                    kwargs[param_name] = f"results.get('node_{source_idx}', {{}}).get('result')"
                else:
                    # 源节点不在 all_nodes 列表中，检查是否是常量节点
                    # 如果是常量节点，直接使用其 param_values 中的值
                    source_param_value = getattr(source_node, 'param_values', {}).get('value')
                    if source_param_value is not None:
                        kwargs[param_name] = repr(source_param_value)
                    else:
                        kwargs[param_name] = "None"
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
