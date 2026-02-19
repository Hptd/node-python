"""控制台重定向"""

import os
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, Signal


class EmittingStream(QObject):
    textWritten = Signal(str)

    def __init__(self):
        super().__init__()
        self._log_dir = "output_logs"
        self._log_filename = "output_log.txt"
        self._enabled = True

    def set_log_path(self, log_dir: str, filename: str = "output_log.txt"):
        """设置日志文件路径"""
        self._log_dir = log_dir
        self._log_filename = filename

    def set_enabled(self, enabled: bool):
        """设置是否启用日志记录"""
        self._enabled = enabled

    def get_log_file_path(self) -> str:
        """获取完整的日志文件路径"""
        log_path = Path(self._log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        return str(log_path / self._log_filename)

    def write(self, text):
        """写入文本到控制台和日志文件"""
        text = str(text)
        self.textWritten.emit(text)

        # 写入日志文件
        if self._enabled and text:
            try:
                log_file_path = self.get_log_file_path()
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    # 添加时间戳
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # 处理文本，确保每行都有时间戳
                    lines = text.split('\n')
                    for line in lines:
                        if line:  # 只写入非空行
                            f.write(f"[{timestamp}] {line}\n")
            except Exception as e:
                # 日志写入失败时，不中断程序
                print(f"[日志写入失败] {e}")

    def flush(self):
        pass

    def clear_log(self):
        """清空日志文件"""
        try:
            log_file_path = self.get_log_file_path()
            if os.path.exists(log_file_path):
                with open(log_file_path, 'w', encoding='utf-8') as f:
                    f.write("")
                return True
        except Exception as e:
            print(f"[清空日志失败] {e}")
        return False