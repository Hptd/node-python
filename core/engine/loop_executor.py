"""循环执行引擎

负责执行循环节点内的节点，处理迭代和结果汇总

支持两种使用方式：
1. 容器模式：将节点拖入循环内部，节点在每次迭代中执行
2. 连接模式：节点连接到循环节点的输出端口
   - 连接到"迭代值"端口的节点：在每次迭代中执行
   - 连接到"汇总结果"端口的节点：在循环完成后执行一次

优化：使用批量执行模式，将所有迭代合并成一个脚本，只启动一次 Python 子进程。
"""

import json
import inspect
import tempfile
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from ..graphics.loop_node_item import LoopNodeItem, RangeLoopNodeItem, ListLoopNodeItem
from ..graphics.simple_node_item import SimpleNodeItem
from .graph_executor import topological_sort
from .embedded_executor import get_executor as get_embedded_executor


def _execute_node(node: SimpleNodeItem, all_nodes: List[SimpleNodeItem],
                  iterator_value: Any = None, iterator_port_name: str = '迭代值') -> Any:
    """执行单个节点，准备输入参数

    自定义节点使用嵌入式 Python 执行，内置节点直接调用。

    Args:
        node: 要执行的节点
        all_nodes: 所有可能提供输入的节点列表
        iterator_value: 当前迭代值（可选）
        iterator_port_name: 迭代值端口名称

    Returns:
        节点执行结果
    """
    kwargs = {}

    for port in node.input_ports:
        input_value = None
        has_connection = False

        for conn in port.connections:
            if conn.start_port:
                source_node = conn.start_port.parent_node

                # 获取源端口的端口名称（输出端口）
                source_port_name = conn.start_port.port_name

                # 检查源节点是否是循环节点
                if isinstance(source_node, LoopNodeItem):
                    # 检查是否连接到迭代值端口
                    if source_port_name == '迭代值':
                        # 使用当前迭代值
                        input_value = iterator_value
                        has_connection = True
                        break
                    elif source_port_name == '汇总结果':
                        # 从循环节点获取汇总结果
                        input_value = source_node.get_aggregated_result()
                        has_connection = True
                        break
                elif isinstance(source_node, SimpleNodeItem) and source_node in all_nodes:
                    # 来自普通节点
                    if source_node.result is not None:
                        input_value = source_node.result
                        has_connection = True
                        break

        if has_connection:
            kwargs[port.port_name] = input_value
        elif port.port_name in node.param_values:
            kwargs[port.port_name] = node.param_values[port.port_name]

    # 自定义节点使用嵌入式 Python 执行
    if hasattr(node, 'is_custom_node') and node.is_custom_node:
        try:
            executor = get_embedded_executor()
            source_code = getattr(node.func, '_custom_source', None)
            if not source_code:
                source_code = inspect.getsource(node.func)
            
            # 提取导入
            imports = _extract_imports(source_code)
            
            result = executor.execute_node(source_code, kwargs, imports, timeout=30)
            node.result = result
            node.set_status(SimpleNodeItem.STATUS_SUCCESS)
            return result
        except Exception as e:
            node.set_status(SimpleNodeItem.STATUS_ERROR, str(e))
            raise
    else:
        # 内置节点直接调用
        result = node.func(**kwargs)
        node.result = result
        node.set_status(SimpleNodeItem.STATUS_SUCCESS)
        return result


def _extract_imports(code: str) -> List[str]:
    """从代码中提取导入的模块"""
    imports = []
    
    # 匹配 import xxx
    import_pattern = r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    imports.extend(re.findall(import_pattern, code, re.MULTILINE))
    
    # 匹配 from xxx import
    from_pattern = r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    imports.extend(re.findall(from_pattern, code, re.MULTILINE))
    
    return list(set(imports))


