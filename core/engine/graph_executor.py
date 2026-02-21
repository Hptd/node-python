"""图表执行引擎

支持两种执行模式：
1. 本地执行：直接在当前进程中调用函数（用于内置节点）
2. 嵌入式执行：在独立的 Python 进程中执行（用于自定义节点，支持第三方库）
"""

from typing import List, Dict, Any, Optional
from ..graphics.simple_node_item import SimpleNodeItem


def topological_sort(nodes: List[SimpleNodeItem]) -> List[SimpleNodeItem]:
    """拓扑排序
    
    根据节点连接关系计算执行顺序，确保依赖节点先执行。
    """
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


def execute_graph(
    nodes: List[SimpleNodeItem],
    executor = None
) -> bool:
    """执行图表（统一使用嵌入式 Python 环境）
    
    Args:
        nodes: 节点列表
        executor: 嵌入式执行器实例（必需）
    
    Returns:
        执行是否成功
    """
    print("=" * 40)
    print("开始运行图表（统一使用嵌入式 Python 环境）...")
    
    if not nodes:
        print("没有节点可执行。")
        return False

    # 重置所有节点结果
    for node in nodes:
        node.result = None

    # 拓扑排序
    sorted_nodes = topological_sort(nodes)
    print(f"执行顺序: {[n.name for n in sorted_nodes]}")

    try:
        for node in sorted_nodes:
            print(f"\n执行节点: {node.name}")
            
            # 收集参数
            kwargs = {}
            for port in node.input_ports:
                param_name = port.port_name
                
                if port.connections:
                    # 如果有连接，使用连接节点的结果
                    conn = port.connections[0]
                    source_node = conn.start_port.parent_node
                    kwargs[param_name] = source_node.result
                    print(f"  参数 {param_name}: 来自节点 {source_node.name} = {source_node.result}")
                else:
                    # 如果没有连接，检查是否有预设的参数值
                    if hasattr(node, 'param_values') and param_name in node.param_values:
                        kwargs[param_name] = node.param_values[param_name]
                        print(f"  参数 {param_name}: 预设值 = {node.param_values[param_name]}")
                    else:
                        kwargs[param_name] = None
                        print(f"  参数 {param_name}: 无值 (None)")

            # 执行节点（统一使用嵌入式 Python 环境）
            if executor is None:
                raise RuntimeError("需要提供嵌入式 Python 执行器实例")
            
            # 对于内置节点，需要获取其函数代码
            if hasattr(node, 'is_custom_node') and node.is_custom_node:
                # 自定义节点：使用存储的源代码
                if not hasattr(node, 'source_code') or not node.source_code:
                    raise RuntimeError(f"自定义节点 {node.name} 没有源代码")
                
                func_code = node.source_code
            else:
                            # 内置节点：获取函数源代码
                            if not hasattr(node, 'func'):
                                raise RuntimeError(f"节点 {node.name} 没有可执行函数")
                            
                            # 内置节点的预定义源代码
                            BUILTIN_NODE_SOURCE = {
                                "打印节点": "def node_print(data):\n    \"\"\"\n    打印输出节点。\n    将输入的数据打印到下方的控制台中。\n    \"\"\"\n    print(f\"执行结果: {data}\")",
                                "字符串": "def const_string(value: str = \"\") -> str:\n    \"\"\"\n    字符串常量节点。\n    返回一个字符串值。\n    \"\"\"\n    return value",
                                "整数": "def const_int(value: int = 0) -> int:\n    \"\"\"\n    整数常量节点。\n    返回一个整数值。\n    \"\"\"\n    return value",
                                "浮点数": "def const_float(value: float = 0.0) -> float:\n    \"\"\"\n    浮点数常量节点。\n    返回一个浮点数值。\n    \"\"\"\n    return value",
                                "布尔": "def const_bool(value: bool = True) -> bool:\n    \"\"\"\n    布尔常量节点。\n    返回一个布尔值。\n    \"\"\"\n    return value",
                                "列表": "def const_list(value: list = None) -> list:\n    \"\"\"\n    列表常量节点。\n    返回一个列表值。\n    \"\"\"\n    if value is None:\n        return []\n    return value",
                                "字典": "def const_dict(value: dict = None) -> dict:\n    \"\"\"\n    字典常量节点。\n    返回一个字典值。\n    \"\"\"\n    if value is None:\n        return {}\n    return value",
                                "数据提取": "def extract_data(data: dict, path: str = \"\") -> any:\n    \"\"\"\n    数据提取节点。\n    从输入的结构化数据（字典/JSON）中提取指定路径的字段内容。\n    \"\"\"\n    if not data or not path:\n        return None\n    \n    # 简化实现\n    if isinstance(data, dict):\n        try:\n            keys = path.split('.')\n            current = data\n            for key in keys:\n                if isinstance(current, dict):\n                    current = current.get(key)\n                elif isinstance(current, list) and key.isdigit():\n                    idx = int(key)\n                    if 0 <= idx < len(current):\n                        current = current[idx]\n                    else:\n                        return None\n                else:\n                    return None\n                if current is None:\n                    return None\n            return current\n        except Exception:\n            return None\n    return None",
                                "数据类型检测": "def type_test(data) -> None:\n    \"\"\"\n    数据类型检测节点。\n    检测并打印输入数据的类型信息。\n    \"\"\"\n    print(f\"输入数据类型为：{type(data)}\")"
                            }
                            
                            # 尝试从预定义源代码字典中获取
                            func_name = node.name
                            if func_name in BUILTIN_NODE_SOURCE:
                                func_code = BUILTIN_NODE_SOURCE[func_name]
                            else:
                                # 如果找不到，尝试使用 inspect.getsource
                                try:
                                    import inspect
                                    func_code = inspect.getsource(node.func)
                                except Exception as e:
                                    raise RuntimeError(f"无法获取节点 {func_name} 的源代码: {e}")            
            # 提取导入的模块
            from utils.sandbox import extract_imports
            imports = extract_imports(func_code)
            print(f"  检测到的导入: {imports}")
            
            # 在嵌入式环境中执行
            node.result = executor.execute_node(
                func_code=func_code,
                args=kwargs,
                imports=imports,
                timeout=30
            )
            
            # 只有当结果不是None时才显示结果，避免冗余输出
            if node.result is not None:
                print(f"  结果: {node.result}")
            else:
                # 对于返回None的节点（如打印节点），只显示节点执行完成
                print(f"  节点执行完成")
                
            # 如果是打印节点，需要将输出显示到控制台
            if node.name == "打印节点":
                # 打印节点的输出已经被包含在嵌入式环境的stdout中
                # 这里不需要额外处理，因为execute_node会捕获输出
                pass

        print("\n" + "=" * 40)
        print("运行完成！")
        print("=" * 40)
        return True
        
    except Exception as e:
        print(f"\n运行出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def execute_graph_embedded(nodes: List[SimpleNodeItem]) -> bool:
    """使用嵌入式 Python 执行图表
    
    这是 execute_graph 的便捷封装，自动创建执行器。
    统一使用嵌入式 Python 环境执行所有节点。
    """
    from .embedded_executor import get_executor
    
    try:
        executor = get_executor()
        return execute_graph(nodes, executor=executor)
    except RuntimeError as e:
        print(f"嵌入式执行器初始化失败: {e}")
        print("提示: 请运行 'python -m utils.setup_embedded_python install' 初始化环境")
        return False
    except Exception as e:
        print(f"执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_execution_environment() -> Dict[str, Any]:
    """检查执行环境状态
    
    Returns:
        环境信息字典（只检查嵌入式 Python 环境）
    """
    info = {
        "embedded_python": False,
        "embedded_info": None,
        "error": None
    }
    
    # 检查嵌入式 Python
    try:
        from .embedded_executor import EmbeddedPythonExecutor
        executor = EmbeddedPythonExecutor()
        info["embedded_python"] = True
        info["embedded_info"] = executor.get_environment_info()
    except RuntimeError as e:
        info["error"] = str(e)
    except Exception as e:
        info["error"] = f"检查失败: {e}"
    
    return info


if __name__ == '__main__':
    # 测试
    print("执行引擎测试（统一使用嵌入式 Python 环境）")
    print("-" * 40)
    
    env_info = check_execution_environment()
    print("环境检查:")
    print(f"  嵌入式 Python: {'✓' if env_info['embedded_python'] else '✗'}")
    
    if env_info['embedded_info']:
        print(f"  Python 版本: {env_info['embedded_info'].get('python_version', '未知')}")
        print(f"  已安装包数: {env_info['embedded_info'].get('installed_packages_count', 0)}")
    
    if env_info['error']:
        print(f"  错误: {env_info['error']}")