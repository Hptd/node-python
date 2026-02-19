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
    use_embedded: bool = False,
    executor = None
) -> bool:
    """执行图表
    
    Args:
        nodes: 节点列表
        use_embedded: 是否使用嵌入式 Python 执行（用于自定义节点）
        executor: 嵌入式执行器实例（use_embedded=True 时必需）
    
    Returns:
        执行是否成功
    """
    print("=" * 40)
    print("开始运行图表...")
    
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

            # 执行节点
            if use_embedded and hasattr(node, 'is_custom_node') and node.is_custom_node:
                # 使用嵌入式 Python 执行（自定义节点）
                if executor is None:
                    raise RuntimeError("使用嵌入式执行时需要提供 executor 实例")
                
                # 获取节点源代码
                if not hasattr(node, 'source_code') or not node.source_code:
                    raise RuntimeError(f"自定义节点 {node.name} 没有源代码")
                
                # 提取导入的模块
                from utils.sandbox import extract_imports
                imports = extract_imports(node.source_code)
                print(f"  检测到的导入: {imports}")
                
                # 执行
                node.result = executor.execute_node(
                    func_code=node.source_code,
                    args=kwargs,
                    imports=imports,
                    timeout=30
                )
                print(f"  结果: {node.result}")
                
            else:
                # 本地执行（内置节点）
                if kwargs:
                    node.result = node.func(**kwargs)
                else:
                    node.result = node.func()
                print(f"  结果: {node.result}")

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
    适用于需要执行自定义节点的场景。
    """
    from .embedded_executor import get_executor
    
    try:
        executor = get_executor()
        return execute_graph(nodes, use_embedded=True, executor=executor)
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
        环境信息字典
    """
    info = {
        "local_python": True,
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
    print("执行引擎测试")
    print("-" * 40)
    
    env_info = check_execution_environment()
    print("环境检查:")
    print(f"  本地 Python: {'✓' if env_info['local_python'] else '✗'}")
    print(f"  嵌入式 Python: {'✓' if env_info['embedded_python'] else '✗'}")
    
    if env_info['embedded_info']:
        print(f"  Python 版本: {env_info['embedded_info'].get('python_version', '未知')}")
        print(f"  已安装包数: {env_info['embedded_info'].get('installed_packages_count', 0)}")
    
    if env_info['error']:
        print(f"  错误: {env_info['error']}")