def _execute_loop_batch(
    loop_node: LoopNodeItem,
    iteration_nodes: List[SimpleNodeItem],
    inner_nodes: List,
    iterator_values: List[Any],
    all_nodes: List[SimpleNodeItem]
) -> List[Any]:
    """批量执行循环 - 将所有迭代合并成一个脚本，只启动一次 Python 子进程

    Args:
        loop_node: 循环节点
        iteration_nodes: 连接到迭代值的节点列表
        inner_nodes: 循环内部的节点（容器模式）
        iterator_values: 所有迭代值列表
        all_nodes: 所有节点列表

    Returns:
        结果列表
    """
    from utils.console_stream import colored_print
    
    # 合并容器模式和连接模式的节点
    nodes_to_execute = list(set(inner_nodes + iteration_nodes))
    
    if not nodes_to_execute:
        # 没有节点时，直接返回迭代值
        colored_print(f"    循环内没有节点，直接返回迭代值", "debug")
        return list(iterator_values)
    
    # 收集所有节点代码和导入
    all_imports = set()
    node_functions = []
    
    for idx, node in enumerate(nodes_to_execute):
        if hasattr(node, 'is_custom_node') and node.is_custom_node:
            source_code = getattr(node.func, '_custom_source', None)
            if not source_code:
                source_code = inspect.getsource(node.func)
        else:
            # 内置节点使用内置代码映射
            source_code = _get_builtin_node_code(node.name)
            if not source_code:
                continue
        
        # 提取导入
        imports = _extract_imports(source_code)
        all_imports.update(imports)
        
        # 提取函数名
        func_name = _extract_func_name(source_code)
        node_functions.append({
            'node': node,
            'func_name': func_name,
            'source_code': source_code,
            'index': idx
        })
    
    # 构建批量执行脚本
    script = _build_loop_execution_script(
        node_functions,
        list(all_imports),
        iterator_values,
        nodes_to_execute,
        all_nodes
    )
    
    # 使用嵌入式执行器执行
    try:
        executor = get_embedded_executor()
        result = _execute_script_in_embedded(executor, script, timeout=300)
        
        if isinstance(result, list):
            colored_print(f"  批量循环执行完成，收集 {len(result)} 个结果", "info")
            return result
        else:
            colored_print(f"  批量循环执行完成，结果：{result}", "debug")
            return [result] * len(iterator_values)
            
    except Exception as e:
        colored_print(f"  批量循环执行出错：{e}", "error")
        raise


