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
    from utils.console_stream import colored_print
    
    colored_print("=" * 40, "system")
    colored_print("开始运行图表（统一使用嵌入式 Python 环境）...", "info")
    
    if not nodes:
        colored_print("没有节点可执行。", "warning")
        return False

    # 重置所有节点状态和结果
    for node in nodes:
        node.result = None
        node.reset_status()

    # 拓扑排序
    sorted_nodes = topological_sort(nodes)
    colored_print(f"执行顺序: {[n.name for n in sorted_nodes]}", "debug")

    has_error = False
    
    try:
        for node in sorted_nodes:
            # 设置节点为运行状态
            node.set_status(SimpleNodeItem.STATUS_RUNNING)
            colored_print(f"\n执行节点: {node.name}", "info")
            
            # 强制刷新UI
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            # 收集参数
            kwargs = {}
            for port in node.input_ports:
                param_name = port.port_name
                
                if port.connections:
                    # 如果有连接，使用连接节点的结果
                    conn = port.connections[0]
                    source_node = conn.start_port.parent_node
                    kwargs[param_name] = source_node.result
                    colored_print(f"  参数 {param_name}: 来自节点 {source_node.name} = {source_node.result}", "debug")
                else:
                    # 如果没有连接，检查是否有预设的参数值
                    if hasattr(node, 'param_values') and param_name in node.param_values:
                        kwargs[param_name] = node.param_values[param_name]
                        colored_print(f"  参数 {param_name}: 预设值 = {node.param_values[param_name]}", "debug")
                    else:
                        kwargs[param_name] = None
                        colored_print(f"  参数 {param_name}: 无值 (None)", "warning")

            # 执行节点（统一使用嵌入式 Python 环境）
            if executor is None:
                raise RuntimeError("需要提供嵌入式 Python 执行器实例")
            
            try:
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
                        "打印节点": '''def node_print(data):
    """
    打印输出节点。
    将输入的数据打印到下方的控制台中。
    """
    print(f"执行结果: {data}")''',
                        "字符串": '''def const_string(value: str = "") -> str:
    """
    字符串常量节点。
    返回一个字符串值。
    """
    return value''',
                        "整数": '''def const_int(value: int = 0) -> int:
    """
    整数常量节点。
    返回一个整数值。
    """
    return value''',
                        "浮点数": '''def const_float(value: float = 0.0) -> float:
    """
    浮点数常量节点。
    返回一个浮点数值。
    """
    return value''',
                        "布尔": '''def const_bool(value: bool = True) -> bool:
    """
    布尔常量节点。
    返回一个布尔值。
    """
    return value''',
                        "列表": '''def const_list(value: list = None) -> list:
    """
    列表常量节点。
    返回一个列表值。
    """
    if value is None:
        return []
    return value''',
                        "字典": '''def const_dict(value: dict = None) -> dict:
    """
    字典常量节点。
    返回一个字典值。
    """
    if value is None:
        return {}
    return value''',
                        "数据提取": '''def extract_data(data: dict, path: str = "") -> any:
    """
    数据提取节点。
    从输入的结构化数据（字典/JSON）中提取指定路径的字段内容。
    """
    if not data or not path:
        return None
    
    if isinstance(data, dict):
        try:
            keys = path.split('.')
            current = data
            for key in keys:
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, list) and key.isdigit():
                    idx = int(key)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                else:
                    return None
                if current is None:
                    return None
            return current
        except Exception:
            return None
    return None''',
                        "数据类型检测": '''def type_test(data) -> None:
    """
    数据类型检测节点。
    检测并打印输入数据的类型信息。
    """
    print(f"输入数据类型为：{type(data)}")'''
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
                colored_print(f"  检测到的导入: {imports}", "debug")
                
                # 在嵌入式环境中执行
                node.result = executor.execute_node(
                    func_code=func_code,
                    args=kwargs,
                    imports=imports,
                    timeout=30
                )
                
                # 执行成功，设置节点状态
                node.set_status(SimpleNodeItem.STATUS_SUCCESS)
                
                # 只有当结果不是None时才显示结果，避免冗余输出
                if node.result is not None:
                    colored_print(f"  结果: {node.result}", "success")
                else:
                    # 对于返回None的节点（如打印节点），只显示节点执行完成
                    colored_print(f"  节点执行完成", "success")
                    
            except Exception as e:
                # 执行出错，设置节点错误状态
                error_msg = str(e)
                node.set_status(SimpleNodeItem.STATUS_ERROR, error_msg)
                colored_print(f"\n节点 '{node.name}' 执行出错: {error_msg}", "error")
                has_error = True
                
                # 继续执行其他节点（或可以选择中断）
                import traceback
                colored_print(traceback.format_exc(), "error")
                continue

        colored_print("\n" + "=" * 40, "system")
        if has_error:
            colored_print("运行完成（有错误）", "warning")
        else:
            colored_print("运行完成！", "success")
        colored_print("=" * 40, "system")
        return not has_error
        
    except Exception as e:
        colored_print(f"\n运行出错: {e}", "error")
        import traceback
        colored_print(traceback.format_exc(), "error")
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