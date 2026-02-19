"""嵌入式 Python 环境初始化工具

用于下载、配置和管理嵌入式 Python 环境。
支持 Windows 官方嵌入式 Python 发行版。
"""

import urllib.request
import zipfile
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Callable


# 嵌入式 Python 下载配置
EMBEDDED_PYTHON_URLS = {
    "3.10": "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip",
    "3.11": "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip",
    "3.12": "https://www.python.org/ftp/python/3.12.4/python-3.12.4-embed-amd64.zip",
}

GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"


class EmbeddedPythonSetup:
    """嵌入式 Python 环境安装器"""
    
    def __init__(
        self, 
        target_dir: Optional[Path] = None,
        version: str = "3.10",
        progress_callback: Optional[Callable[[str, int], None]] = None
    ):
        """初始化安装器
        
        Args:
            target_dir: 安装目标目录，None 则使用项目目录
            version: Python 版本，支持 "3.10", "3.11", "3.12"
            progress_callback: 进度回调函数，接收 (消息, 百分比)
        """
        self.version = version
        self.progress_callback = progress_callback or self._default_progress
        
        # 确定目标目录
        if target_dir is None:
            # 默认安装到项目根目录
            self.target_dir = Path(__file__).parent.parent.resolve()
        else:
            self.target_dir = Path(target_dir).resolve()
        
        self.embedded_dir = self.target_dir / "python_embedded"
        self.python_exe = self.embedded_dir / "python.exe"
        
    def _default_progress(self, message: str, percent: int):
        """默认进度输出"""
        print(f"[{percent:3d}%] {message}")
    
    def _report(self, message: str, percent: int):
        """报告进度"""
        self.progress_callback(message, percent)
    
    def is_installed(self) -> bool:
        """检查是否已安装"""
        return self.python_exe.exists()
    
    def get_python_path(self) -> Optional[str]:
        """获取 Python 解释器路径"""
        if self.is_installed():
            return str(self.python_exe)
        return None
    
    def install(self) -> bool:
        """执行完整安装流程
        
        安装步骤：
        1. 下载嵌入式 Python zip
        2. 解压到目标目录
        3. 启用 site 导入支持
        4. 下载 get-pip.py
        5. 安装 pip
        
        Returns:
            安装是否成功
        """
        try:
            # 检查平台
            if sys.platform != "win32":
                print(f"警告: 当前平台 {sys.platform} 不是 Windows，")
                print("嵌入式 Python 主要针对 Windows 设计。")
                print("在 macOS/Linux 上，建议使用系统 Python 或 pyenv。")
                response = input("是否继续？ [y/N]: ")
                if response.lower() != 'y':
                    return False
            
            self._report("开始安装嵌入式 Python...", 0)
            
            # 创建目录
            self.embedded_dir.mkdir(parents=True, exist_ok=True)
            self._report(f"安装目录: {self.embedded_dir}", 5)
            
            # 1. 下载嵌入式 Python
            if not self._download_python():
                return False
            
            # 2. 启用 site 支持
            self._enable_site_support()
            
            # 3. 下载并安装 pip
            if not self._install_pip():
                return False
            
            # 4. 验证安装
            if not self._verify_installation():
                return False
            
            self._report("安装完成！", 100)
            print(f"\n嵌入式 Python 已安装到: {self.embedded_dir}")
            print(f"Python 路径: {self.python_exe}")
            print("\n你可以：")
            print("1. 设置环境变量: NODE_PYTHON_EMBEDDED=" + str(self.python_exe))
            print("2. 在程序中自动检测此路径")
            
            return True
            
        except Exception as e:
            self._report(f"安装失败: {e}", 0)
            import traceback
            traceback.print_exc()
            return False
    
    def _download_python(self) -> bool:
        """下载嵌入式 Python"""
        url = EMBEDDED_PYTHON_URLS.get(self.version)
        if not url:
            print(f"不支持的版本: {self.version}")
            print(f"支持的版本: {list(EMBEDDED_PYTHON_URLS.keys())}")
            return False
        
        zip_path = self.embedded_dir / "python_embedded.zip"
        
        self._report(f"正在下载 Python {self.version}...", 10)
        print(f"下载地址: {url}")
        
        try:
            # 使用 urllib 下载，显示进度
            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                percent = min(int(downloaded / total_size * 30), 30)  # 10-40%
                self._report(f"下载中... {downloaded // 1024 // 1024}MB", 10 + percent)
            
            urllib.request.urlretrieve(url, zip_path, reporthook=download_progress)
            
            self._report("下载完成，正在解压...", 40)
            
            # 解压
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.embedded_dir)
            
            # 删除 zip 文件
            zip_path.unlink()
            
            self._report("解压完成", 50)
            return True
            
        except Exception as e:
            print(f"下载失败: {e}")
            return False
    
    def _enable_site_support(self):
        """启用 site 导入支持（用于 pip）"""
        self._report("启用 site 支持...", 55)
        
        # 查找 ._pth 文件
        pth_files = list(self.embedded_dir.glob("*._pth"))
        if not pth_files:
            print("警告: 未找到 ._pth 文件，pip 可能无法正常工作")
            return
        
        pth_file = pth_files[0]
        
        # 读取并修改
        with open(pth_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 取消注释 import site
        if '#import site' in content:
            content = content.replace('#import site', 'import site')
            with open(pth_file, 'w', encoding='utf-8') as f:
                f.write(content)
            self._report("已启用 site 支持", 60)
        elif 'import site' in content:
            self._report("site 支持已启用", 60)
        else:
            # 添加 import site
            with open(pth_file, 'a', encoding='utf-8') as f:
                f.write('\nimport site\n')
            self._report("已添加 site 支持", 60)
    
    def _install_pip(self) -> bool:
        """下载并安装 pip"""
        self._report("正在下载 pip 安装程序...", 65)
        
        get_pip_path = self.embedded_dir / "get-pip.py"
        
        try:
            urllib.request.urlretrieve(GET_PIP_URL, get_pip_path)
            self._report("正在安装 pip...", 75)
            
            # 运行 get-pip.py
            result = subprocess.run(
                [str(self.python_exe), str(get_pip_path)],
                capture_output=True,
                text=True,
                cwd=str(self.embedded_dir),
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode != 0:
                print("pip 安装失败:")
                print(result.stderr)
                return False
            
            # 删除 get-pip.py
            get_pip_path.unlink()
            
            self._report("pip 安装完成", 85)
            return True
            
        except Exception as e:
            print(f"安装 pip 失败: {e}")
            return False
    
    def _verify_installation(self) -> bool:
        """验证安装"""
        self._report("验证安装...", 90)
        
        try:
            # 检查 Python 版本
            result = subprocess.run(
                [str(self.python_exe), '--version'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                print(f"Python 版本: {result.stdout.strip() or result.stderr.strip()}")
            else:
                print("无法获取 Python 版本")
                return False
            
            # 检查 pip
            result = subprocess.run(
                [str(self.python_exe), '-m', 'pip', '--version'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if result.returncode == 0:
                print(f"pip 版本: {result.stdout.strip()}")
            else:
                print("pip 未正确安装")
                return False
            
            self._report("验证通过", 95)
            return True
            
        except Exception as e:
            print(f"验证失败: {e}")
            return False
    
    def uninstall(self) -> bool:
        """卸载嵌入式 Python"""
        if not self.embedded_dir.exists():
            print("嵌入式 Python 未安装")
            return True
        
        try:
            import shutil
            shutil.rmtree(self.embedded_dir)
            print(f"已删除: {self.embedded_dir}")
            return True
        except Exception as e:
            print(f"卸载失败: {e}")
            return False
    
    def get_info(self) -> dict:
        """获取安装信息"""
        info = {
            "target_dir": str(self.target_dir),
            "embedded_dir": str(self.embedded_dir),
            "python_exe": str(self.python_exe),
            "is_installed": self.is_installed(),
            "version": self.version,
        }
        
        if self.is_installed():
            try:
                # 获取 Python 版本
                result = subprocess.run(
                    [str(self.python_exe), '--version'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                info["python_version"] = result.stdout.strip() or result.stderr.strip()
                
                # 获取已安装包数量
                result = subprocess.run(
                    [str(self.python_exe), '-m', 'pip', 'list', '--format=json'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                if result.returncode == 0:
                    import json
                    packages = json.loads(result.stdout)
                    info["installed_packages"] = len(packages)
                
            except Exception as e:
                info["error"] = str(e)
        
        return info


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="嵌入式 Python 环境管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 安装嵌入式 Python
  python -m utils.setup_embedded_python install
  
  # 安装特定版本
  python -m utils.setup_embedded_python install --version 3.11
  
  # 指定安装目录
  python -m utils.setup_embedded_python install --target-dir D:/tools
  
  # 查看安装信息
  python -m utils.setup_embedded_python info
  
  # 卸载
  python -m utils.setup_embedded_python uninstall
        """
    )
    
    parser.add_argument(
        'command',
        choices=['install', 'uninstall', 'info'],
        help='要执行的命令'
    )
    parser.add_argument(
        '--version',
        choices=['3.10', '3.11', '3.12'],
        default='3.10',
        help='Python 版本（默认: 3.10）'
    )
    parser.add_argument(
        '--target-dir',
        type=str,
        help='安装目标目录（默认: 项目根目录）'
    )
    
    args = parser.parse_args()
    
    target_dir = Path(args.target_dir) if args.target_dir else None
    setup = EmbeddedPythonSetup(
        target_dir=target_dir,
        version=args.version
    )
    
    if args.command == 'install':
        success = setup.install()
        sys.exit(0 if success else 1)
    
    elif args.command == 'uninstall':
        success = setup.uninstall()
        sys.exit(0 if success else 1)
    
    elif args.command == 'info':
        info = setup.get_info()
        print("\n嵌入式 Python 环境信息:")
        print("-" * 40)
        for key, value in info.items():
            print(f"{key}: {value}")
        print("-" * 40)


if __name__ == '__main__':
    main()
