"""编排执行引擎

将所有节点编排成一个完整的 Python 脚本执行

核心思路：
1. 从所有节点中提取 import 语句到文件头部
2. 根据拓扑关系生成顺序执行代码
3. 循环节点生成 for 循环代码
4. 可复用代码提取为函数
"""

import re
import sys
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from ..graphics.simple_node_item import SimpleNodeItem
from ..graphics.loop_node_item import LoopNodeItem, RangeLoopNodeItem, ListLoopNodeItem
from .graph_executor import topological_sort


class OrchestratedGraphExecutor:
    """编排图表执行器

    将图表中的所有节点编排成一个完整的 Python 脚本执行
    """

    def __init__(self):
        self._node_results = {}  # 节点执行结果缓存

    def execute_graph(
        self,
        nodes: List[SimpleNodeItem],
        loop_nodes: List[LoopNodeItem]
    ) -> bool:
        """执行图表

        Args:
            nodes: 普通节点列表
            loop_nodes: 循环节点列表

        Returns:
            执行是否成功
        """
        from utils.console_stream import colored_print

        colored_print("=" * 50, "system")
        colored_print("开始运行图表（编排执行模式）...", "info")

        # 1. 收集所有节点（包括循环节点内部的节点）
        all_nodes = self._collect_all_nodes(nodes, loop_nodes)

        # 2. 提取所有 import 语句
        all_imports = self._extract_all_imports(all_nodes)

        # 3. 生成节点函数定义
        node_functions = self._generate_node_functions(all_nodes)

        # 4. 生成主执行代码
        main_code = self._generate_main_execution(nodes, loop_nodes, all_nodes)

        # 5. 组装完整脚本
        full_script = self._assemble_script(all_imports, node_functions, main_code)

        # 6. 打印生成的脚本（用于调试）
        colored_print("\n生成的执行脚本:", "debug")
        colored_print("-" * 50, "debug")
        colored_print(full_script, "debug")
        colored_print("-" * 50, "debug")

        # 7. 执行脚本
        try:
            self._execute_script(full_script, all_nodes)
            colored_print("\n运行完成！", "success")
            colored_print("=" * 50, "system")
            return True
        except Exception as e:
            colored_print(f"\n运行出错：{e}", "error")
            import traceback
            colored_print(traceback.format_exc(), "error")
            return False

    def _collect_all_nodes(
        self,
        nodes: List[SimpleNodeItem],
        loop_nodes: List[LoopNodeItem]
    ) -> List[SimpleNodeItem]:
        """收集所有节点（包括循环节点内部的节点）"""
        all_nodes = list(nodes)
        for loop_node in loop_nodes:
            all_nodes.extend(loop_node.nodes)
        return all_nodes

    def _extract_all_imports(self, nodes: List[SimpleNodeItem]) -> Set[str]:
        """从所有节点中提取 import 语句"""
        imports = set()

        for node in nodes:
            source_code = self._get_node_source_code(node)
            if source_code:
                node_imports = self._extract_imports_from_source(source_code)
                imports.update(node_imports)

        # 添加常用的基础模块
        imports.add('import sys')
        imports.add('import json')

        return imports

    def _extract_imports_from_source(self, source_code: str) -> Set[str]:
        """从源代码中提取 import 语句（包括函数内部的 import）"""
        imports = set()

        for line in source_code.split('\n'):
            line = line.strip()
            # 匹配 import xxx
            import_match = re.match(r'^import\s+(.+)$', line)
            if import_match:
                imports.add(line)
                continue

            # 匹配 from xxx import yyy
            from_match = re.match(r'^from\s+(\S+)\s+import\s+(.+)$', line)
            if from_match:
                imports.add(line)

        return imports

    def _get_node_source_code(self, node) -> Optional[str]:
        """获取节点的源代码"""
        # 优先从 node.source_code 获取
        if hasattr(node, 'source_code') and node.source_code:
            return node.source_code

        # 从 node.func._custom_source 获取
        if hasattr(node, 'func') and hasattr(node.func, '_custom_source'):
            return node.func._custom_source

        # 从 node.func._source 获取（内置节点）
        if hasattr(node, 'func') and hasattr(node.func, '_source'):
            return node.func._source

        return None

    def _generate_node_functions(self, nodes: List[SimpleNodeItem]) -> Dict[str, str]:
        """生成节点函数定义"""
        functions = {}

        for node in nodes:
            source_code = self._get_node_source_code(node)
            if source_code:
                # 提取函数名
                func_name = self._extract_func_name(source_code)
                # 移除 import 语句
                clean_code = self._remove_imports(source_code)
                functions[func_name] = clean_code

        return functions

    def _extract_func_name(self, source_code: str) -> str:
        """从源代码中提取函数名"""
        match = re.search(r'^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', source_code, re.MULTILINE)
        if match:
            return match.group(1)
        return "unknown_function"

    def _remove_imports(self, source_code: str) -> str:
        """从源代码中移除 import 语句（包括函数内部的 import）"""
        lines = source_code.split('\n')
        clean_lines = []

        for line in lines:
            stripped = line.strip()
            # 跳过 import 语句（包括函数内部的 import）
            if stripped.startswith('import ') or stripped.startswith('from '):
                continue
            clean_lines.append(line)

        return '\n'.join(clean_lines)

    def _generate_main_execution(
        self,
        nodes: List[SimpleNodeItem],
        loop_nodes: List[LoopNodeItem],
        all_nodes: List[SimpleNodeItem]
    ) -> str:
        """生成主执行代码"""
        lines = []
        lines.append("# ========== 主执行代码 ==========")
        lines.append("results = {}  # 存储节点执行结果")
        lines.append("")

        # 对普通节点进行拓扑排序
        sorted_nodes = topological_sort(nodes) if nodes else []

        # 生成节点执行代码
        for i, node in enumerate(sorted_nodes):
            func_name = self._extract_func_name(self._get_node_source_code(node) or "")
            node_var = f"node_{i}_result"

            # 获取输入参数
            args = self._get_node_call_args(node, all_nodes)

            # 生成调用代码
            if args:
                args_str = ', '.join([f"{k}={v}" for k, v in args.items()])
                lines.append(f"{node_var} = {func_name}({args_str})")
            else:
                lines.append(f"{node_var} = {func_name}()")

            lines.append(f"results['{node.node_id}'] = {node_var}")
            # 使用双引号避免 f-string 中的引号冲突
            safe_node_name = node.name.replace('"', '\\"')
            lines.append(f'print(f"节点 \'{safe_node_name}\' 执行结果：{{{node_var}}}")')
            lines.append("")

        # 生成循环节点执行代码
        for loop_node in loop_nodes:
            loop_code = self._generate_loop_code(loop_node, all_nodes)
            lines.append(loop_code)
            lines.append("")

        return '\n'.join(lines)

    def _get_node_call_args(
        self,
        node: SimpleNodeItem,
        all_nodes: List[SimpleNodeItem]
    ) -> Dict[str, str]:
        """获取节点调用的参数"""
        args = {}

        for port in node.input_ports:
            param_name = port.port_name
            value = None

            # 检查是否有连接
            if port.connections:
                conn = port.connections[0]
                if conn.start_port:
                    source_node = conn.start_port.parent_node
                    # 使用源节点的结果
                    value = f"results.get('{source_node.node_id}')"
            else:
                # 使用属性面板的值
                if hasattr(node, 'param_values') and param_name in node.param_values:
                    val = node.param_values[param_name]
                    value = repr(val)

            if value:
                args[param_name] = value

        return args

    def _generate_loop_code(
        self,
        loop_node: LoopNodeItem,
        all_nodes: List[SimpleNodeItem]
    ) -> str:
        """生成循环代码"""
        lines = []

        # 获取迭代值
        iterator_values = loop_node.get_iterator_values()

        # 获取连接到循环节点的节点
        iteration_nodes, result_nodes = self._get_nodes_connected_to_loop(loop_node, all_nodes)

        # 循环类型
        safe_loop_name = loop_node.loop_name.replace('"', '\\"')
        if isinstance(loop_node, RangeLoopNodeItem):
            range_start = loop_node.range_start
            range_end = loop_node.range_end
            range_step = loop_node.range_step
            lines.append(f"# 循环：{safe_loop_name}")
            lines.append(f'print("开始执行循环 \'{safe_loop_name}\'...")')
            lines.append(f"loop_results = []")
            lines.append(f"for iterator_value in range({range_start}, {range_end}, {range_step}):")
        else:
            # List 循环
            lines.append(f"# 循环：{safe_loop_name}")
            lines.append(f'print("开始执行循环 \'{safe_loop_name}\'...")')
            lines.append(f"loop_results = []")
            lines.append(f"for iterator_value in {repr(iterator_values)}:")

        # 循环内节点执行
        if iteration_nodes:
            sorted_iter_nodes = topological_sort(iteration_nodes) if iteration_nodes else []
            for iter_node in sorted_iter_nodes:
                func_name = self._extract_func_name(self._get_node_source_code(iter_node) or "")
                args = self._get_node_call_args(iter_node, all_nodes)

                # 替换连接到"迭代值"端口的参数为 iterator_value
                for port in iter_node.input_ports:
                    for conn in port.connections:
                        if conn.start_port and conn.start_port.parent_node == loop_node:
                            if conn.start_port.port_name == '迭代值':
                                args[port.port_name] = "iterator_value"

                if args:
                    args_str = ', '.join([f"{k}={v}" for k, v in args.items()])
                    lines.append(f"    iter_result = {func_name}({args_str})")
                else:
                    lines.append(f"    iter_result = {func_name}()")

                lines.append(f"    loop_results.append(iter_result)")
                lines.append(f'    print(f"  迭代值：{{iterator_value}}, 结果：{{iter_result}}")')
        else:
            # 没有连接节点，直接使用迭代值作为结果
            lines.append("    loop_results.append(iterator_value)")

        # 存储循环结果
        lines.append(f"results['{loop_node.node_id}'] = loop_results")
        lines.append(f'print(f"循环 \'{safe_loop_name}\' 完成，结果：{{loop_results}}")')

        # 执行连接到汇总结果的节点
        if result_nodes:
            lines.append("")
            lines.append(f"# 执行连接到汇总结果的节点")
            for result_node in result_nodes:
                func_name = self._extract_func_name(self._get_node_source_code(result_node) or "")
                args = self._get_node_call_args(result_node, all_nodes)

                # 替换连接到"汇总结果"端口的参数
                for port in result_node.input_ports:
                    for conn in port.connections:
                        if conn.start_port and conn.start_port.parent_node == loop_node:
                            if conn.start_port.port_name == '汇总结果':
                                args[port.port_name] = f"results.get('{loop_node.node_id}')"

                if args:
                    args_str = ', '.join([f"{k}={v}" for k, v in args.items()])
                    lines.append(f"result_node_result = {func_name}({args_str})")
                else:
                    lines.append(f"result_node_result = {func_name}()")

                lines.append(f"results['{result_node.node_id}'] = result_node_result")
                safe_result_node_name = result_node.name.replace('"', '\\"')
                lines.append(f'print(f"节点 \'{safe_result_node_name}\' 执行结果：{{result_node_result}}")')

        return '\n'.join(lines)

    def _get_nodes_connected_to_loop(
        self,
        loop_node: LoopNodeItem,
        all_nodes: List[SimpleNodeItem]
    ) -> Tuple[List[SimpleNodeItem], List[SimpleNodeItem]]:
        """获取连接到循环节点的节点"""
        iteration_nodes = set()
        result_nodes = set()

        for node in all_nodes:
            if not isinstance(node, SimpleNodeItem):
                continue
            if node == loop_node:
                continue

            for port in node.input_ports:
                for conn in port.connections:
                    if conn.start_port and conn.start_port.parent_node == loop_node:
                        if conn.start_port.port_name == '迭代值':
                            iteration_nodes.add(node)
                        elif conn.start_port.port_name == '汇总结果':
                            result_nodes.add(node)

        return list(iteration_nodes), list(result_nodes)

    def _assemble_script(
        self,
        imports: Set[str],
        node_functions: Dict[str, str],
        main_code: str
    ) -> str:
        """组装完整脚本"""
        script_lines = []

        # 1. 文件头注释
        script_lines.append("#!/usr/bin/env python3")
        script_lines.append("# -*- coding: utf-8 -*-")
        script_lines.append('"""自动生成的节点执行脚本"""')
        script_lines.append("")

        # 2. Import 语句
        script_lines.append("# ========== 导入模块 ==========")
        for imp in sorted(imports):
            script_lines.append(imp)
        script_lines.append("")

        # 3. 节点函数定义
        script_lines.append("# ========== 节点函数定义 ==========")
        for func_name, func_code in node_functions.items():
            script_lines.append(f"# 节点：{func_name}")
            script_lines.append(func_code)
            script_lines.append("")

        # 4. 主执行代码
        script_lines.append(main_code)

        return '\n'.join(script_lines)

    def _execute_script(
        self,
        script: str,
        all_nodes: List[SimpleNodeItem]
    ):
        """执行生成的脚本"""
        from utils.console_stream import colored_print

        # 创建执行环境
        exec_env = {
            '__builtins__': __builtins__,
            '__file__': '<generated_script>',
        }

        # 预导入所有模块到执行环境
        import_lines = [line for line in script.split('\n')
                       if line.strip().startswith('import ') or
                          line.strip().startswith('from ')]
        
        missing_modules = []
        for line in import_lines:
            try:
                exec(line, exec_env)
            except ImportError as e:
                # 提取模块名
                module_name = line.replace('import ', '').replace('from ', '').split()[0].split('.')[0]
                missing_modules.append(module_name)
                colored_print(f"导入模块失败：{line} - {e}", "warning")

        # 如果有缺失的模块，提供安装提示
        if missing_modules:
            colored_print("\n[警告] 以下模块未安装:", "warning")
            for module in missing_modules:
                colored_print(f"  - {module}", "warning")
            
            colored_print("\n[提示] 请运行以下命令安装缺失的模块:", "info")
            colored_print(f"  pip install {' '.join(missing_modules)}", "info")
            colored_print("\n[提示] 如果是打包后的环境，请运行:", "info")
            colored_print(f"  install_embedded_deps.bat", "info")
            colored_print(f"  或将依赖安装到 python_embedded/Lib/site-packages 目录\n", "info")

        # 执行脚本
        try:
            exec(script, exec_env, exec_env)
        except Exception as e:
            colored_print(f"\n[错误] 执行脚本时出错：{e}", "error")
            raise
