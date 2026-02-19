"""自定义节点持久化存储"""

import os
import json
import inspect
import ast
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from core.nodes.node_library import (NODE_LIBRARY_CATEGORIZED, LOCAL_NODE_LIBRARY,
                                      CUSTOM_CATEGORIES, add_node_to_library)
from utils.constants import STORAGE_DIR, CUSTOM_NODES_FILE


def get_storage_path() -> Path:
    """获取存储路径"""
    # 优先使用用户数据目录
    if hasattr(sys, '_MEIPASS'):  # PyInstaller打包后的环境
        # 打包后使用应用所在目录
        base_dir = Path(sys.executable).parent
    else:
        # 开发环境使用项目目录
        base_dir = Path.cwd()
    
    storage_dir = base_dir / STORAGE_DIR
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir / CUSTOM_NODES_FILE


def save_custom_nodes() -> bool:
    """保存自定义节点到文件"""
    try:
        custom_nodes_data = []
        
        # 收集所有自定义节点
        for category in CUSTOM_CATEGORIES:
            if category in NODE_LIBRARY_CATEGORIZED:
                for name, func in NODE_LIBRARY_CATEGORIZED[category].items():
                    # 获取源代码
                    source = getattr(func, '_custom_source', None)
                    if source is None:
                        try:
                            source = inspect.getsource(func)
                        except Exception:
                            source = ""
                    
                    # 获取函数签名信息
                    sig = inspect.signature(func)
                    params = list(sig.parameters.keys())
                    return_type = str(sig.return_annotation) if sig.return_annotation != inspect.Parameter.empty else ""
                    
                    node_data = {
                        "name": name,
                        "category": category,
                        "source_code": source,
                        "parameters": params,
                        "return_type": return_type,
                        "docstring": inspect.getdoc(func) or "",
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                    custom_nodes_data.append(node_data)
        
        # 保存到文件
        storage_file = get_storage_path()
        with open(storage_file, 'w', encoding='utf-8') as f:
            json.dump(custom_nodes_data, f, ensure_ascii=False, indent=2)
        
        print(f"已保存 {len(custom_nodes_data)} 个自定义节点到: {storage_file}")
        return True
        
    except Exception as e:
        print(f"保存自定义节点失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_custom_nodes() -> bool:
    """从文件加载自定义节点"""
    try:
        storage_file = get_storage_path()
        if not storage_file.exists():
            print("未找到自定义节点存储文件，跳过加载")
            return True
        
        with open(storage_file, 'r', encoding='utf-8') as f:
            custom_nodes_data = json.load(f)
        
        loaded_count = 0
        for node_data in custom_nodes_data:
            try:
                name = node_data["name"]
                category = node_data["category"]
                source_code = node_data["source_code"]
                
                # 检查节点是否已存在
                if name in LOCAL_NODE_LIBRARY:
                    print(f"节点 '{name}' 已存在，跳过加载")
                    continue
                
                # 验证和编译源代码
                tree = ast.parse(source_code)
                func_defs = [node for node in ast.iter_child_nodes(tree) if isinstance(node, ast.FunctionDef)]
                if len(func_defs) != 1:
                    print(f"节点 '{name}' 源代码无效: 必须定义且仅定义一个函数")
                    continue
                
                func_name = func_defs[0].name
                
                # 编译执行
                namespace = {}
                exec(compile(tree, f"<custom_node_{name}>", "exec"), namespace)
                func = namespace[func_name]
                
                if not callable(func):
                    print(f"节点 '{name}' 不是可调用函数")
                    continue
                
                # 保存源代码到函数属性
                func._custom_source = source_code
                
                # 添加到库中
                add_node_to_library(name, func, category)
                loaded_count += 1
                print(f"已加载自定义节点: {name} ({category})")
                
            except Exception as e:
                print(f"加载节点 '{node_data.get('name', '未知')}' 失败: {e}")
        
        print(f"成功加载 {loaded_count} 个自定义节点")
        return True
        
    except Exception as e:
        print(f"加载自定义节点失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def delete_custom_node(name: str) -> bool:
    """删除自定义节点"""
    from core.nodes.node_library import remove_node_from_library
    
    if remove_node_from_library(name):
        # 重新保存所有自定义节点
        return save_custom_nodes()
    return False


def get_custom_nodes_info() -> List[Dict[str, Any]]:
    """获取所有自定义节点信息"""
    info = []
    for category in CUSTOM_CATEGORIES:
        if category in NODE_LIBRARY_CATEGORIZED:
            for name, func in NODE_LIBRARY_CATEGORIZED[category].items():
                info.append({
                    "name": name,
                    "category": category,
                    "docstring": inspect.getdoc(func) or "",
                    "parameters": list(inspect.signature(func).parameters.keys()),
                    "has_return": inspect.signature(func).return_annotation != inspect.Parameter.empty
                })
    return info


def clear_all_custom_nodes() -> bool:
    """清除所有自定义节点"""
    from core.nodes.node_library import clear_custom_nodes
    
    clear_custom_nodes()
    
    # 删除存储文件
    try:
        storage_file = get_storage_path()
        if storage_file.exists():
            storage_file.unlink()
            print("已删除自定义节点存储文件")
        return True
    except Exception as e:
        print(f"删除存储文件失败: {e}")
        return False