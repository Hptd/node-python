"""嵌入式 Python 执行器

用于在独立的嵌入式 Python 环境中执行节点代码，支持第三方库。
"""

import subprocess
import json
import tempfile
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class EmbeddedPythonExecutor:
    """嵌入式 Python 执行器
    
    在独立的 Python 进程中执行节点代码，支持：
    - 动态导入第三方库
    - 安全沙箱限制
    - 超时控制
    - 结果序列化
    """
    
    def __init__(self, python_path: Optional[str] = None):
        """初始化执行器
        
        Args:
            python_path: 嵌入式 Python 解释器路径，None 则自动查找
        """
        self.python_exe = python_path or self._find_embedded_python()
        self.site_packages = Path(self.python_exe).parent / "Lib" / "site-packages"
        self._check_environment()
    
    def _find_embedded_python(self) -> str:
        """查找嵌入式 Python 解释器路径
        
        查找顺序（优先exe同级目录）：
        1. 可执行文件同级目录的 python_embedded/python.exe（打包后主要使用）
        2. 环境变量 NODE_PYTHON_EMBEDDED
        3. 项目目录下的 python_embedded/python.exe（开发环境）
        """
        import sys
        
        # 1. 可执行文件同级目录（打包后的主要使用场景）
        if hasattr(sys, '_MEIPASS'):  # PyInstaller 打包环境
            exe_dir = Path(sys.executable).parent
        else:
            exe_dir = Path(sys.executable).parent
        
        embedded_path = exe_dir / "python_embedded" / "python.exe"
        if embedded_path.exists():
            return str(embedded_path.resolve())
        
        # 2. 环境变量
        env_path = os.environ.get("NODE_PYTHON_EMBEDDED")
        if env_path and Path(env_path).exists():
            return str(Path(env_path).resolve())
        
        # 3. 项目目录（开发环境备用）
        project_dir = Path(__file__).parent.parent.parent
        embedded_path = project_dir / "python_embedded" / "python.exe"
        if embedded_path.exists():
            return str(embedded_path.resolve())
        
        raise RuntimeError(
            "未找到嵌入式 Python 环境。\n"
            f"请检查以下位置是否存在 python_embedded/python.exe：\n"
            f"1. {exe_dir / 'python_embedded'}（exe同级目录，打包后主要使用）\n"
            f"2. 环境变量 NODE_PYTHON_EMBEDDED 指定的路径\n"
            f"3. {project_dir / 'python_embedded'}（开发环境）\n\n"
            "注意：所有节点（包括内置节点）都将在外部 python_embedded 环境中执行。\n"
            "请运行 python -m utils.setup_embedded_python install 进行初始化。"
        )
    
    def _check_environment(self):
        """检查环境是否就绪"""
        if not Path(self.python_exe).exists():
            raise RuntimeError(f"Python 解释器不存在: {self.python_exe}")
        
        # 查找 site-packages 目录（可能在不同位置）
        possible_paths = [
            Path(self.python_exe).parent / "Lib" / "site-packages",
            Path(self.python_exe).parent / "lib" / "python3.10" / "site-packages",
            Path(self.python_exe).parent / "lib" / "python3.11" / "site-packages",
            Path(self.python_exe).parent / "lib" / "python3.12" / "site-packages",
        ]
        
        for path in possible_paths:
            if path.exists():
                self.site_packages = path
                break
        else:
            # 使用默认路径并创建
            self.site_packages = Path(self.python_exe).parent / "Lib" / "site-packages"
            self.site_packages.mkdir(parents=True, exist_ok=True)
    
    def execute_node(
        self, 
        func_code: str, 
        args: Dict[str, Any], 
        imports: Optional[List[str]] = None,
        timeout: int = 30
    ) -> Any:
        """在嵌入式环境中执行节点函数
        
        Args:
            func_code: 函数代码字符串
            args: 参数字典
            imports: 需要预导入的模块列表
            timeout: 执行超时时间（秒）
        
        Returns:
            函数执行结果（已反序列化）
        
        Raises:
            RuntimeError: 执行失败
            TimeoutError: 执行超时
        """
        # 调试信息
        print(f"  [调试] Python: {self.python_exe}")
        print(f"  [调试] Site-packages: {self.site_packages}")
        print(f"  [调试] Imports: {imports}")
        
        # 构建执行脚本
        script = self._build_execution_script(func_code, args, imports)
        
        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False, encoding='utf-8'
        ) as f:
            f.write(script)
            script_path = f.name
        
        try:
            # 执行脚本
            result = subprocess.run(
                [self.python_exe, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path(self.python_exe).parent),
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode != 0:
                # 执行失败，解析错误信息
                # 合并 stdout 和 stderr 来查找错误信息
                combined_output = result.stdout + "\n" + result.stderr
                error_msg = self._parse_error(combined_output)
                raise RuntimeError(error_msg)
            
            # 解析执行结果
            return self._parse_result(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"节点执行超时（{timeout}秒）")
        finally:
            # 清理临时文件
            try:
                os.unlink(script_path)
            except:
                pass
    
    def _build_execution_script(
        self,
        func_code: str,
        args: Dict[str, Any],
        imports: Optional[List[str]]
    ) -> str:
        """构建执行脚本

        生成的脚本包含：
        1. 环境设置（添加 site-packages 到路径）
        2. 预导入模块
        3. 用户函数代码
        4. 函数执行和结果序列化
        """
        # 处理 imports
        import_lines = ""
        if imports:
            for imp in imports:
                import_lines += f"import {imp}\n"

        # 提取函数名
        func_name = self._extract_func_name(func_code)

        # 使用 JSON 序列化参数，确保列表和字典类型正确传递
        args_json = json.dumps(args, ensure_ascii=False, default=str)

        # 构建脚本
        # 使用 json.dumps 来安全地转义代码字符串
        func_code_escaped = json.dumps(func_code, ensure_ascii=False)
        
        script = f'''# -*- coding: utf-8 -*-
import sys
import json
import traceback
import site
import ast

# 确保 site-packages 在路径中
for p in site.getsitepackages():
    if p not in sys.path:
        sys.path.insert(0, p)

# 预导入模块
{import_lines}

# 用户函数代码
{func_code}

# 执行函数并输出结果
if __name__ == "__main__":
    try:
        # 先检查语法错误
        func_code_str = {func_code_escaped}
        try:
            ast.parse(func_code_str)
        except SyntaxError as se:
            error_output = {{
                "success": False,
                "error": "语法错误: " + str(se.msg) + " (行 " + str(se.lineno) + ")",
                "traceback": "SyntaxError: " + str(se.msg) + "\\n  文件: <节点代码>, 行 " + str(se.lineno)
            }}
            print("__ERROR_START__", file=sys.stderr)
            print(json.dumps(error_output, ensure_ascii=False), file=sys.stderr)
            print("__ERROR_END__", file=sys.stderr)
            sys.exit(1)
        
        args = json.loads('{args_json}')
        result = {func_name}(**args)
        
        # 序列化结果
        output = {{
            "success": True,
            "result": result,
            "type": type(result).__name__
        }}
        print("__RESULT_START__")
        print(json.dumps(output, default=str, ensure_ascii=False))
        print("__RESULT_END__")
        
    except Exception as e:
        error_output = {{
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }}
        # 输出到 stderr 以便正确捕获
        print("__ERROR_START__", file=sys.stderr)
        print(json.dumps(error_output, ensure_ascii=False), file=sys.stderr)
        print("__ERROR_END__", file=sys.stderr)
        sys.exit(1)
'''
        return script
    
    def _extract_func_name(self, code: str) -> str:
        """从代码中提取函数名
        
        使用正则表达式匹配函数定义，
        要求代码中必须且只能定义一个顶层函数。
        """
        pattern = r'^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, code, re.MULTILINE)
        
        if not matches:
            raise ValueError("代码中未找到函数定义")
        
        if len(matches) > 1:
            raise ValueError(f"代码中定义了多个函数: {matches}，只允许一个")
        
        return matches[0]
    
    def _parse_result(self, stdout: str) -> Any:
        """解析执行结果
        
        从 stdout 中提取 JSON 格式的结果
        同时捕获打印输出并显示到主控制台
        """
        # 查找结果标记
        start_marker = "__RESULT_START__"
        end_marker = "__RESULT_END__"
        
        start_idx = stdout.find(start_marker)
        end_idx = stdout.find(end_marker)
        
        # 捕获并显示打印输出（结果标记之前的内容）
        if start_idx > 0:
            printed_output = stdout[:start_idx].strip()
            if printed_output:
                # 将嵌入式环境的打印输出显示到主控制台
                print(f"  [节点输出] {printed_output}")
        
        if start_idx == -1 or end_idx == -1:
            # 没有找到标记，可能是旧格式或错误
            # 尝试直接解析最后几行
            lines = stdout.strip().split('\n')
            for line in reversed(lines):
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        if isinstance(data, dict) and "success" in data:
                            if data["success"]:
                                return data.get("result")
                            else:
                                raise RuntimeError(data.get("error", "未知错误"))
                    except json.JSONDecodeError:
                        continue
            
            # 如果都失败了，返回原始输出
            return stdout.strip()
        
        # 提取 JSON 内容
        json_str = stdout[start_idx + len(start_marker):end_idx].strip()
        
        try:
            data = json.loads(json_str)
            if data.get("success"):
                result = data.get("result")
                # 对于返回 None 的节点，打印节点的输出已经在前面显示了
                return result
            else:
                raise RuntimeError(data.get("error", "未知错误"))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"无法解析执行结果: {e}")
    
    def _parse_error(self, output: str) -> str:
        """解析错误信息，返回详细信息包括 traceback"""
        # 查找错误标记
        start_marker = "__ERROR_START__"
        end_marker = "__ERROR_END__"
        
        start_idx = output.find(start_marker)
        end_idx = output.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            json_str = output[start_idx + len(start_marker):end_idx].strip()
            try:
                data = json.loads(json_str)
                error_msg = data.get("error", "未知错误")
                traceback_info = data.get("traceback", "")
                
                # 返回详细错误信息，包含 traceback
                if traceback_info:
                    return f"{traceback_info}"
                return error_msg
            except:
                pass
        
        # 尝试从输出中直接提取 Python 错误信息
        # 查找 Traceback 开头
        lines = output.strip().split('\n')
        traceback_lines = []
        in_traceback = False
        error_line = ""
        
        for line in lines:
            if 'Traceback (most recent call last)' in line:
                in_traceback = True
                traceback_lines.append(line)
            elif in_traceback:
                traceback_lines.append(line)
                # 检测错误行（如 NameError, SyntaxError 等）
                if 'Error:' in line or 'Exception:' in line:
                    error_line = line
            # 也检测单独的错误行
            elif 'Error:' in line or 'Exception:' in line:
                if not error_line:
                    error_line = line
        
        # 如果找到了 traceback，返回完整信息
        if traceback_lines:
            return '\n'.join(traceback_lines)
        
        # 如果只找到错误行
        if error_line:
            return error_line
        
        # 返回原始输出
        return output.strip() or "执行失败（无错误信息）"
    
    # ==================== 包管理功能 ====================
    
    def install_package(self, package_name: str) -> Tuple[bool, str]:
        """安装第三方包
        
        Args:
            package_name: 包名，可以是 "requests" 或 "requests==2.28.0"
        
        Returns:
            (成功标志, 输出信息)
        """
        try:
            result = subprocess.run(
                [self.python_exe, '-m', 'pip', 'install', package_name],
                capture_output=True,
                text=True,
                timeout=300,  # 安装可能较慢
                cwd=str(Path(self.python_exe).parent),
                encoding='utf-8',
                errors='replace'
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            return result.returncode == 0, output
            
        except subprocess.TimeoutExpired:
            return False, "安装超时（5分钟）"
        except Exception as e:
            return False, f"安装失败: {str(e)}"
    
    def uninstall_package(self, package_name: str) -> Tuple[bool, str]:
        """卸载第三方包"""
        try:
            result = subprocess.run(
                [self.python_exe, '-m', 'pip', 'uninstall', '-y', package_name],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(Path(self.python_exe).parent),
                encoding='utf-8',
                errors='replace'
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            return result.returncode == 0, output
            
        except Exception as e:
            return False, f"卸载失败: {str(e)}"
    
    def list_installed_packages(self) -> List[Dict[str, str]]:
        """列出已安装的包
        
        Returns:
            包列表，每个包包含 name 和 version
        """
        try:
            result = subprocess.run(
                [self.python_exe, '-m', 'pip', 'list', '--format=json'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path(self.python_exe).parent),
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                # 过滤掉 pip、setuptools、wheel 等基础包
                exclude = {'pip', 'setuptools', 'wheel'}
                return [p for p in packages if p['name'] not in exclude]
            
            return []
            
        except Exception as e:
            print(f"获取包列表失败: {e}")
            return []
    
    def check_package_installed(self, package_name: str) -> bool:
        """检查包是否已安装"""
        packages = self.list_installed_packages()
        return any(p['name'].lower() == package_name.lower() for p in packages)
    
    def get_package_info(self, package_name: str) -> Optional[Dict]:
        """获取包详细信息"""
        try:
            result = subprocess.run(
                [self.python_exe, '-m', 'pip', 'show', package_name],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path(self.python_exe).parent),
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                info = {}
                for line in result.stdout.strip().split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip().lower()] = value.strip()
                return info
            
            return None
            
        except Exception:
            return None
    
    def install_requirements(self, requirements_file: str) -> Tuple[bool, str]:
        """从 requirements.txt 安装依赖
        
        Args:
            requirements_file: requirements.txt 文件路径
        
        Returns:
            (成功标志, 输出信息)
        """
        if not Path(requirements_file).exists():
            return False, f"文件不存在: {requirements_file}"
        
        try:
            result = subprocess.run(
                [self.python_exe, '-m', 'pip', 'install', '-r', requirements_file],
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(Path(self.python_exe).parent),
                encoding='utf-8',
                errors='replace'
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            return result.returncode == 0, output
            
        except subprocess.TimeoutExpired:
            return False, "安装超时（10分钟）"
        except Exception as e:
            return False, f"安装失败: {str(e)}"
    
    def export_requirements(self, output_file: str) -> bool:
        """导出当前环境到 requirements.txt"""
        try:
            result = subprocess.run(
                [self.python_exe, '-m', 'pip', 'freeze'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path(self.python_exe).parent),
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                # 过滤基础包
                lines = result.stdout.strip().split('\n')
                filtered = []
                for line in lines:
                    if not any(line.lower().startswith(pkg) for pkg in ['pip', 'setuptools', 'wheel']):
                        filtered.append(line)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(filtered))
                
                return True
            
            return False
            
        except Exception as e:
            print(f"导出失败: {e}")
            return False
    
    # ==================== 环境信息 ====================
    
    def get_python_version(self) -> str:
        """获取嵌入式 Python 版本"""
        try:
            result = subprocess.run(
                [self.python_exe, '--version'],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='utf-8',
                errors='replace'
            )
            return result.stdout.strip() or result.stderr.strip()
        except Exception as e:
            return f"无法获取版本: {e}"
    
    def get_environment_info(self) -> Dict[str, Any]:
        """获取环境信息摘要"""
        return {
            "python_exe": self.python_exe,
            "python_version": self.get_python_version(),
            "site_packages": str(self.site_packages),
            "site_packages_exists": self.site_packages.exists(),
            "installed_packages_count": len(self.list_installed_packages())
        }


# 全局执行器实例（懒加载）
_executor: Optional[EmbeddedPythonExecutor] = None

def get_executor() -> EmbeddedPythonExecutor:
    """获取全局执行器实例"""
    global _executor
    if _executor is None:
        _executor = EmbeddedPythonExecutor()
    return _executor

def reset_executor():
    """重置执行器（用于配置变更后）"""
    global _executor
    _executor = None
