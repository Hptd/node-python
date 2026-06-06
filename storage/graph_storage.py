"""图表保存/加载"""

import json
from typing import Dict, List, Any, Callable, Optional
from pathlib import Path

from ..core.nodes.node_library import LOCAL_NODE_LIBRARY
from ..core.graphics.simple_node_item import SimpleNodeItem


def save_graph_to_file(graph_data: Dict[str, Any], filepath: str) -> bool:
    """保存图表到文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        print(f"图表已保存到: {filepath}")
        return True
    except Exception as e:
        print(f"保存图表失败: {e}")
        return False


def load_graph_from_file(filepath: str) -> Dict[str, Any]:
    """从文件加载图表"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        print(f"已从文件加载图表: {filepath}")
        return graph_data
    except Exception as e:
        print(f"加载图表失败: {e}")
        return {"nodes": [], "connections": [], "groups": []}


def export_graph_to_json(scene_items: List) -> Dict[str, Any]:
    """导出图表为JSON格式"""
    graph_data = {"nodes": [], "connections": [], "groups": []}

    from ..core.graphics.node_group import NodeGroup
    from ..core.graphics.connection_item import ConnectionItem
    from ..core.graphics.loop_node_item import LoopNodeItem
    from ..core.graphics.multithread_node_item import MultithreadNodeItem

    node_id_to_node = {}

    for item in scene_items:
        if isinstance(item, SimpleNodeItem):
            node_id_to_node[item.node_id] = item
            node_data = {
                "id": item.node_id,
                "type": item.name,
                "x": item.x(),
                "y": item.y()
            }
            if item.param_values:
                node_data["param_values"] = item.param_values
            graph_data["nodes"].append(node_data)
        elif isinstance(item, LoopNodeItem):
            node_id_to_node[item.node_id] = item
            loop_data = {
                "id": item.node_id,
                "type": "RangeLoop" if item.loop_type == LoopNodeItem.LOOP_TYPE_RANGE else "ListLoop",
                "x": item.x(),
                "y": item.y(),
                "loop_name": item.loop_name,
                "loop_type": item.loop_type
            }
            if item.loop_type == LoopNodeItem.LOOP_TYPE_RANGE:
                loop_data["range_start"] = item.range_start
                loop_data["range_end"] = item.range_end
                loop_data["range_step"] = item.range_step
            else:
                loop_data["list_data"] = item.list_data
            graph_data["nodes"].append(loop_data)
        elif isinstance(item, MultithreadNodeItem):
            node_id_to_node[item.node_id] = item
            graph_data["nodes"].append({
                "id": item.node_id,
                "type": "Multithread",
                "x": item.x(),
                "y": item.y(),
                "input_list": item.input_list,
                "thread_count": item.thread_count,
                "return_order": item.return_order
            })
        elif isinstance(item, ConnectionItem):
            if item.end_port:
                graph_data["connections"].append({
                    "from_node": item.start_port.parent_node.node_id,
                    "from_port": item.start_port.port_name,
                    "to_node": item.end_port.parent_node.node_id,
                    "to_port": item.end_port.port_name
                })
        elif isinstance(item, NodeGroup):
            group_data = {
                "name": item.group_name,
                "node_ids": [node.node_id for node in item.nodes]
            }
            graph_data["groups"].append(group_data)

    return graph_data


def import_graph_from_json(
    graph_data: Dict[str, Any],
    scene,
    create_node_func: Callable,
    create_loop_node_func: Optional[Callable] = None,
    create_multithread_node_func: Optional[Callable] = None
) -> List[SimpleNodeItem]:
    """从JSON导入图表"""
    created_nodes = []
    node_map = {}  # id -> node对象

    from ..core.graphics.node_group import NodeGroup

    # 创建节点
    for node_data in graph_data.get("nodes", []):
        node_id = node_data.get("id")
        node_type = node_data.get("type")
        x = node_data.get("x", 0)
        y = node_data.get("y", 0)
        param_values = node_data.get("param_values", {})

        if node_type in ("RangeLoop", "ListLoop"):
            if create_loop_node_func:
                node = create_loop_node_func(
                    loop_type=node_data.get("loop_type", "range"),
                    x=x, y=y,
                    loop_name=node_data.get("loop_name", "循环"),
                    range_start=node_data.get("range_start", 0),
                    range_end=node_data.get("range_end", 10),
                    range_step=node_data.get("range_step", 1),
                    list_data=node_data.get("list_data", "[]")
                )
                node_map[node_id] = node
                created_nodes.append(node)
        elif node_type == "Multithread":
            if create_multithread_node_func:
                node = create_multithread_node_func(
                    x=x, y=y,
                    input_list=node_data.get("input_list", "[]"),
                    thread_count=node_data.get("thread_count", 4),
                    return_order=node_data.get("return_order", "按输入顺序")
                )
                node_map[node_id] = node
                created_nodes.append(node)
        elif node_type in LOCAL_NODE_LIBRARY:
            func = LOCAL_NODE_LIBRARY[node_type]
            node = create_node_func(node_type, func, x, y)
            node_map[node_id] = node
            created_nodes.append(node)
            # 恢复参数值
            if param_values:
                node.param_values.update(param_values)

    # 创建连接
    for conn_data in graph_data.get("connections", []):
        from_node_id = conn_data.get("from_node")
        to_node_id = conn_data.get("to_node")
        from_port_name = conn_data.get("from_port")
        to_port_name = conn_data.get("to_port")

        if from_node_id in node_map and to_node_id in node_map:
            from_node = node_map[from_node_id]
            to_node = node_map[to_node_id]

            from_port = None
            to_port = None

            for port in from_node.output_ports:
                if port.port_name == from_port_name:
                    from_port = port
                    break

            for port in to_node.input_ports:
                if port.port_name == to_port_name:
                    to_port = port
                    break

            if from_port and to_port:
                from ..core.graphics.connection_item import ConnectionItem
                conn = ConnectionItem(from_port, to_port)
                scene.addItem(conn)
                conn.finalize_connection(to_port)

    # 创建节点组
    for group_data in graph_data.get("groups", []):
        group_name = group_data.get("name", "组")
        node_ids = group_data.get("node_ids", [])

        group_nodes = [node_map[nid] for nid in node_ids if nid in node_map]

        if group_nodes:
            group = NodeGroup(nodes=group_nodes, name=group_name)
            scene.addItem(group)

    return created_nodes
