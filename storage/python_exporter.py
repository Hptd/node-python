#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Python 文件导出器

将节点图表导出为可独立运行的 Python 脚本。
生成的脚本包含：
1. 统一的导入语句（头部）
2. 节点函数定义（中间）
3. 主执行函数（底部）

支持节点类型：
- SimpleNodeItem: 普通节点
- LoopNodeItem: 循环节点（区间循环/List 循环）
- MultithreadNodeItem: 多线程处理节点
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
from datetime import datetime

from core.graphics.simple_node_item import SimpleNodeItem
from core.graphics.loop_node_item import LoopNodeItem, RangeLoopNodeItem, ListLoopNodeItem
from core.graphics.multithread_node_item import MultithreadNodeItem
from core.engine.graph_executor import topological_sort


class PythonExporter:
    """Python 文件导出器"""

    # 内置节点源代码映射
    BUILTIN_NODE_SOURCE = {
        "打印节点": '''def node_print(data):
    """打印输出节点"""
    print(f"执行结果：{data}")
    return data''',

        "字符串": '''def const_string(value= "") -> str:
    """
    字符串常量节点。
    将任意输入转换为字符串值。
    """
    if value is None:
        return ""
    return str(value)''',

        "整数": '''def const_int(value= 0) -> int:
    """
    整数常量节点。
    将任意输入转换为整数值。
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
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        if ',' in value:
            return [item.strip() for item in value.split(',')]
        return [value]
    return [value]''',

        "字典": '''def const_dict(value= None) -> dict:
    """
    字典常量节点。
    将任意输入转换为字典值。
    """
    import json
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
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
        if all(isinstance(item, (tuple, list)) and len(item) == 2 for item in value):
            return dict(value)
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
    import re
    tokens = re.findall(r'([^.\\[\\]]+)|\\[(\\d+)\\]', path)
    keys = []
    for token in tokens:
        if token[0]:
            keys.append(token[0])
        elif token[1]:
            keys.append(int(token[1]))
    if not keys:
        keys = path.split('.')
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
    """文件选择器节点"""
    return selected_file_path''',

        "文件夹选择器": '''def folder_picker(folder_path: str = "") -> str:
    """文件夹选择器节点"""
    return folder_path''',
    }

    def __init__(self, nodes: List[Any]):
        """初始化导出器

        Args:
            nodes: 所有节点列表（包含 SimpleNodeItem、LoopNodeItem、MultithreadNodeItem）
        """
        self.all_nodes = nodes
        self.all_imports: Set[str] = set()
        self.node_functions: List[Dict] = []
        self.node_id_to_idx: Dict[int, int] = {}
        
        # 为每个节点分配索引
        for idx, node in enumerate(nodes):
            self.node_id_to_idx[id(node)] = idx

    def export(self, filepath: str) -> Tuple[bool, str]:
        """导出为 Python 文件"""
        try:
            if not self.all_nodes:
                return False, "没有可执行的节点"

            self._collect_node_functions()
            script = self._build_script()

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(script)

            return True, f"已导出 {len(self.all_nodes)} 个节点"

        except Exception as e:
            import traceback
            return False, f"导出失败：{e}\n{traceback.format_exc()}"

    def _collect_node_functions(self):
        """收集所有节点函数和导入语句"""
        for idx, node in enumerate(self.all_nodes):
            # 跳过循环节点和多线程节点（它们不需要函数定义）
            if isinstance(node, (LoopNodeItem, MultithreadNodeItem)):
                continue
                
            source_code, func_name = self._get_node_code(node)
            imports = self._extract_imports(source_code)
            self.all_imports.update(imports)

            unique_func_name = f"{func_name}_{idx}"
            self.node_functions.append({
                'original_name': func_name,
                'unique_name': unique_func_name,
                'code': source_code.replace(f"def {func_name}(", f"def {unique_func_name}("),
                'node': node,
                'node_name': node.name,
                'index': idx
            })

    def _get_node_code(self, node: SimpleNodeItem) -> Tuple[str, str]:
        """获取节点的函数代码和函数名"""
        if hasattr(node, 'is_custom_node') and node.is_custom_node:
            if hasattr(node, 'source_code') and node.source_code:
                source = node.source_code
            else:
                raise RuntimeError(f"自定义节点 {node.name} 没有源代码")
        else:
            if node.name in self.BUILTIN_NODE_SOURCE:
                source = self.BUILTIN_NODE_SOURCE[node.name]
            elif hasattr(node, 'func') and hasattr(node.func, '_source'):
                source = node.func._source
            else:
                raise RuntimeError(f"节点 {node.name} 没有可用的源代码")

        func_name = self._extract_func_name(source)
        return source, func_name

    def _extract_func_name(self, code: str) -> str:
        pattern = r'^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, code, re.MULTILINE)
        if not matches:
            raise ValueError("代码中未找到函数定义")
        return matches[0]

    def _extract_imports(self, code: str) -> List[str]:
        imports = []
        import_pattern = r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        imports.extend(re.findall(import_pattern, code, re.MULTILINE))
        from_pattern = r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        imports.extend(re.findall(from_pattern, code, re.MULTILINE))
        return list(set(imports))

    def _build_script(self) -> str:
        parts = [
            self._build_header(),
            self._build_imports(),
            self._build_node_functions(),
            self._build_main_function()
        ]
        return '\n\n'.join(parts)

    def _build_header(self) -> str:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NodePython 导出的工作流

