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
    """执行图表（使用批量执行引擎，只调用一次 python.exe）
    
    Args:
        nodes: 节点列表
        executor: 兼容旧接口，实际不再使用
    
    Returns:
        执行是否成功
    """
    from utils.console_stream import colored_print
    from .batch_executor import get_batch_executor
    
    colored_print("=" * 40, "system")
    colored_print("开始运行图表（批量执行模式）...", "info")
    
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

    # 将所有待执行节点标记为运行中状态（提供视觉反馈）
    for node in sorted_nodes:
        node.set_status(SimpleNodeItem.STATUS_RUNNING)

    # 强制刷新UI以确保状态更新立即显示
    from PySide6.QtWidgets import QApplication
    if QApplication.instance():
        QApplication.instance().processEvents()

    try:
        # 使用批量执行引擎
        batch_executor = get_batch_executor()
        success, results, logs = batch_executor.execute_graph(sorted_nodes)
        
        # 处理执行结果
        has_error = False
        
        if success:
            # 将结果应用到节点
            for idx, node in enumerate(sorted_nodes):
                result_key = f'node_{idx}'
                if result_key in results:
                    result_data = results[result_key]
                    if result_data.get('success'):
                        node.result = result_data.get('result')
                        node.set_status(SimpleNodeItem.STATUS_SUCCESS)
                        if node.result is not None:
                            colored_print(f"  节点 '{node.name}' 结果: {node.result}", "success")
                        else:
                            colored_print(f"  节点 '{node.name}' 执行完成", "success")
                    else:
                        error_msg = result_data.get('error', '未知错误')
                        node.set_status(SimpleNodeItem.STATUS_ERROR, error_msg)
                        colored_print(f"  ❌ 节点 '{node.name}' 执行出错: {error_msg}", "error")
                        has_error = True
                else:
                    colored_print(f"  ⚠ 节点 '{node.name}' 没有返回结果", "warning")
            
            # 输出日志
            if logs:
                colored_print("\n执行日志:", "info")
                for line in logs.split('\n'):
                    if line.strip():
                        colored_print(f"  {line}", "debug")
        else:
            # 执行失败
            has_error = True
            colored_print(f"\n{'='*50}", "error")
            colored_print("❌ 图表执行失败", "error")
            colored_print(f"{'='*50}", "error")
            colored_print(logs, "error")
            
            # 将所有节点标记为错误状态
            for node in sorted_nodes:
                node.set_status(SimpleNodeItem.STATUS_ERROR, "批量执行失败")

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