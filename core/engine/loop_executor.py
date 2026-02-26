"""循环执行引擎

负责执行循环节点内的节点，处理迭代和结果汇总

支持两种使用方式：
1. 容器模式：将节点拖入循环内部，节点在每次迭代中执行
2. 连接模式：节点连接到循环节点的输出端口
   - 连接到"迭代值"端口的节点：在每次迭代中执行
   - 连接到"汇总结果"端口的节点：在循环完成后执行一次
"""

import json
import inspect
from typing import List, Dict, Any, Optional, Set
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
    import re
    imports = []
    
    # 匹配 import xxx
    import_pattern = r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    imports.extend(re.findall(import_pattern, code, re.MULTILINE))
    
    # 匹配 from xxx import
    from_pattern = r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    imports.extend(re.findall(from_pattern, code, re.MULTILINE))
    
    return list(set(imports))


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

    all_results = []

    # 遍历迭代器值
    for index, current_value in enumerate(iterator_values):
        colored_print(f"\n  [{index + 1}/{len(iterator_values)}] 迭代值：{current_value}", "debug")

        try:
            # 执行当前迭代
            result = _execute_single_iteration(
                loop_node,
                index,
                current_value,
                inner_nodes,
                iteration_nodes,
                all_nodes,
                external_input
            )

            # 记录结果
            loop_node.add_result(result)
            all_results.append(result)  # 添加结果到列表

            # 更新显示
            loop_node.update_iterator_display(index)

            if result is not None:
                colored_print(f"    迭代结果：{result}", "debug")

        except Exception as e:
            colored_print(f"    [ERROR] 迭代 {index + 1} 出错：{e}", "error")
            import traceback
            colored_print(traceback.format_exc(), "error")
            all_results.append(None)

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
        except Exception as e:
            colored_print(f"    [ERROR] 节点 '{node.name}' 执行出错：{e}", "error")


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
