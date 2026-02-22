"""控制台重定向"""

import os
import re
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QTextCharFormat, QColor, QFont

from utils.theme_manager import theme_manager


class EmittingStream(QObject):
    textWritten = Signal(str, str)  # 添加消息类型参数

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

    def write(self, text, msg_type: str = "normal"):
        """写入文本到控制台和日志文件
        
        Args:
            text: 要写入的文本
            msg_type: 消息类型 (normal, error, warning, info, success, debug, system)
        """
        text = str(text)
        self.textWritten.emit(text, msg_type)

        # 写入日志文件
        if self._enabled and text:
            try:
                log_file_path = self.get_log_file_path()
                with open(log_file_path, 'a', encoding='utf-8') as f:
                    # 添加时间戳和消息类型标记
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    type_prefix = f"[{msg_type.upper()}]" if msg_type != "normal" else ""
                    # 处理文本，确保每行都有时间戳
                    lines = text.split('\n')
                    for line in lines:
                        if line:  # 只写入非空行
                            f.write(f"[{timestamp}]{type_prefix} {line}\n")
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


def colored_print(text: str, msg_type: str = "normal"):
    """彩色打印函数
    
    Args:
        text: 要打印的文本
        msg_type: 消息类型
            - "normal": 普通文本（默认控制台颜色）
            - "error": 错误信息（红色）
            - "warning": 警告信息（橙色）
            - "info": 提示信息（蓝色）
            - "success": 成功信息（绿色）
            - "debug": 调试信息（紫色）
            - "system": 系统信息（灰色）
    """
    import sys
    from utils.console_stream import EmittingStream
    
    # 如果 stdout 是 EmittingStream 实例，使用带类型的写入
    if isinstance(sys.stdout, EmittingStream):
        sys.stdout.write(text, msg_type)
    else:
        # 否则使用普通打印
        print(text)


def get_message_format(msg_type: str) -> QTextCharFormat:
    """获取消息类型对应的文本格式
    
    Args:
        msg_type: 消息类型
        
    Returns:
        QTextCharFormat 对象
    """
    fmt = QTextCharFormat()
    
    # 根据消息类型设置颜色
    color_map = {
        "error": theme_manager.get_color("console_error"),
        "warning": theme_manager.get_color("console_warning"),
        "info": theme_manager.get_color("console_info"),
        "success": theme_manager.get_color("console_success"),
        "debug": theme_manager.get_color("console_debug"),
        "system": theme_manager.get_color("console_system"),
        "normal": theme_manager.get_color("console_text"),
    }
    
    color = color_map.get(msg_type, color_map["normal"])
    fmt.setForeground(QColor(color))
    
    # 错误信息使用粗体
    if msg_type == "error":
        fmt.setFontWeight(QFont.Bold)
    
    return fmt


def detect_message_type(text: str) -> str:
    """自动检测消息类型
    
    根据文本内容自动判断消息类型
    """
    text_lower = text.lower()
    
    # 错误关键词
    error_keywords = ["error", "错误", "exception", "traceback", "failed", "失败"]
    for kw in error_keywords:
        if kw in text_lower:
            return "error"
    
    # 警告关键词
    warning_keywords = ["warning", "警告", "warn"]
    for kw in warning_keywords:
        if kw in text_lower:
            return "warning"
    
    # 成功关键词
    success_keywords = ["success", "成功", "complete", "完成", "done"]
    for kw in success_keywords:
        if kw in text_lower:
            return "success"
    
    # 系统信息（分隔线等）
    if text.strip().startswith("=") or text.strip().startswith("-"):
        return "system"
    
    return "normal"