def _get_builtin_node_code(node_name: str) -> Optional[str]:
    """获取内置节点的源代码"""
    BUILTIN_NODE_SOURCE = {
        "打印节点": '''def node_print(data):
    """打印输出节点"""
    print(f"执行结果：{data}")
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
    import re
    tokens = re.findall(r'([^\\.\\[\\]]+)|\\[(\\d+)\\]', path)
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
    }
    return BUILTIN_NODE_SOURCE.get(node_name)


def _extract_func_name(code: str) -> str:
    """从代码中提取函数名"""
    pattern = r'^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    matches = re.findall(pattern, code, re.MULTILINE)
    if not matches:
        raise ValueError("代码中未找到函数定义")
    return matches[0]


def _build_loop_execution_script(
    node_functions: List[Dict],
    imports: List[str],
    iterator_values: List[Any],
    nodes_to_execute: List[SimpleNodeItem],
    all_nodes: List[SimpleNodeItem]
) -> str:
    """构建循环批量执行脚本"""
    
    # 序列化迭代值
    iterator_values_json = json.dumps(iterator_values, ensure_ascii=False, default=str)
    
    # 构建节点参数字典
    node_params = {}
    for node in nodes_to_execute:
        node_key = f"node_{nodes_to_execute.index(node)}"
        params = {}
        for port in node.input_ports:
            # 检查是否有连接
            has_connection = False
            for conn in port.connections:
                if conn.start_port:
                    source_node = conn.start_port.parent_node
                    if isinstance(source_node, LoopNodeItem):
                        if conn.start_port.port_name == '迭代值':
                            # 连接到迭代值，标记为特殊值
                            params[port.port_name] = '__ITERATOR_VALUE__'
                            has_connection = True
                            break
                    elif isinstance(source_node, SimpleNodeItem):
                        source_idx = nodes_to_execute.index(source_node) if source_node in nodes_to_execute else -1
                        if source_idx >= 0:
                            params[port.port_name] = f'__RESULT_node_{source_idx}__'
                            has_connection = True
                            break
            
            if not has_connection:
                # 使用预设参数值
                param_value = node.param_values.get(port.port_name)
                params[port.port_name] = param_value
        
        node_params[node_key] = {
            'func_name': next((nf['func_name'] for nf in node_functions if nf['node'] == node), None),
            'params': params
        }
    
    # 构建脚本
    script_parts = []
    script_parts.append("# -*- coding: utf-8 -*-")
    script_parts.append("# 循环批量执行脚本 - 由 NodePython 自动生成")
    script_parts.append("")
    
    # 导入
    script_parts.append("import sys")
    script_parts.append("import json")
    for imp in imports:
        script_parts.append(f"import {imp}")
    script_parts.append("")
    
    # 节点函数定义
    script_parts.append("# ==================== 节点函数定义 ====================")
    for nf in node_functions:
        script_parts.append(f"# 节点：{nf['node'].name}")
        script_parts.append(nf['source_code'])
        script_parts.append("")
    
    # 执行主函数
    script_parts.append("# ==================== 执行主函数 ====================")
    script_parts.append(f"iterator_values = json.loads('{iterator_values_json}')")
    script_parts.append("all_results = []")
    script_parts.append("")
    script_parts.append("for iter_idx, iterator_value in enumerate(iterator_values):")
    script_parts.append("    results = {}")
    script_parts.append("    logs = []")
    
    # 为每个节点生成调用代码
    for node in nodes_to_execute:
        node_key = f"node_{nodes_to_execute.index(node)}"
        func_name = node_params[node_key]['func_name']
        params = node_params[node_key]['params']
        
        # 构建参数字典，替换特殊标记
        args_parts = []
        for param_name, param_value in params.items():
            if param_value == '__ITERATOR_VALUE__':
                args_parts.append(f"{param_name}=iterator_value")
            elif str(param_value).startswith('__RESULT_'):
                source_key = param_value.replace('__RESULT_', '').replace('__', '')
                args_parts.append(f"{param_name}=results.get('{source_key}')")
            else:
                args_parts.append(f"{param_name}={repr(param_value)}")
        
        args_str = ', '.join(args_parts)
        
        script_parts.append(f"    # 执行节点：{node.name}")
        script_parts.append(f"    try:")
        script_parts.append(f"        result_{node_key} = {func_name}({args_str})")
        script_parts.append(f"        results['{node_key}'] = result_{node_key}")
        script_parts.append(f"        logs.append(f'节点 {node.name} 执行完成：{{result_{node_key}}}')")
        script_parts.append(f"    except Exception as e:")
        script_parts.append(f"        logs.append(f'节点 {node.name} 执行出错：{{e}}')")
        script_parts.append(f"        results['{node_key}'] = None")
        script_parts.append("")
    
    # 收集结果（使用最后一个节点的输出）
    if nodes_to_execute:
        last_node_key = f"node_{len(nodes_to_execute) - 1}"
        script_parts.append(f"    # 收集本次迭代结果")
        script_parts.append(f"    all_results.append(results.get('{last_node_key}'))")
        script_parts.append("")
    
    # 输出结果
    script_parts.append("# 输出执行结果")
    script_parts.append("output = {")
    script_parts.append("    'success': True,")
    script_parts.append("    'results': all_results,")
    script_parts.append("    'logs': logs")
    script_parts.append("}")
    script_parts.append("print('__LOOP_RESULT_START__')")
    script_parts.append("print(json.dumps(output, ensure_ascii=False, default=str))")
    script_parts.append("print('__LOOP_RESULT_END__')")
    
    return '\n'.join(script_parts)


def _execute_script_in_embedded(executor, script: str, timeout: int = 30) -> Any:
    """在嵌入式环境中执行脚本并解析结果"""
    # 写入临时文件
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, encoding='utf-8'
    ) as f:
        f.write(script)
        script_path = f.name
    
    try:
        import subprocess
        result = subprocess.run(
            [executor.python_exe, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',
            cwd=str(Path(executor.python_exe).parent)
        )
        
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout)
        
        # 解析结果
        stdout = result.stdout
        start_marker = "__LOOP_RESULT_START__"
        end_marker = "__LOOP_RESULT_END__"
        
        start_idx = stdout.find(start_marker)
        end_idx = stdout.find(end_marker)
        
        if start_idx == -1 or end_idx == -1:
            # 尝试直接解析
            print(f"输出：{stdout}")
            return None
        
        json_str = stdout[start_idx + len(start_marker):end_idx].strip()
        data = json.loads(json_str)
        
        if data.get('success'):
            return data.get('results', [])
        else:
            raise RuntimeError(data.get('error', '未知错误'))
            
    finally:
        try:
            os.unlink(script_path)
        except:
            pass


def _get_nodes_connected_to_loop(loop_node: LoopNodeItem, all_nodes: List[SimpleNodeItem]) -> tuple:
    """获取连接到循环节点的节点
    
    不仅获取直接连接的节点，还包括这些节点的下游节点（节点链）
    
    Returns:
        (iteration_nodes, result_nodes) - 迭代节点列表和结果节点列表
    """
    iteration_nodes = set()  # 连接到"迭代值"端口的节点及其下游
    result_nodes = set()     # 连接到"汇总结果"端口的节点及其下游
    
    # 首先获取直接连接的节点
    direct_iteration_nodes = set()
    direct_result_nodes = set()
    
    for node in all_nodes:
        if not isinstance(node, SimpleNodeItem):
            continue
        if node == loop_node:
            continue
            
        for port in node.input_ports:
            for conn in port.connections:
                if conn.start_port and conn.start_port.parent_node == loop_node:
                    if conn.start_port.port_name == '迭代值':
                        direct_iteration_nodes.add(node)
                    elif conn.start_port.port_name == '汇总结果':
                        direct_result_nodes.add(node)
    
    # 获取直接连接到迭代值的节点的下游节点（节点链）
    def get_downstream_nodes(start_nodes: Set[SimpleNodeItem], all_nodes: List[SimpleNodeItem]) -> Set[SimpleNodeItem]:
        """获取起始节点的所有下游节点"""
        result = set(start_nodes)
        queue = list(start_nodes)
        
        while queue:
            current = queue.pop(0)
            # 查找以当前节点输出为输入的节点
            for node in all_nodes:
                if not isinstance(node, SimpleNodeItem):
                    continue
                if node in result:
                    continue
                if node == loop_node:
                    continue
                    
                for port in node.input_ports:
                    for conn in port.connections:
                        if conn.start_port and conn.start_port.parent_node == current:
                            result.add(node)
                            queue.append(node)
                            break
        
        return result
    
    # 获取完整的节点链
    iteration_nodes = get_downstream_nodes(direct_iteration_nodes, all_nodes)
    result_nodes = get_downstream_nodes(direct_result_nodes, all_nodes)
    
    return list(iteration_nodes), list(result_nodes)


def execute_loop(
    loop_node: LoopNodeItem,
    all_nodes: List[SimpleNodeItem],
    external_input: Any = None
) -> List[Any]:
    """执行循环节点

    使用批量执行模式，将所有迭代合并成一个脚本，只启动一次 Python 子进程。

    Args:
        loop_node: 循环节点实例
        all_nodes: 场景中所有节点列表
        external_input: 外部输入数据（可选）

    Returns:
        循环结果列表
    """
    from utils.console_stream import colored_print

    # 保存原始配置值（用于执行后恢复）
    original_range_start = loop_node.range_start
    original_range_end = loop_node.range_end
    original_range_step = loop_node.range_step
    original_list_data = loop_node.list_data

    # 获取迭代器值
    iterator_values = loop_node.get_iterator_values()

    if not iterator_values:
        colored_print(f"  循环节点 '{loop_node.loop_name}': 没有迭代数据", "warning")
        return []

    colored_print(f"\n开始执行循环 '{loop_node.loop_name}': 共 {len(iterator_values)} 次迭代", "info")

    # 重置循环状态
    loop_node.reset_execution_state()
    loop_node._total_iterations = len(iterator_values)

    # 获取连接到循环节点的节点
    iteration_nodes, result_nodes = _get_nodes_connected_to_loop(loop_node, all_nodes)

    # 获取循环内部的节点（容器模式）
    inner_nodes = loop_node.nodes

    colored_print(f"  循环内节点：{len(inner_nodes)} 个", "debug")
    colored_print(f"  连接到迭代值的节点：{[n.name for n in iteration_nodes]}", "debug")
    colored_print(f"  连接到汇总结果的节点：{[n.name for n in result_nodes]}", "debug")

    # 使用批量执行模式
    all_results = []
    
    try:
        # 批量执行所有迭代
        all_results = _execute_loop_batch(
            loop_node,
            iteration_nodes,
            inner_nodes,
            iterator_values,
            all_nodes
        )
        
        # 更新结果显示和节点状态
        for index, result in enumerate(all_results):
            loop_node.add_result(result)
            loop_node.update_iterator_display(index)
        
        # 批量执行完成后，将所有迭代节点设置为成功状态
        for node in iteration_nodes:
            node.set_status(SimpleNodeItem.STATUS_SUCCESS)
        
        # 设置循环节点为成功状态（重置迭代索引）
        loop_node._current_index = -1
        loop_node.update()  # 触发重绘
            
    except Exception as e:
        colored_print(f"  批量执行失败，回退到逐次执行：{e}", "warning")
        # 回退到逐次执行模式
        for index, current_value in enumerate(iterator_values):
            colored_print(f"\n  [{index + 1}/{len(iterator_values)}] 迭代值：{current_value}", "debug")
            try:
                result = _execute_single_iteration(
                    loop_node,
                    index,
                    current_value,
                    inner_nodes,
                    iteration_nodes,
                    all_nodes,
                    external_input
                )
                loop_node.add_result(result)
                all_results.append(result)
                loop_node.update_iterator_display(index)
            except Exception as e2:
                colored_print(f"    [ERROR] 迭代 {index + 1} 出错：{e2}", "error")
                all_results.append(None)
        
        # 回退执行完成后，也设置节点状态
        for node in iteration_nodes:
            if node.result is not None:
                node.set_status(SimpleNodeItem.STATUS_SUCCESS)
            else:
                node.set_status(SimpleNodeItem.STATUS_ERROR, "节点未执行")
        
        # 重置循环节点索引
        loop_node._current_index = -1
        loop_node.update()  # 触发重绘

    colored_print(f"\n循环 '{loop_node.loop_name}' 执行完成，收集 {len(all_results)} 个结果", "info")
    colored_print(f"循环 '{loop_node.loop_name}' 汇总结果：{all_results}", "success")

    # 执行连接到汇总结果的节点
    if result_nodes:
        colored_print(f"\n执行连接到汇总结果的节点...", "info")
        _execute_result_nodes(result_nodes, loop_node, all_nodes)

    # 恢复原始配置值
    loop_node.range_start = original_range_start
    loop_node.range_end = original_range_end
    loop_node.range_step = original_range_step
    loop_node.list_data = original_list_data

    return all_results


def _execute_result_nodes(result_nodes: List[SimpleNodeItem], loop_node: LoopNodeItem,
                          all_nodes: List[SimpleNodeItem]):
    """执行连接到汇总结果的节点"""
    from utils.console_stream import colored_print

    for node in result_nodes:
        try:
            colored_print(f"  执行节点：{node.name}", "debug")
            _execute_node(node, all_nodes)
            colored_print(f"    结果：{node.result}", "success")
            # 设置节点为成功状态
            node.set_status(SimpleNodeItem.STATUS_SUCCESS)
        except Exception as e:
            colored_print(f"    [ERROR] 节点 '{node.name}' 执行出错：{e}", "error")
            node.set_status(SimpleNodeItem.STATUS_ERROR, str(e))


def _execute_single_iteration(
    loop_node: LoopNodeItem,
    index: int,
    iterator_value: Any,
    inner_nodes: List,
    iteration_nodes: List[SimpleNodeItem],
    all_nodes: List[SimpleNodeItem],
    external_input: Any = None
) -> Any:
    """执行单次迭代

    Args:
        loop_node: 循环节点
        index: 当前迭代索引
        iterator_value: 当前迭代值
        inner_nodes: 循环内部的节点（容器模式）
        iteration_nodes: 连接到迭代值的节点（连接模式）
        all_nodes: 所有节点
        external_input: 外部输入数据

    Returns:
        本次迭代的结果
    """
    from utils.console_stream import colored_print

    # 合并容器模式和连接模式的节点
    nodes_to_execute = list(inner_nodes) + iteration_nodes
    # 去重
    nodes_to_execute = list(set(nodes_to_execute))

    if not nodes_to_execute:
        # 当循环内没有节点时，使用迭代值作为结果
        colored_print(f"    循环内没有节点，使用迭代值作为结果：{iterator_value}", "debug")
        return iterator_value

    # 对节点进行拓扑排序
    try:
        sorted_nodes = topological_sort(nodes_to_execute)
    except Exception as e:
        colored_print(f"    拓扑排序失败：{e}", "warning")
        sorted_nodes = nodes_to_execute

    # 重置所有节点的状态
    for node in sorted_nodes:
        if isinstance(node, SimpleNodeItem):
            node.result = None
            node.reset_status()

    iteration_results = {}
    last_result = None

    for node in sorted_nodes:
        try:
            # 检查是否是循环节点（嵌套循环）
            if isinstance(node, LoopNodeItem):
                colored_print(f"      执行嵌套循环 '{node.loop_name}'...", "info")
                loop_result = execute_loop(node, all_nodes, external_input)
                result_key = f"{id(node)}_result"
                iteration_results[result_key] = loop_result
                colored_print(f"      嵌套循环 '{node.loop_name}' 完成，结果：{loop_result}", "debug")
                continue

            # 执行节点
            result = _execute_node(node, all_nodes, iterator_value)
            
            # 存储结果
            if node.output_ports:
                output_port_name = node.output_ports[0].port_name
                result_key = f"{node.node_id}_{output_port_name}"
                iteration_results[result_key] = result

            node.result = result
            last_result = result
            
            if isinstance(node, SimpleNodeItem):
                node.set_status(SimpleNodeItem.STATUS_SUCCESS)

        except Exception as e:
            node_name = getattr(node, 'loop_name', None) or getattr(node, 'name', '未知节点')
            colored_print(f"      节点 '{node_name}' 执行出错：{e}", "error")
            if isinstance(node, SimpleNodeItem):
                node.set_status(SimpleNodeItem.STATUS_ERROR, str(e))
            raise

    return last_result


def _apply_external_inputs_to_loop_node(
    loop_node: LoopNodeItem,
    all_nodes: List[SimpleNodeItem]
) -> bool:
    """应用外部输入到循环节点的配置参数
    
    检查循环节点的输入端口连接，从外部节点获取值并更新循环配置。
    
    Args:
        loop_node: 循环节点
        all_nodes: 所有节点列表
        
    Returns:
        是否成功应用所有外部输入
    """
    from utils.console_stream import colored_print
    
    has_connection = False
    
    for port in loop_node.input_ports:
        for conn in port.connections:
            if conn.start_port:
                source_node = conn.start_port.parent_node
                if isinstance(source_node, SimpleNodeItem) and source_node.result is not None:
                    has_connection = True
                    value = source_node.result

                    # 区间循环端口：最小值、最大值、步长
                    if loop_node.loop_type == LoopNodeItem.LOOP_TYPE_RANGE:
                        if port.port_name == '最小值':
                            # 使用属性设置，自动触发验证
                            loop_node.range_start = value
                            colored_print(f"  外部输入 - 最小值：{value}", "debug")
                        elif port.port_name == '最大值':
                            # 使用属性设置，自动触发验证
                            loop_node.range_end = value
                            colored_print(f"  外部输入 - 最大值：{value}", "debug")
                        elif port.port_name == '步长':
                            # 使用属性设置，自动触发验证
                            loop_node.range_step = value
                            colored_print(f"  外部输入 - 步长：{value}", "debug")

                    # 列表循环端口：列表数据
                    elif loop_node.loop_type == LoopNodeItem.LOOP_TYPE_LIST:
                        if port.port_name == '列表数据':
                            # 使用属性设置，自动触发验证
                            loop_node.list_data = value
                            colored_print(f"  外部输入 - 列表数据：{loop_node.list_data}", "debug")
    
    return has_connection


def execute_graph_with_loops(
    nodes: List[SimpleNodeItem],
    loop_nodes: List[LoopNodeItem],
    executor=None
) -> bool:
    """执行包含循环节点的图表

    Args:
        nodes: 普通节点列表
        loop_nodes: 循环节点列表
        executor: 执行器（兼容旧接口）

    Returns:
        执行是否成功
    """
    from utils.console_stream import colored_print

    colored_print("=" * 50, "system")
    colored_print("开始运行图表（包含循环节点）...", "info")

    if not nodes and not loop_nodes:
        colored_print("没有节点可执行。", "warning")
        return False

    # 重置所有节点状态
    for node in nodes:
        node.result = None
        node.reset_status()

    for loop_node in loop_nodes:
        loop_node.reset_execution_state()

    # 获取场景中所有节点（包括循环节点内部的节点）
    all_nodes = list(nodes)
    for loop_node in loop_nodes:
        all_nodes.extend(loop_node.nodes)

    # 对普通节点进行拓扑排序
    sorted_nodes = topological_sort(nodes) if nodes else []

    # 将节点分为三类
    pre_loop_nodes = []
    post_loop_nodes = []

    # 获取所有连接到循环迭代值的节点（这些节点在循环内执行，不应在循环后重复执行）
    iteration_nodes_set = set()
    for loop_node in loop_nodes:
        iteration_nodes, _ = _get_nodes_connected_to_loop(loop_node, all_nodes)
        iteration_nodes_set.update(iteration_nodes)

    for node in sorted_nodes:
        # 检查节点是否在循环内
        in_loop = False
        for loop_node in loop_nodes:
            if loop_node.contains_node(node):
                in_loop = True
                break

        if in_loop:
            continue

        # 跳过连接到迭代值的节点（这些节点已在循环内执行）
        if node in iteration_nodes_set:
            continue

        # 检查节点是否依赖循环节点的结果
        depends_on_loop = False
        for port in node.input_ports:
            for conn in port.connections:
                if conn.start_port:
                    source_node = conn.start_port.parent_node
                    if isinstance(source_node, LoopNodeItem):
                        depends_on_loop = True
                        break
            if depends_on_loop:
                break

        if depends_on_loop:
            post_loop_nodes.append(node)
        else:
            pre_loop_nodes.append(node)

    colored_print(f"循环前节点：{[n.name for n in pre_loop_nodes]}", "debug")
    colored_print(f"循环节点：{[ln.loop_name for ln in loop_nodes]}", "debug")
    colored_print(f"循环后节点：{[n.name for n in post_loop_nodes]}", "debug")

    # 标记运行状态
    for node in sorted_nodes:
        node.set_status(SimpleNodeItem.STATUS_RUNNING)

    from PySide6.QtWidgets import QApplication
    if QApplication.instance():
        QApplication.instance().processEvents()

    try:
        has_error = False

        # 1. 先执行循环前的节点
        colored_print("\n执行循环前节点...", "info")
        for node in pre_loop_nodes:
            try:
                result = _execute_node(node, pre_loop_nodes)
                if result is not None:
                    colored_print(f"节点 '{node.name}' 结果：{result}", "success")
            except Exception as e:
                colored_print(f"❌ 节点 '{node.name}' 执行出错：{e}", "error")
                node.set_status(SimpleNodeItem.STATUS_ERROR, str(e))
                has_error = True

        # 2. 执行循环节点
        colored_print("\n执行循环节点...", "info")
        for loop_node in loop_nodes:
            try:
                # 应用外部输入到循环节点配置
                _apply_external_inputs_to_loop_node(loop_node, all_nodes)
                
                # 执行循环（传入所有节点以支持连接模式）
                loop_results = execute_loop(loop_node, all_nodes)

                if loop_results:
                    colored_print(f"循环 '{loop_node.loop_name}' 汇总结果：{loop_results}", "success")

            except Exception as e:
                colored_print(f"❌ 循环 '{loop_node.loop_name}' 执行出错：{e}", "error")
                has_error = True

        # 3. 最后执行循环后的节点
        colored_print("\n执行循环后节点...", "info")
        for node in post_loop_nodes:
            try:
                result = _execute_node(node, pre_loop_nodes + post_loop_nodes)
                if result is not None:
                    colored_print(f"节点 '{node.name}' 结果：{result}", "success")
            except Exception as e:
                colored_print(f"❌ 节点 '{node.name}' 执行出错：{e}", "error")
                node.set_status(SimpleNodeItem.STATUS_ERROR, str(e))
                has_error = True

        colored_print("\n" + "=" * 40, "system")
        if has_error:
            colored_print("运行完成（有错误）", "warning")
        else:
            colored_print("运行完成！", "success")
        colored_print("=" * 40, "system")

        return not has_error

    except Exception as e:
        colored_print(f"\n运行出错：{e}", "error")
        import traceback
        colored_print(traceback.format_exc(), "error")
        return False
