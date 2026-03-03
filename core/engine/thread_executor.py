"""多线程执行引擎

使用 ThreadPoolExecutor 并行执行节点链。
每个线程运行一个独立子进程，天然线程安全。
"""

import json
import inspect
import re
import os
import tempfile
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Any, Set, Tuple

from ..graphics.simple_node_item import SimpleNodeItem
from ..graphics.multithread_node_item import MultithreadNodeItem
from .graph_executor import topological_sort

_print_lock = threading.Lock()


def _safe_print(msg: str, level: str = "info"):
    with _print_lock:
        from utils.console_stream import colored_print
        colored_print(msg, level)


# ──────────────────────────────────────────────
# 辅助：查找连接到多线程节点的节点
# ──────────────────────────────────────────────

def _get_nodes_connected_to_thread_node(
    thread_node: MultithreadNodeItem,
    all_nodes: List[SimpleNodeItem]
) -> Tuple[List[SimpleNodeItem], List[SimpleNodeItem]]:
    """返回 (iteration_nodes, result_nodes)"""

    direct_iter = set()
    direct_result = set()

    for node in all_nodes:
        if not isinstance(node, SimpleNodeItem):
            continue
        for port in node.input_ports:
            for conn in port.connections:
                if conn.start_port and conn.start_port.parent_node == thread_node:
                    pname = conn.start_port.port_name
                    if pname == '迭代值':
                        direct_iter.add(node)
                    elif pname == '汇总结果':
                        direct_result.add(node)

    def downstream(starts: Set[SimpleNodeItem]) -> Set[SimpleNodeItem]:
        result = set(starts)
        queue = list(starts)
        while queue:
            cur = queue.pop(0)
            for node in all_nodes:
                if not isinstance(node, SimpleNodeItem) or node in result:
                    continue
                for port in node.input_ports:
                    for conn in port.connections:
                        if conn.start_port and conn.start_port.parent_node == cur:
                            result.add(node)
                            queue.append(node)
                            break

        return result

    def upstream(nodes: Set[SimpleNodeItem]) -> Set[SimpleNodeItem]:
        result = set(nodes)
        queue = list(nodes)
        visited = set()
        while queue:
            cur = queue.pop(0)
            if id(cur) in visited:
                continue
            visited.add(id(cur))
            for port in cur.input_ports:
                for conn in port.connections:
                    if conn.start_port:
                        src = conn.start_port.parent_node
                        if isinstance(src, SimpleNodeItem) and src != thread_node and src not in result:
                            result.add(src)
                            queue.append(src)
        return result

    iter_nodes = upstream(downstream(direct_iter))
    res_nodes = upstream(downstream(direct_result))
    return list(iter_nodes), list(res_nodes)


# ──────────────────────────────────────────────
# 辅助：代码提取
# ──────────────────────────────────────────────

