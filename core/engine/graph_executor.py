"""图表执行引擎"""

from typing import List
from ..graphics.simple_node_item import SimpleNodeItem


def topological_sort(nodes: List[SimpleNodeItem]) -> List[SimpleNodeItem]:
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


def execute_graph(nodes: List[SimpleNodeItem]) -> bool:
    """执行图表"""
    print("=" * 40)
    print("开始运行图表...")

    if not nodes:
        print("没有节点可执行。")
        return False

    for node in nodes:
        node.result = None

    sorted_nodes = topological_sort(nodes)
    print(f"执行顺序: {[n.name for n in sorted_nodes]}")

    try:
        for node in sorted_nodes:
            kwargs = {}  # 使用关键字参数
            
            for port in node.input_ports:
                param_name = port.port_name
                
                if port.connections:
                    # 如果有连接，使用连接节点的结果
                    conn = port.connections[0]
                    source_node = conn.start_port.parent_node
                    kwargs[param_name] = source_node.result
                else:
                    # 如果没有连接，检查是否有预设的参数值
                    if hasattr(node, 'param_values') and param_name in node.param_values:
                        kwargs[param_name] = node.param_values[param_name]
                    else:
                        kwargs[param_name] = None

            if kwargs:
                node.result = node.func(**kwargs)
            else:
                node.result = node.func()

        print("运行完成！")
        print("=" * 40)
        return True
    except Exception as e:
        print(f"运行出错: {e}")
        import traceback
        traceback.print_exc()
        return False