"""调试执行引擎

支持两种调试模式：
1. 单节点调试 - 只执行单个节点，使用节点属性面板的输入值
2. 断点调试 - 执行选中节点及其上游依赖路径上的所有节点

支持节点类型：
- SimpleNodeItem: 普通节点
- LoopNodeItem: 循环节点（区间循环、List 循环）
"""

from typing import List, Dict, Any, Set, Optional, Tuple
from ..graphics.simple_node_item import SimpleNodeItem
from ..graphics.loop_node_item import LoopNodeItem, RangeLoopNodeItem, ListLoopNodeItem
from ..nodes.node_library import LOCAL_NODE_LIBRARY
from utils.console_stream import colored_print


class DebugExecutor:
    """调试执行器"""

    @staticmethod
    def debug_single_node(node: SimpleNodeItem) -> bool:
        """单节点调试 - 只执行单个节点

        使用该节点属性面板中设置的输入值进行调试。
        如果属性面板的输入值不符合要求，会提示用户。

        Args:
            node: 要调试的节点

        Returns:
            执行是否成功
        """
        colored_print("=" * 50, "system")
        colored_print(f"【单节点调试】节点：{node.name}", "info")
        colored_print("=" * 50, "system")

        try:
            # 准备输入参数
            kwargs = DebugExecutor._prepare_node_inputs(node)

            # 显示输入参数
            colored_print(f"\n输入参数:", "debug")
            for param_name, value in kwargs.items():
                colored_print(f"  {param_name}: {value}", "debug")

            # 执行节点
            colored_print(f"\n执行节点 '{node.name}'...", "info")
            result = node.func(**kwargs)

            # 显示结果
            node.result = result
            node.set_status(SimpleNodeItem.STATUS_SUCCESS)

            colored_print(f"\n执行结果:", "success")
            if result is not None:
                colored_print(f"  {result}", "success")
            else:
                colored_print("  无返回值", "info")

            colored_print("\n" + "=" * 50, "system")
            colored_print("单节点调试完成", "success")
            colored_print("=" * 50, "system")

            return True

        except TypeError as e:
            # 参数类型错误
            error_msg = str(e)
            colored_print(f"\n❌ 执行出错：{error_msg}", "error")
            colored_print("\n💡 提示：单节点调试需要使用属性面板设置正确的输入值", "warning")
            colored_print("请检查：", "warning")
            colored_print("  1. 参数类型是否正确（整数/浮点数/字符串/列表/字典）", "warning")
            colored_print("  2. 必需参数是否已设置", "warning")
            colored_print("  3. 列表/字典参数是否使用正确的 JSON 格式", "warning")

            node.set_status(SimpleNodeItem.STATUS_ERROR, error_msg)
            return False

        except Exception as e:
            error_msg = str(e)
            colored_print(f"\n❌ 执行出错：{error_msg}", "error")
            import traceback
            colored_print(traceback.format_exc(), "error")

            node.set_status(SimpleNodeItem.STATUS_ERROR, error_msg)
            return False

    @staticmethod
    def debug_single_loop_node(loop_node: LoopNodeItem, all_nodes: List = None) -> bool:
        """单节点调试 - 循环节点

        执行一次完整的循环迭代。
        优先使用外部连接的输入值，如果没有连接则使用属性面板的配置值。

        Args:
            loop_node: 要调试的循环节点
            all_nodes: 场景中所有节点列表（可选，用于获取外部输入）

        Returns:
            执行是否成功
        """
        colored_print("=" * 50, "system")
        colored_print(f"【单节点调试】循环节点：{loop_node.loop_name}", "info")
        colored_print(f"循环类型：{loop_node.loop_type}", "debug")
        colored_print("=" * 50, "system")

        try:
            # 首先尝试应用外部输入
            if all_nodes:
                upstream_nodes = DebugExecutor._get_loop_upstream_nodes(loop_node, all_nodes)
                colored_print(f"\n收集到上游节点：{[n.name for n in upstream_nodes]}", "debug")
                
                if upstream_nodes:
                    colored_print(f"\n执行上游依赖节点（共 {len(upstream_nodes)} 个）:", "info")
                    
                    for node in upstream_nodes:
                        node.result = None
                        node.reset_status()
                    
                    for i, node in enumerate(upstream_nodes, 1):
                        colored_print(f"\n[{i}/{len(upstream_nodes)}] 执行上游节点：{node.name}", "debug")
                        
                        try:
                            kwargs = DebugExecutor._prepare_node_inputs_with_connections(
                                node, upstream_nodes[:i]
                            )
                            result = node.func(**kwargs)
                            node.result = result
                            node.set_status(SimpleNodeItem.STATUS_SUCCESS)
                            colored_print(f"  → 结果：{result}", "debug")
                        except Exception as e:
                            colored_print(f"  ❌ 节点 '{node.name}' 执行出错：{e}", "error")
                            return False
                    
                    # 应用上游节点的输出到循环节点的输入端口
                    DebugExecutor._apply_inputs_to_loop_node(loop_node, upstream_nodes)
                else:
                    colored_print(f"\n没有上游依赖节点，使用属性面板值", "debug")

            # 获取迭代器值（使用外部输入或属性面板值）
            iterator_values = loop_node.get_iterator_values()

            if not iterator_values:
                colored_print(f"\n⚠ 循环节点没有迭代数据", "warning")
                colored_print("请检查循环参数设置是否正确", "warning")
                return False

            # 显示循环配置
            if isinstance(loop_node, RangeLoopNodeItem):
                colored_print(f"\n循环配置:", "info")
                colored_print(f"  最小值：{loop_node.range_start}", "debug")
                colored_print(f"  最大值：{loop_node.range_end}", "debug")
                colored_print(f"  步长：{loop_node.range_step}", "debug")
            elif isinstance(loop_node, ListLoopNodeItem):
                colored_print(f"\n循环配置:", "info")
                colored_print(f"  列表数据：{loop_node.list_data}", "debug")

            colored_print(f"\n迭代数据（共 {len(iterator_values)} 项）:", "info")
            if len(iterator_values) <= 10:
                colored_print(f"  {iterator_values}", "debug")
            else:
                colored_print(f"  {iterator_values[:5]} ... (共 {len(iterator_values)} 项)", "debug")

            # 执行循环（空节点列表，只验证循环本身）
            colored_print(f"\n执行循环...", "info")
            results = []
            for i, value in enumerate(iterator_values, 1):
                colored_print(f"  [{i}/{len(iterator_values)}] 迭代值：{value}", "debug")
                results.append(value)

            # 显示结果
            loop_node._loop_results = results
            loop_node.reset_execution_state()

            colored_print(f"\n循环结果:", "success")
            colored_print(f"  {results}", "success")

            colored_print("\n" + "=" * 50, "system")
            colored_print("循环节点单节点调试完成", "success")
            colored_print("=" * 50, "system")

            return True

        except Exception as e:
            error_msg = str(e)
            colored_print(f"\n❌ 执行出错：{error_msg}", "error")
            import traceback
            colored_print(traceback.format_exc(), "error")
            return False

    @staticmethod
    def debug_breakpoint(target_node: SimpleNodeItem, all_nodes: List[SimpleNodeItem]) -> bool:
        """断点调试 - 执行目标节点及其上游依赖路径

        基于 Python 代码的顺序执行原理，执行从起始节点到目标节点的完整路径。

        Args:
            target_node: 目标调试节点（用户选中的节点）
            all_nodes: 场景中所有节点列表

        Returns:
            执行是否成功
        """
        colored_print("=" * 50, "system")
        colored_print(f"【断点调试】目标节点：{target_node.name}", "info")
        colored_print("=" * 50, "system")

        try:
            # 获取上游依赖节点（按执行顺序排序）
            upstream_nodes = DebugExecutor._get_upstream_nodes(target_node, all_nodes)

            if not upstream_nodes:
                colored_print("\n⚠ 该节点没有上游依赖，将只执行目标节点", "warning")
                upstream_nodes = [target_node]

            colored_print(f"\n执行路径（共 {len(upstream_nodes)} 个节点）:", "info")
            for i, node in enumerate(upstream_nodes, 1):
                marker = "→ " if node == target_node else "  "
                colored_print(f"  {marker}[{i}] {node.name}", "debug" if node != target_node else "info")

            # 重置所有相关节点的状态
            for node in upstream_nodes:
                node.result = None
                node.reset_status()

            # 按顺序执行每个节点
            colored_print(f"\n开始执行...", "info")

            for i, node in enumerate(upstream_nodes, 1):
                is_target = (node == target_node)

                if is_target:
                    colored_print(f"\n{'='*40}", "system")
                    colored_print(f"【断点】执行目标节点 [{i}/{len(upstream_nodes)}]: {node.name}", "info")
                    colored_print(f"{'='*40}", "system")
                else:
                    colored_print(f"\n[{i}/{len(upstream_nodes)}] 执行上游节点：{node.name}", "debug")

                try:
                    # 准备输入参数
                    kwargs = DebugExecutor._prepare_node_inputs_with_connections(
                        node, upstream_nodes[:i]
                    )

                    # 执行节点
                    result = node.func(**kwargs)
                    node.result = result
                    node.set_status(SimpleNodeItem.STATUS_SUCCESS)

                    # 显示结果
                    if result is not None:
                        colored_print(f"  → 结果：{result}", "success" if is_target else "debug")
                    else:
                        colored_print(f"  → 执行完成（无返回值）", "info" if is_target else "debug")

                except Exception as e:
                    error_msg = str(e)
                    colored_print(f"  ❌ 节点 '{node.name}' 执行出错：{error_msg}", "error")
                    node.set_status(SimpleNodeItem.STATUS_ERROR, error_msg)

                    if not is_target:
                        colored_print(f"  ⚠ 上游节点执行失败，无法继续执行目标节点", "warning")

                    import traceback
                    colored_print(traceback.format_exc(), "error")
                    return False

            # 显示最终结果
            colored_print(f"\n{'='*50}", "system")
            colored_print("断点调试完成", "success")
            colored_print(f"目标节点 '{target_node.name}' 最终结果：{target_node.result}", "success")
            colored_print("=" * 50, "system")

            return True

        except Exception as e:
            colored_print(f"\n❌ 调试执行失败：{e}", "error")
            import traceback
            colored_print(traceback.format_exc(), "error")
            return False

    @staticmethod
    def debug_breakpoint_loop(loop_node: LoopNodeItem, all_nodes: List) -> bool:
        """断点调试 - 循环节点

        执行循环节点及其上游依赖节点，包括：
        1. 执行所有上游依赖节点（为循环提供输入数据）
        2. 执行完整的循环迭代

        Args:
            loop_node: 目标调试的循环节点
            all_nodes: 场景中所有节点列表（包括普通节点和循环节点）

        Returns:
            执行是否成功
        """
        colored_print("=" * 50, "system")
        colored_print(f"【断点调试】循环节点：{loop_node.loop_name}", "info")
        colored_print(f"循环类型：{loop_node.loop_type}", "debug")
        colored_print("=" * 50, "system")

        try:
            # 获取上游依赖节点（为循环提供输入的节点）
            upstream_nodes = DebugExecutor._get_loop_upstream_nodes(loop_node, all_nodes)

            # 显示循环配置
            if isinstance(loop_node, RangeLoopNodeItem):
                colored_print(f"\n循环配置:", "info")
                colored_print(f"  最小值：{loop_node.range_start}", "debug")
                colored_print(f"  最大值：{loop_node.range_end}", "debug")
                colored_print(f"  步长：{loop_node.range_step}", "debug")
            elif isinstance(loop_node, ListLoopNodeItem):
                colored_print(f"\n循环配置:", "info")
                colored_print(f"  列表数据：{loop_node.list_data}", "debug")

            # 执行上游节点
            if upstream_nodes:
                colored_print(f"\n执行上游依赖节点（共 {len(upstream_nodes)} 个）:", "info")
                for i, node in enumerate(upstream_nodes, 1):
                    colored_print(f"  [{i}] {node.name}", "debug")

                for node in upstream_nodes:
                    node.result = None
                    node.reset_status()

                for i, node in enumerate(upstream_nodes, 1):
                    colored_print(f"\n[{i}/{len(upstream_nodes)}] 执行上游节点：{node.name}", "debug")

                    try:
                        kwargs = DebugExecutor._prepare_node_inputs_with_connections(
                            node, upstream_nodes[:i]
                        )
                        result = node.func(**kwargs)
                        node.result = result
                        node.set_status(SimpleNodeItem.STATUS_SUCCESS)
                        colored_print(f"  → 结果：{result}", "debug")
                    except Exception as e:
                        colored_print(f"  ❌ 节点 '{node.name}' 执行出错：{e}", "error")
                        return False

            # 应用上游节点的输出到循环节点的输入端口
            DebugExecutor._apply_inputs_to_loop_node(loop_node, upstream_nodes)

            # 执行循环
            colored_print(f"\n执行循环 '{loop_node.loop_name}'...", "info")
            iterator_values = loop_node.get_iterator_values()

            if not iterator_values:
                colored_print(f"\n⚠ 循环节点没有迭代数据", "warning")
                return False

            colored_print(f"\n迭代数据（共 {len(iterator_values)} 项）:", "info")
            if len(iterator_values) <= 10:
                colored_print(f"  {iterator_values}", "debug")
            else:
                colored_print(f"  {iterator_values[:5]} ... (共 {len(iterator_values)} 项)", "debug")

            # 执行循环迭代
            results = []
            for i, value in enumerate(iterator_values, 1):
                colored_print(f"  [{i}/{len(iterator_values)}] 迭代值：{value}", "debug")
                results.append(value)

            # 保存结果
            loop_node._loop_results = results
            loop_node.reset_execution_state()

            # 显示循环结果
            colored_print(f"\n循环结果:", "success")
            colored_print(f"  {results}", "success")

            colored_print("\n" + "=" * 50, "system")
            colored_print("循环节点断点调试完成", "success")
            colored_print("=" * 50, "system")

            return True

        except Exception as e:
            colored_print(f"\n❌ 调试执行失败：{e}", "error")
            import traceback
            colored_print(traceback.format_exc(), "error")
            return False

    @staticmethod
    def _apply_inputs_to_loop_node(loop_node: LoopNodeItem, upstream_nodes: List[SimpleNodeItem]):
        """应用上游节点的输出到循环节点的输入端口

        Args:
            loop_node: 循环节点
            upstream_nodes: 上游节点列表
        """
        applied_inputs = {}
        for port in loop_node.input_ports:
            for conn in port.connections:
                if conn.start_port:
                    source_node = conn.start_port.parent_node
                    if source_node in upstream_nodes and source_node.result is not None:
                        value = source_node.result
                        applied_inputs[port.port_name] = value

                        if isinstance(loop_node, RangeLoopNodeItem):
                            if port.port_name == '最小值':
                                loop_node.range_start = value
                            elif port.port_name == '最大值':
                                loop_node.range_end = value
                            elif port.port_name == '步长':
                                loop_node.range_step = value
                        elif isinstance(loop_node, ListLoopNodeItem):
                            if port.port_name == '列表数据':
                                loop_node.list_data = value
        
        if applied_inputs:
            colored_print(f"\n应用外部输入到循环节点:", "debug")
            for port_name, value in applied_inputs.items():
                colored_print(f"  {port_name}: {value}", "debug")

    @staticmethod
    def _get_loop_upstream_nodes(
        loop_node: LoopNodeItem,
        all_nodes: List
    ) -> List[SimpleNodeItem]:
        """获取循环节点的上游依赖节点

        Args:
            loop_node: 循环节点
            all_nodes: 所有节点列表

        Returns:
            上游节点列表（按执行顺序）
        """
        related_nodes = set()
        visited = set()

        def collect_upstream(node):
            """递归收集上游节点"""
            if id(node) in visited:
                return
            visited.add(id(node))

            if isinstance(node, SimpleNodeItem):
                related_nodes.add(node)
                # 继续收集该节点的上游
                for port in node.input_ports:
                    for conn in port.connections:
                        if conn.start_port:
                            source_node = conn.start_port.parent_node
                            if isinstance(source_node, (SimpleNodeItem, LoopNodeItem)):
                                collect_upstream(source_node)
            
            elif isinstance(node, LoopNodeItem):
                # 对于循环节点，遍历其输入端口查找上游节点
                for port in node.input_ports:
                    for conn in port.connections:
                        if conn.start_port:
                            source_node = conn.start_port.parent_node
                            if isinstance(source_node, (SimpleNodeItem, LoopNodeItem)):
                                collect_upstream(source_node)

        # 从循环节点开始收集
        collect_upstream(loop_node)
        sorted_nodes = DebugExecutor._topological_sort(list(related_nodes))
        return sorted_nodes

    @staticmethod
    def _prepare_node_inputs(node: SimpleNodeItem) -> Dict[str, Any]:
        """准备单节点调试的输入参数（仅使用属性面板的值）
        
        Args:
            node: 节点
            
        Returns:
            输入参数字典
        """
        kwargs = {}
        
        for param_name in node.param_types.keys():
            if param_name in node.param_values:
                value = node.param_values[param_name]
                kwargs[param_name] = value
            else:
                # 没有设置值，使用默认值（如果有）
                pass
        
        return kwargs
    
    @staticmethod
    def _prepare_node_inputs_with_connections(
        node: SimpleNodeItem,
        executed_nodes: List[SimpleNodeItem]
    ) -> Dict[str, Any]:
        """准备断点调试的输入参数（优先使用连接值）

        优先使用上游节点的执行结果作为输入，
        如果没有连接或上游节点没有结果，则使用属性面板的值。

        Args:
            node: 当前节点
            executed_nodes: 已执行的节点列表（用于获取输入值）

        Returns:
            输入参数字典
        """
        kwargs = {}

        for port in node.input_ports:
            param_name = port.port_name
            input_value = None
            has_connection = False

            # 检查是否有连接
            for conn in port.connections:
                if conn.start_port:
                    source_node = conn.start_port.parent_node

                    # 检查源节点是否在已执行节点中
                    if source_node in executed_nodes and source_node.result is not None:
                        input_value = source_node.result
                        has_connection = True
                        break

            if has_connection:
                kwargs[param_name] = input_value
            elif param_name in node.param_values:
                # 使用属性面板的值
                kwargs[param_name] = node.param_values[param_name]

        return kwargs
    
    @staticmethod
    def _get_upstream_nodes(
        target_node: SimpleNodeItem, 
        all_nodes: List[SimpleNodeItem]
    ) -> List[SimpleNodeItem]:
        """获取目标节点的所有上游依赖节点（按执行顺序排序）
        
        使用拓扑排序确保依赖节点先执行。
        
        Args:
            target_node: 目标节点
            all_nodes: 所有节点列表
            
        Returns:
            上游节点列表（按执行顺序）
        """
        # 收集所有相关节点（目标节点及其所有上游节点）
        related_nodes = set()
        visited = set()
        
        def collect_upstream(node: SimpleNodeItem):
            """递归收集上游节点"""
            if id(node) in visited:
                return
            visited.add(id(node))
            related_nodes.add(node)
            
            # 查找所有输入端口的连接
            for port in node.input_ports:
                for conn in port.connections:
                    if conn.start_port:
                        source_node = conn.start_port.parent_node
                        if isinstance(source_node, SimpleNodeItem) and source_node in all_nodes:
                            collect_upstream(source_node)
        
        # 从目标节点开始递归收集
        collect_upstream(target_node)
        
        # 对收集的节点进行拓扑排序
        sorted_nodes = DebugExecutor._topological_sort(list(related_nodes))
        
        return sorted_nodes
    
    @staticmethod
    def _topological_sort(nodes: List[SimpleNodeItem]) -> List[SimpleNodeItem]:
        """拓扑排序
        
        根据节点连接关系计算执行顺序，确保依赖节点先执行。
        
        Args:
            nodes: 节点列表
            
        Returns:
            排序后的节点列表
        """
        if not nodes:
            return []
        
        # 计算入度
        in_degree = {node: 0 for node in nodes}
        
        for node in nodes:
            for port in node.input_ports:
                for conn in port.connections:
                    if conn.start_port:
                        source_node = conn.start_port.parent_node
                        if source_node in nodes:
                            in_degree[node] += 1
        
        # 拓扑排序
        queue = [node for node in nodes if in_degree[node] == 0]
        sorted_nodes = []
        
        while queue:
            node = queue.pop(0)
            sorted_nodes.append(node)
            
            for port in node.output_ports:
                for conn in port.connections:
                    if conn.end_port:
                        target_node = conn.end_port.parent_node
                        if target_node in in_degree:
                            in_degree[target_node] -= 1
                            if in_degree[target_node] == 0:
                                queue.append(target_node)
        
        return sorted_nodes


def debug_single_node(node: SimpleNodeItem) -> bool:
    """单节点调试的便捷函数"""
    return DebugExecutor.debug_single_node(node)


def debug_breakpoint(target_node: SimpleNodeItem, all_nodes: List[SimpleNodeItem]) -> bool:
    """断点调试的便捷函数"""
    return DebugExecutor.debug_breakpoint(target_node, all_nodes)


def debug_single_loop_node(loop_node: LoopNodeItem, all_nodes: List = None) -> bool:
    """循环节点单节点调试的便捷函数"""
    return DebugExecutor.debug_single_loop_node(loop_node, all_nodes)


def debug_breakpoint_loop(loop_node: LoopNodeItem, all_nodes: List) -> bool:
    """循环节点断点调试的便捷函数"""
    return DebugExecutor.debug_breakpoint_loop(loop_node, all_nodes)
