"""节点库管理模块"""

import inspect
from typing import Dict, Any

# 导入基础节点
from .base_nodes import (node_add, node_print, NODE_CODE_EXAMPLE,
                         const_bool, const_int, const_float, const_string,
                         const_list, const_dict)

# ==========================================
# 节点库：分类 -> {节点名: 函数}
# ==========================================
NODE_LIBRARY_CATEGORIZED = {
    "基础运算": {
        "加法节点": node_add,
    },
    "输出": {
        "打印节点": node_print,
    },
    "常量": {
        "布尔": const_bool,
        "整数": const_int,
        "浮点数": const_float,
        "字符串": const_string,
        "列表": const_list,
        "字典": const_dict,
    },
}

# 扁平索引，方便查找
LOCAL_NODE_LIBRARY = {}
for cat, nodes in NODE_LIBRARY_CATEGORIZED.items():
    LOCAL_NODE_LIBRARY.update(nodes)

# 用户自定义分类列表
CUSTOM_CATEGORIES = []


def add_node_to_library(name: str, func: Any, category: str) -> None:
    """将节点添加到分类库和扁平索引"""
    if category not in NODE_LIBRARY_CATEGORIZED:
        NODE_LIBRARY_CATEGORIZED[category] = {}
        if category not in CUSTOM_CATEGORIES:
            CUSTOM_CATEGORIES.append(category)
    NODE_LIBRARY_CATEGORIZED[category][name] = func
    LOCAL_NODE_LIBRARY[name] = func


def get_node_function(name: str):
    """获取节点函数"""
    return LOCAL_NODE_LIBRARY.get(name)


def get_all_categories() -> list:
    """获取所有分类"""
    return list(NODE_LIBRARY_CATEGORIZED.keys())


def get_nodes_in_category(category: str) -> Dict[str, Any]:
    """获取指定分类下的所有节点"""
    return NODE_LIBRARY_CATEGORIZED.get(category, {})


def remove_node_from_library(name: str) -> bool:
    """从库中移除节点"""
    if name not in LOCAL_NODE_LIBRARY:
        return False
    
    # 从扁平索引中移除
    LOCAL_NODE_LIBRARY.pop(name)
    
    # 从分类库中移除
    for category, nodes in NODE_LIBRARY_CATEGORIZED.items():
        if name in nodes:
            nodes.pop(name)
            # 如果分类为空，移除分类
            if not nodes:
                NODE_LIBRARY_CATEGORIZED.pop(category)
                if category in CUSTOM_CATEGORIES:
                    CUSTOM_CATEGORIES.remove(category)
            break
    
    return True


def clear_custom_nodes() -> None:
    """清除所有自定义节点"""
    global LOCAL_NODE_LIBRARY, NODE_LIBRARY_CATEGORIZED, CUSTOM_CATEGORIES
    
    # 备份系统节点
    system_nodes = {}
    system_categories = {}
    for cat, nodes in NODE_LIBRARY_CATEGORIZED.items():
        if cat not in CUSTOM_CATEGORIES:
            system_categories[cat] = nodes.copy()
            for name, func in nodes.items():
                system_nodes[name] = func
    
    # 重置为系统节点
    NODE_LIBRARY_CATEGORIZED = system_categories
    LOCAL_NODE_LIBRARY = system_nodes
    CUSTOM_CATEGORIES = []