def _extract_imports(code: str) -> List[str]:
    imports = []
    imports.extend(re.findall(r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)', code, re.MULTILINE))
    imports.extend(re.findall(r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)', code, re.MULTILINE))
    return list(set(imports))


def _extract_func_name(code: str) -> str:
    matches = re.findall(r'^def\s+([^\s(]+)\s*\(', code, re.MULTILINE)
    if not matches:
        raise ValueError("代码中未找到函数定义")
    return matches[0]


_BUILTIN_CODE = {
    "打印节点": 'def node_print(data):\n    print(data)\n    return data',
    "字符串": '''def const_string(value= "") -> str:
    """字符串常量节点。将任意输入转换为字符串值。"""
    from utils.type_converter import TypeConverter
    return TypeConverter.to_string(value)''',
    "整数": '''def const_int(value= 0) -> int:
    """整数常量节点。将任意输入转换为整数值。"""
    from utils.type_converter import TypeConverter
    return TypeConverter.to_int(value)''',
    "浮点数": '''def const_float(value= 0.0) -> float:
    """浮点数常量节点。将任意输入转换为浮点数值。"""
    from utils.type_converter import TypeConverter
    return TypeConverter.to_float(value)''',
    "布尔": '''def const_bool(value= True) -> bool:
    """布尔常量节点。将任意输入转换为布尔值。"""
    from utils.type_converter import TypeConverter
    return TypeConverter.to_bool(value)''',
    "列表": '''def const_list(value= None) -> list:
    """列表常量节点。将任意输入转换为列表值。"""
    from utils.type_converter import TypeConverter
    return TypeConverter.to_list(value)''',
    "字典": '''def const_dict(value= None) -> dict:
    """字典常量节点。将任意输入转换为字典值。"""
    from utils.type_converter import TypeConverter
    return TypeConverter.to_dict(value)''',
}


def _get_node_source(node: SimpleNodeItem) -> str:
    if hasattr(node, 'is_custom_node') and node.is_custom_node:
        src = getattr(node.func, '_custom_source', None)
        if not src:
            src = inspect.getsource(node.func)
        return src
    # 内置节点
    src = _BUILTIN_CODE.get(node.name)
    if src:
        return src
    # 尝试从 _source 属性获取
    if hasattr(node.func, '_source'):
        return node.func._source
    try:
        return inspect.getsource(node.func)
    except Exception:
        return None


# ──────────────────────────────────────────────
# 脚本生成：单次迭代
# ──────────────────────────────────────────────

def _build_iteration_script(
    nodes_to_execute: List[SimpleNodeItem],
    iterator_value: Any,
    thread_node: MultithreadNodeItem,
) -> str:
    """为单个迭代值生成可独立运行的 Python 脚本"""

    all_imports: Set[str] = set()
    node_functions = []

    for idx, node in enumerate(nodes_to_execute):
        src = _get_node_source(node)
        if not src:
            continue
        all_imports.update(_extract_imports(src))
        try:
            func_name = _extract_func_name(src)
        except ValueError:
            continue
        node_functions.append({'node': node, 'func_name': func_name, 'source': src, 'idx': idx})

    # 构建每个节点的参数映射
    node_params = {}
    for node in nodes_to_execute:
        nk = f"node_{nodes_to_execute.index(node)}"
        params = {}
        for port in node.input_ports:
            found = False
            for conn in port.connections:
                if not conn.start_port:
                    continue
                src_node = conn.start_port.parent_node
                if src_node == thread_node and conn.start_port.port_name == '迭代值':
                    params[port.port_name] = '__ITER__'
                    found = True
                    break
                if isinstance(src_node, SimpleNodeItem) and src_node in nodes_to_execute:
                    si = nodes_to_execute.index(src_node)
                    params[port.port_name] = f'__RES_node_{si}__'
                    found = True
                    break
                if isinstance(src_node, SimpleNodeItem):
                    pv = src_node.param_values.get('value')
                    if pv is not None:
                        params[port.port_name] = pv
                        found = True
                        break
            if not found:
                params[port.port_name] = node.param_values.get(port.port_name)
        node_params[nk] = {
            'func_name': next((nf['func_name'] for nf in node_functions if nf['node'] == node), None),
            'params': params,
        }

    # 找结果节点：链尾节点（在 nodes_to_execute 内没有下游连接的节点）
    nodes_set = set(id(n) for n in nodes_to_execute)
    terminal_nodes = []
    for node in nodes_to_execute:
        has_downstream = False
        for port in node.output_ports:
            for conn in port.connections:
                if conn.end_port and id(conn.end_port.parent_node) in nodes_set:
                    has_downstream = True
                    break
            if has_downstream:
                break
        if not has_downstream:
            terminal_nodes.append(node)

    result_node_key = None
    if terminal_nodes:
        max_idx = max(nodes_to_execute.index(n) for n in terminal_nodes)
        result_node_key = f"node_{max_idx}"
    elif nodes_to_execute:
        result_node_key = f"node_{len(nodes_to_execute) - 1}"

    iter_json = json.dumps(iterator_value, ensure_ascii=False, default=str)

    lines = ["# -*- coding: utf-8 -*-", "import sys, json, os"]
    
    # 添加项目根目录到 sys.path（以便导入 utils 等模块）
    lines.append("# 添加项目根目录到路径")
    lines.append("python_exe_dir = os.path.dirname(os.path.abspath(sys.executable))")
    lines.append("possible_paths = [")
    lines.append("    os.environ.get('NODE_PYTHON_PROJECT_DIR', ''),")
    lines.append("    python_exe_dir,")
    lines.append("    os.path.dirname(python_exe_dir),")
    lines.append("]")
    lines.append("for path in possible_paths:")
    lines.append("    if path and os.path.isdir(path) and os.path.isdir(os.path.join(path, 'utils')):")
    lines.append("        sys.path.insert(0, path)")
    lines.append("        break")
    lines.append("")
    
    for imp in sorted(all_imports):
        lines.append(f"import {imp}")
    lines.append("")

    for nf in node_functions:
        lines.append(nf['source'])
        lines.append("")

    lines.append(f"iterator_value = json.loads({repr(iter_json)})")
    lines.append("_results = {}")
    lines.append("")

    for node in nodes_to_execute:
        nk = f"node_{nodes_to_execute.index(node)}"
        fn = node_params[nk]['func_name']
        if not fn:
            continue
        params = node_params[nk]['params']
        args = []
        for pname, pval in params.items():
            if pval == '__ITER__':
                args.append(f"{pname}=iterator_value")
            elif isinstance(pval, str) and pval.startswith('__RES_'):
                sk = pval[6:-2]  # strip __RES_ and __
                args.append(f"{pname}=_results.get('{sk}')")
            else:
                args.append(f"{pname}={repr(pval)}")
        args_str = ', '.join(args)
        lines.append(f"try:")
        lines.append(f"    _results['{nk}'] = {fn}({args_str})")
        lines.append(f"except Exception as _e:")
        lines.append(f"    import traceback")
        lines.append(f"    print(f'[节点错误] {nk} ({fn}): {{_e}}', file=__import__(\"sys\").stderr)")
        lines.append(f"    traceback.print_exc(file=__import__(\"sys\").stderr)")
        lines.append(f"    _results['{nk}'] = None")
        lines.append("")

    lines.append(f"_final = _results.get({repr(result_node_key)})")
    lines.append("print('__THREAD_RESULT_START__')")
    lines.append("print(json.dumps({'success': True, 'result': _final}, ensure_ascii=False, default=str))")
    lines.append("print('__THREAD_RESULT_END__')")

    return '\n'.join(lines)


# ──────────────────────────────────────────────
# 运行脚本子进程
# ──────────────────────────────────────────────

def _run_script(script: str, python_exe: str, timeout: int = 300) -> Any:
    """在子进程中运行脚本，返回结果值"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(script)
        path = f.name
    try:
        proc = subprocess.run(
            [python_exe, path],
            capture_output=True, text=True,
            timeout=timeout, encoding='utf-8', errors='replace',
            cwd=str(Path(python_exe).parent)
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)

        # 即使成功，也打印 stderr（节点内部错误信息）
        if proc.stderr and proc.stderr.strip():
            _safe_print(f"[子进程警告/错误]\n{proc.stderr.strip()}", "warning")

        stdout = proc.stdout
        s = stdout.find('__THREAD_RESULT_START__')
        e = stdout.find('__THREAD_RESULT_END__')
        if s == -1 or e == -1:
            raise RuntimeError(f"未找到结果标记，输出：{stdout[:200]}")

        data = json.loads(stdout[s + len('__THREAD_RESULT_START__'):e].strip())
        if data.get('success'):
            return data.get('result')
        raise RuntimeError(data.get('error', '未知错误'))
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


# ──────────────────────────────────────────────
# 执行结果节点
# ──────────────────────────────────────────────

def _execute_result_nodes(
    result_nodes: List[SimpleNodeItem],
    thread_node: MultithreadNodeItem,
    all_nodes: List[SimpleNodeItem],
):
    from utils.console_stream import colored_print
    from .loop_executor import _execute_node  # 复用循环执行器的单节点执行逻辑

    for node in result_nodes:
        try:
            colored_print(f"  执行汇总结果节点：{node.name}", "debug")
            # 为连接到"汇总结果"端口的节点注入汇总结果
            for port in node.input_ports:
                for conn in port.connections:
                    if conn.start_port and conn.start_port.parent_node == thread_node:
                        if conn.start_port.port_name == '汇总结果':
                            node.param_values[port.port_name] = thread_node.get_aggregated_result()
            _execute_node(node, all_nodes)
            node.set_status(SimpleNodeItem.STATUS_SUCCESS)
            colored_print(f"    结果：{node.result}", "success")
        except Exception as e:
            colored_print(f"    [ERROR] 节点 '{node.name}' 出错：{e}", "error")
            node.set_status(SimpleNodeItem.STATUS_ERROR, str(e))


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def execute_multithreaded_node(
    thread_node: MultithreadNodeItem,
    all_nodes: List[SimpleNodeItem],
) -> List[Any]:
    """执行多线程处理节点"""
    from utils.console_stream import colored_print
    from .batch_executor import BatchGraphExecutor

    # 获取参数
    input_list = thread_node.get_input_list()
    thread_count = thread_node.get_thread_count()
    return_order = thread_node.get_return_order()

    # 参数验证
    if not input_list:
        colored_print("[多线程处理] 输入列表为空，跳过执行", "warning")
        return []

    thread_count = max(1, min(thread_count, len(input_list)))

    # 找连接节点
    iteration_nodes, result_nodes = _get_nodes_connected_to_thread_node(thread_node, all_nodes)

    colored_print(
        f"[多线程处理] 开始执行，输入列表长度：{len(input_list)}，"
        f"线程数：{thread_count}，返回顺序：{return_order}",
        "info"
    )
    colored_print(f"  迭代节点：{[n.name for n in iteration_nodes]}", "debug")

    # 重置状态
    thread_node.reset_execution_state()

    # 获取 Python 解释器路径
    python_exe = BatchGraphExecutor()._find_python()

    # 在主线程中预先生成所有脚本（避免多线程修改节点对象）
    scripts = []
    if iteration_nodes:
        sorted_iter_nodes = topological_sort(iteration_nodes)
        for item in input_list:
            script = _build_iteration_script(sorted_iter_nodes, item, thread_node)
            scripts.append(script)
    else:
        # 没有连接节点，直接返回输入列表
        colored_print("[多线程处理] 没有连接到迭代值的节点，直接返回输入列表", "warning")
        for item in input_list:
            thread_node.add_result(item)
        return input_list

    # 并行执行
    results_by_index = {}
    results_ordered = []
    completed = [0]
    success_count = [0]
    lock = threading.Lock()

    def run_one(script: str, idx: int):
        result = _run_script(script, python_exe)
        return idx, result

    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = {
            executor.submit(run_one, script, idx): idx
            for idx, script in enumerate(scripts)
        }

        for future in as_completed(futures):
            idx = futures[future]
            try:
                _, result = future.result()
                with lock:
                    results_by_index[idx] = result
                    results_ordered.append(result)
                    completed[0] += 1
                    success_count[0] += 1
                _safe_print(
                    f"[多线程处理] 完成 item[{idx}] ({completed[0]}/{len(input_list)})",
                    "info"
                )
            except Exception as e:
                with lock:
                    results_by_index[idx] = None
                    results_ordered.append(None)
                    completed[0] += 1
                _safe_print(
                    f"[多线程处理] 线程出错 - item[{idx}]: {e}",
                    "error"
                )

    _safe_print(
        f"[多线程处理] 所有线程完成！成功：{success_count[0]}/{len(input_list)}",
        "info"
    )

    # 整理结果
    if return_order == "按输入顺序":
        final_results = [results_by_index.get(i) for i in range(len(input_list))]
    else:
        final_results = results_ordered

    # 存储结果到节点
    for r in final_results:
        thread_node.add_result(r)

    # 更新迭代节点状态
    for node in iteration_nodes:
        node.set_status(SimpleNodeItem.STATUS_SUCCESS)

    # 执行汇总结果节点
    if result_nodes:
        colored_print("\n[多线程处理] 执行汇总结果节点...", "info")
        _execute_result_nodes(result_nodes, thread_node, all_nodes)

    colored_print(f"[多线程处理] 汇总结果：{final_results}", "success")
    return final_results