此文件由 中文节点 Python 编辑器 自动生成。

运行方式:
    python 此文件.py

生成时间：{timestamp}
"""'''

    def _build_imports(self) -> str:
        lines = ["import sys", "import json", "import os"]
        lines.append("")
        lines.append("# 添加项目根目录到路径")
        lines.append("script_dir = os.path.dirname(os.path.abspath(__file__))")
        lines.append("for parent in [script_dir] + [os.path.dirname(script_dir) for _ in range(3)]:")
        lines.append("    if os.path.isdir(parent) and os.path.isdir(os.path.join(parent, 'utils')):")
        lines.append("        sys.path.insert(0, parent)")
        lines.append("        break")
        lines.append("")

        extra_imports = sorted(self.all_imports - {'sys', 'json', 'os'})
        for imp in extra_imports:
            lines.append(f"import {imp}")
        if extra_imports:
            lines.append("")

        return '\n'.join(lines)

    def _build_node_functions(self) -> str:
        parts = ["# ==================== 节点函数定义 ===================="]
        for node_func in self.node_functions:
            parts.append(f"# 节点 {node_func['index']}: {node_func['node_name']}")
            parts.append(node_func['code'])
            parts.append("")
        if len(self.node_functions) == 0:
            parts.append("# 无普通节点，仅包含循环节点/多线程节点")
        return '\n'.join(parts)

    def _get_input_value_code(self, node: Any, port_name: str, inside_loop: bool = False) -> str:
        """获取节点输入参数的值（生成 Python 代码）
        
        Args:
            node: 节点实例
            port_name: 输入端口名称
            inside_loop: 是否在循环内部（如果在循环内且连接到迭代值，使用 iterator_value）
        """
        port = None
        for p in node.input_ports:
            if p.port_name == port_name:
                port = p
                break

        if port is None:
            return "None"

        if port.connections:
            conn = port.connections[0]
            source_node = conn.start_port.parent_node
            source_port_name = conn.start_port.port_name
            source_idx = self.node_id_to_idx.get(id(source_node))

            if source_idx is not None:
                if isinstance(source_node, LoopNodeItem):
                    if source_port_name == '迭代值':
                        # 在循环内部时，直接使用 iterator_value
                        if inside_loop:
                            return "iterator_value"
                        else:
                            # 循环外引用迭代值，这是无效的，返回 None
                            return "None"
                    elif source_port_name == '汇总结果':
                        return f"loop_result_{source_idx}"
                elif isinstance(source_node, MultithreadNodeItem):
                    if source_port_name == '迭代值':
                        return "thread_iterator_value"
                    elif source_port_name == '汇总结果':
                        return f"thread_result_{source_idx}"
                else:
                    return f"results.get('node_{source_idx}', {{}}).get('result')"
            return "None"
        else:
            if hasattr(node, 'param_values') and port_name in node.param_values:
                return repr(node.param_values[port_name])
            return "None"

    def _build_main_function(self) -> str:
        lines = [
            "# ==================== 主执行函数 ====================",
            "",
            "def main():",
            '    """主执行函数"""',
            "    results = {}",
            "    logs = []",
            "",
        ]

        # 使用拓扑排序确定节点执行顺序
        from core.engine.graph_executor import topological_sort
        try:
            sorted_nodes = topological_sort(self.all_nodes)
        except Exception:
            # 拓扑排序失败时，使用原始顺序
            sorted_nodes = self.all_nodes

        processed_nodes = set()

        for node in sorted_nodes:
            node_idx = self.node_id_to_idx[id(node)]

            if isinstance(node, RangeLoopNodeItem):
                lines.extend(self._build_range_loop_code(node, node_idx, processed_nodes))
                processed_nodes.add(id(node))
            elif isinstance(node, ListLoopNodeItem):
                lines.extend(self._build_list_loop_code(node, node_idx, processed_nodes))
                processed_nodes.add(id(node))
            elif isinstance(node, MultithreadNodeItem):
                lines.extend(self._build_multithread_code(node, node_idx, processed_nodes))
                processed_nodes.add(id(node))
            elif isinstance(node, SimpleNodeItem):
                if id(node) not in processed_nodes:
                    lines.extend(self._build_simple_node_code(node, node_idx))
                    processed_nodes.add(id(node))

        lines.append("")
        lines.append("    # 输出执行结果")
        lines.append("    print('=' * 50)")
        lines.append("    print('执行完成')")
        lines.append("    print('=' * 50)")
        lines.append("    for log in logs:")
        lines.append("        print(log)")
        lines.append("")
        lines.append("if __name__ == '__main__':")
        lines.append("    main()")

        return '\n'.join(lines)

    def _build_simple_node_code(self, node: SimpleNodeItem, idx: int) -> List[str]:
        lines = []
        unique_func_name = None
        
        for nf in self.node_functions:
            if nf['index'] == idx:
                unique_func_name = nf['unique_name']
                break
        
        if unique_func_name is None:
            return lines
        
        lines.append(f"    # 执行节点 {idx}: {node.name}")
        lines.append("    try:")

        kwargs = {}
        for port in node.input_ports:
            kwargs[port.port_name] = self._get_input_value_code(node, port.port_name)

        args_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
        lines.append(f"        result_{idx} = {unique_func_name}({args_str})")
        lines.append(f"        results['node_{idx}'] = {{")
        lines.append(f"            'success': True,")
        lines.append(f"            'result': result_{idx},")
        lines.append(f"            'node_name': '{node.name}'")
        lines.append(f"        }}")
        lines.append(f"        logs.append(f'节点 {node.name} 执行完成：{{result_{idx}}}')")
        lines.append("    except Exception as e:")
        lines.append(f"        error_msg = f'节点 {node.name} 执行出错：{{e}}'")
        lines.append(f"        results['node_{idx}'] = {{'success': False, 'error': error_msg}}")
        lines.append(f"        logs.append(error_msg)")
        lines.append("")
        
        return lines

    def _get_loop_input_code(self, node: LoopNodeItem, port_name: str) -> str:
        """获取循环节点输入端口的值"""
        for port in node.input_ports:
            if port.port_name == port_name:
                if port.connections:
                    conn = port.connections[0]
                    source_node = conn.start_port.parent_node
                    source_idx = self.node_id_to_idx.get(id(source_node))
                    if source_idx is not None:
                        return f"results.get('node_{source_idx}', {{}}).get('result')"
                # 无连接时使用默认值
                if isinstance(node, RangeLoopNodeItem):
                    if port_name == '最小值':
                        return repr(node.range_start)
                    elif port_name == '最大值':
                        return repr(node.range_end)
                    elif port_name == '步长':
                        return repr(node.range_step)
                elif isinstance(node, ListLoopNodeItem):
                    if port_name == '列表数据':
                        try:
                            parsed = json.loads(node.list_data) if node.list_data else []
                            return repr(parsed)
                        except:
                            return "[]"
                return "None"
        return "None"

    def _build_range_loop_code(self, node: RangeLoopNodeItem, idx: int, processed_nodes: set) -> List[str]:
        lines = []

        # 获取循环参数（支持从其他节点输入）
        range_start_code = self._get_loop_input_code(node, '最小值')
        range_end_code = self._get_loop_input_code(node, '最大值')
        range_step_code = self._get_loop_input_code(node, '步长')

        lines.append(f"    # 执行节点 {idx}: 区间循环 (Range Loop)")
        lines.append("    try:")
        lines.append(f"        loop_result_{idx} = []")
        lines.append(f"        iterator_values = list(range({range_start_code}, {range_end_code}, {range_step_code}))")
        lines.append(f"        logs.append(f'区间循环开始：共{{len(iterator_values)}}次迭代')")
        lines.append("")
        lines.append(f"        for iterator_value in iterator_values:")

        loop_nodes = self._find_nodes_connected_to_loop(node, '迭代值')
        has_loop_nodes = False
        generated_code = False

        for loop_node in loop_nodes:
            if id(loop_node) in processed_nodes:
                continue
            processed_nodes.add(id(loop_node))
            loop_idx = self.node_id_to_idx.get(id(loop_node))
            if loop_idx is not None:
                if not has_loop_nodes:
                    has_loop_nodes = True
                iteration_code = self._build_loop_iteration_code(loop_node, loop_idx, indent=12)
                if iteration_code:
                    generated_code = True
                lines.extend(iteration_code)

        # 如果循环内没有节点或没有生成有效代码，添加 pass
        if not has_loop_nodes or not generated_code:
            lines.append("            pass  # 循环内无节点")
        else:
            # 循环内节点执行完成后，收集最后一次迭代的结果
            # 找到拓扑排序后的最后一个节点
            if loop_nodes:
                last_node_idx = self.node_id_to_idx.get(id(loop_nodes[-1]))
                if last_node_idx is not None:
                    lines.append(f"            # 收集本次迭代结果")
                    lines.append(f"            if results.get('node_{last_node_idx}', {{}}).get('success'):")
                    lines.append(f"                loop_result_{idx}.append(results['node_{last_node_idx}']['result'])")
                    lines.append(f"            else:")
                    lines.append(f"                loop_result_{idx}.append(None)")

        lines.append("")
        lines.append(f"        logs.append(f'区间循环完成，执行了{{len(iterator_values)}}次迭代')")
        lines.append("    except Exception as e:")
        lines.append(f"        error_msg = f'区间循环执行出错：{{e}}'")
        lines.append(f"        logs.append(error_msg)")
        lines.append(f"        results['node_{idx}'] = {{'success': False, 'error': error_msg}}")
        lines.append("")

        return lines

    def _build_list_loop_code(self, node: ListLoopNodeItem, idx: int, processed_nodes: set) -> List[str]:
        lines = []

        list_data_code = self._get_loop_input_code(node, '列表数据')

        lines.append(f"    # 执行节点 {idx}: List 循环")
        lines.append("    try:")
        lines.append(f"        loop_result_{idx} = []")
        lines.append(f"        iterator_values = {list_data_code}")
        lines.append(f"        logs.append(f'List 循环开始：共{{len(iterator_values)}}次迭代')")
        lines.append("")
        lines.append(f"        for iterator_value in iterator_values:")

        loop_nodes = self._find_nodes_connected_to_loop(node, '迭代值')
        has_loop_nodes = False
        generated_code = False

        for loop_node in loop_nodes:
            if id(loop_node) in processed_nodes:
                continue
            processed_nodes.add(id(loop_node))
            loop_idx = self.node_id_to_idx.get(id(loop_node))
            if loop_idx is not None:
                if not has_loop_nodes:
                    has_loop_nodes = True
                iteration_code = self._build_loop_iteration_code(loop_node, loop_idx, indent=12)
                if iteration_code:
                    generated_code = True
                lines.extend(iteration_code)

        # 如果循环内没有节点或没有生成有效代码，添加 pass
        if not has_loop_nodes or not generated_code:
            lines.append("            pass  # 循环内无节点")
        else:
            # 循环内节点执行完成后，收集最后一次迭代的结果
            # 找到拓扑排序后的最后一个节点
            if loop_nodes:
                last_node_idx = self.node_id_to_idx.get(id(loop_nodes[-1]))
                if last_node_idx is not None:
                    lines.append(f"            # 收集本次迭代结果")
                    lines.append(f"            if results.get('node_{last_node_idx}', {{}}).get('success'):")
                    lines.append(f"                loop_result_{idx}.append(results['node_{last_node_idx}']['result'])")
                    lines.append(f"            else:")
                    lines.append(f"                loop_result_{idx}.append(None)")

        lines.append("")
        lines.append(f"        logs.append(f'List 循环完成，执行了{{len(iterator_values)}}次迭代')")
        lines.append("    except Exception as e:")
        lines.append(f"        error_msg = f'List 循环执行出错：{{e}}'")
        lines.append(f"        logs.append(error_msg)")
        lines.append(f"        results['node_{idx}'] = {{'success': False, 'error': error_msg}}")
        lines.append("")

        return lines

    def _build_loop_iteration_code(self, node: SimpleNodeItem, idx: int, indent: int = 4) -> List[str]:
        lines = []
        indent_str = " " * indent

        unique_func_name = None
        for nf in self.node_functions:
            if nf['index'] == idx:
                unique_func_name = nf['unique_name']
                break

        if unique_func_name is None:
            return lines

        lines.append(f"{indent_str}# 执行节点 {idx}: {node.name}")
        lines.append(f"{indent_str}try:")

        kwargs = {}
        for port in node.input_ports:
            # 传递 inside_loop=True，让方法知道这是在循环内部
            kwargs[port.port_name] = self._get_input_value_code(node, port.port_name, inside_loop=True)

        args_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
        lines.append(f"{indent_str}    result_{idx} = {unique_func_name}({args_str})")
        lines.append(f"{indent_str}    results['node_{idx}'] = {{")
        lines.append(f"{indent_str}        'success': True,")
        lines.append(f"{indent_str}        'result': result_{idx},")
        lines.append(f"{indent_str}        'node_name': '{node.name}'")
        lines.append(f"{indent_str}    }}")
        lines.append(f"{indent_str}    logs.append(f'节点 {node.name} 执行完成：{{result_{idx}}}')")
        lines.append(f"{indent_str}except Exception as e:")
        lines.append(f"{indent_str}    error_msg = f'节点 {node.name} 执行出错：{{e}}'")
        lines.append(f"{indent_str}    results['node_{idx}'] = {{'success': False, 'error': error_msg}}")
        lines.append(f"{indent_str}    logs.append(error_msg)")
        lines.append("")

        return lines

    def _build_simple_node_code(self, node: SimpleNodeItem, idx: int, indent: int = 4) -> List[str]:
        """生成普通节点代码（可指定缩进）"""
        lines = []
        indent_str = " " * indent

        unique_func_name = None
        for nf in self.node_functions:
            if nf['index'] == idx:
                unique_func_name = nf['unique_name']
                break

        if unique_func_name is None:
            return lines

        lines.append(f"{indent_str}# 执行节点 {idx}: {node.name}")
        lines.append(f"{indent_str}try:")

        kwargs = {}
        for port in node.input_ports:
            kwargs[port.port_name] = self._get_input_value_code(node, port.port_name)

        args_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
        lines.append(f"{indent_str}    result_{idx} = {unique_func_name}({args_str})")
        lines.append(f"{indent_str}    results['node_{idx}'] = {{")
        lines.append(f"{indent_str}        'success': True,")
        lines.append(f"{indent_str}        'result': result_{idx},")
        lines.append(f"{indent_str}        'node_name': '{node.name}'")
        lines.append(f"{indent_str}    }}")
        lines.append(f"{indent_str}    logs.append(f'节点 {node.name} 执行完成：{{result_{idx}}}')")
        lines.append(f"{indent_str}except Exception as e:")
        lines.append(f"{indent_str}    error_msg = f'节点 {node.name} 执行出错：{{e}}'")
        lines.append(f"{indent_str}    results['node_{idx}'] = {{'success': False, 'error': error_msg}}")
        lines.append(f"{indent_str}    logs.append(error_msg)")
        lines.append("")

        return lines

    def _build_multithread_code(self, node: MultithreadNodeItem, idx: int, processed_nodes: set) -> List[str]:
        lines = []

        # 获取输入列表
        input_list_code = "[]"
        for port in node.input_ports:
            if port.port_name == '输入列表':
                if port.connections:
                    conn = port.connections[0]
                    source_node = conn.start_port.parent_node
                    source_idx = self.node_id_to_idx.get(id(source_node))
                    if source_idx is not None:
                        input_list_code = f"results.get('node_{source_idx}', {{}}).get('result')"
                else:
                    try:
                        parsed = json.loads(node.input_list) if node.input_list else []
                        input_list_code = repr(parsed)
                    except:
                        input_list_code = "[]"
                break

        thread_count = node.thread_count

        lines.append(f"    # 执行节点 {idx}: 多线程处理")
        lines.append("    try:")
        lines.append("        from concurrent.futures import ThreadPoolExecutor, as_completed")
        lines.append(f"        thread_result_{idx} = []")
        lines.append(f"        input_list = {input_list_code}")
        lines.append(f"        thread_count = {thread_count}")
        lines.append(f"        logs.append(f'多线程处理开始：{{len(input_list)}}个项目，{{thread_count}}个线程')")
        lines.append("")

        # 查找连接到"迭代值"端口的节点
        thread_nodes = self._find_nodes_connected_to_loop(node, '迭代值')
        process_func_lines = []

        for thread_node in thread_nodes:
            if id(thread_node) in processed_nodes:
                continue
            processed_nodes.add(id(thread_node))
            thread_idx = self.node_id_to_idx.get(id(thread_node))
            if thread_idx is not None:
                process_func_lines.extend(self._build_thread_process_code(thread_node, thread_idx))

        lines.append("        def process_item(item):")
        lines.append("            iterator_value = item")
        lines.append("            local_results = {}")
        lines.append("            try:")

        # 添加处理代码
        if process_func_lines:
            for line in process_func_lines:
                lines.append("            " + line)
        else:
            lines.append("                pass  # 无处理节点")

        lines.append("            return local_results.get('result', iterator_value)")
        lines.append("            except Exception as e:")
        lines.append("                return f'Error: {e}'")
        lines.append("")

        lines.append("        with ThreadPoolExecutor(max_workers=thread_count) as executor:")
        lines.append("            futures = [executor.submit(process_item, item) for item in input_list]")
        lines.append(f"            thread_result_{idx} = [f.result() for f in as_completed(futures)]")
        lines.append("")
        lines.append(f"        logs.append(f'多线程处理完成：处理了{{len(thread_result_{idx})}}个项目')")
        lines.append("    except Exception as e:")
        lines.append(f"        error_msg = f'多线程处理执行出错：{{e}}'")
        lines.append(f"        logs.append(error_msg)")
        lines.append(f"        results['node_{idx}'] = {{'success': False, 'error': error_msg}}")
        lines.append("")

        return lines

    def _build_thread_process_code(self, node: SimpleNodeItem, idx: int) -> List[str]:
        """生成多线程处理内节点的代码"""
        lines = []
        
        unique_func_name = None
        for nf in self.node_functions:
            if nf['index'] == idx:
                unique_func_name = nf['unique_name']
                break
        
        if unique_func_name is None:
            return lines
        
        kwargs = {}
        for port in node.input_ports:
            kwargs[port.port_name] = self._get_input_value_code(node, port.port_name)

        args_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
        lines.append(f"result_{idx} = {unique_func_name}({args_str})")
        lines.append(f"local_results['node_{idx}'] = {{'success': True, 'result': result_{idx}}}")
        
        return lines

    def _find_nodes_connected_to_loop(self, loop_node: Any, port_name: str) -> List[SimpleNodeItem]:
        """查找直接连接到循环节点指定端口的节点

        只返回直接连接到循环节点"迭代值"或"汇总结果"端口的节点。
        下游节点不在循环内执行，而是在循环外使用循环的汇总结果。
        """
        direct_nodes = []
        for node in self.all_nodes:
            if not isinstance(node, SimpleNodeItem):
                continue
            for port in node.input_ports:
                for conn in port.connections:
                    if conn.start_port and conn.start_port.parent_node == loop_node:
                        if conn.start_port.port_name == port_name:
                            direct_nodes.append(node)
                            break
        return direct_nodes


def export_graph_to_python(nodes: List[Any], filepath: str) -> Tuple[bool, str]:
    """导出图表为 Python 文件的便捷函数"""
    exporter = PythonExporter(nodes)
    return exporter.export(filepath)
