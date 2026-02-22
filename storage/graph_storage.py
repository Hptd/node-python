"""图表保存/加载"""

import json
from typing import Dict, List, Any
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
    
    # 导入 NodeGroup 类
    from ..core.graphics.node_group import NodeGroup
    from ..core.graphics.connection_item import ConnectionItem
    
    # 用于记录节点ID到节点对象的映射
    node_id_to_node = {}
    
    for item in scene_items:
        if isinstance(item, SimpleNodeItem):
            node_id_to_node[item.node_id] = item
            graph_data["nodes"].append({
                "id": item.node_id,
                "type": item.name,
                "x": item.x(),
                "y": item.y()
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


def import_graph_from_json(graph_data: Dict[str, Any], scene, create_node_func) -> List[SimpleNodeItem]:
    """从JSON导入图表"""
    created_nodes = []
    node_map = {}  # id -> node对象
    
    # 创建节点
    for node_data in graph_data.get("nodes", []):
        node_id = node_data.get("id")
        node_type = node_data.get("type")
        x = node_data.get("x", 0)
        y = node_data.get("y", 0)
        
        if node_type in LOCAL_NODE_LIBRARY:
            func = LOCAL_NODE_LIBRARY[node_type]
            node = create_node_func(node_type, func, x, y)
            node_map[node_id] = node
            created_nodes.append(node)
    
    # 创建连接
    for conn_data in graph_data.get("connections", []):
        from_node_id = conn_data.get("from_node")
        to_node_id = conn_data.get("to_node")
        from_port_name = conn_data.get("from_port")
        to_port_name = conn_data.get("to_port")
        
        if from_node_id in node_map and to_node_id in node_map:
            from_node = node_map[from_node_id]
            to_node = node_map[to_node_id]
            
            # 查找对应的端口
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
                # 创建连接
                from ..core.graphics.connection_item import ConnectionItem
                conn = ConnectionItem(from_port, to_port)
                scene.addItem(conn)
                conn.finalize_connection(to_port)
    
    # 创建节点组
    from ..core.graphics.node_group import NodeGroup
    for group_data in graph_data.get("groups", []):
        group_name = group_data.get("name", "组")
        node_ids = group_data.get("node_ids", [])
        
        # 获取组内的节点
        group_nodes = [node_map[nid] for nid in node_ids if nid in node_map]
        
        if group_nodes:
            group = NodeGroup(nodes=group_nodes, name=group_name)
            scene.addItem(group)
    
    return created_nodes