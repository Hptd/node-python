"""应用配置"""

import json
import os
from pathlib import Path
from typing import Dict, Any

from utils.constants import STORAGE_DIR, SETTINGS_FILE


def get_settings_path() -> Path:
    """获取设置文件路径"""
    import sys
    if hasattr(sys, '_MEIPASS'):  # PyInstaller打包后的环境
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path.cwd()
    
    settings_dir = base_dir / STORAGE_DIR
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / SETTINGS_FILE


class Settings:
    """应用设置"""
    
    def __init__(self):
        self._settings = self._load_default_settings()
        self.load()
    
    def _load_default_settings(self) -> Dict[str, Any]:
        """加载默认设置"""
        return {
            "window": {
                "width": 1000,
                "height": 700,
                "x": None,
                "y": None,
                "maximized": False
            },
            "graphics": {
                "zoom_speed": 1.15,
                "grid_enabled": False,
                "grid_size": 20,
                "snap_to_grid": False
            },
            "nodes": {
                "auto_save_custom_nodes": True,
                "auto_load_custom_nodes": True,
                "confirm_node_deletion": True
            },
            "execution": {
                "auto_run_on_change": False,
                "show_execution_time": True,
                "stop_on_error": True
            },
            "ui": {
                "theme": "dark",
                "font_size": 10,
                "language": "zh_CN",
                "show_tooltips": True
            },
            "logging": {
                "log_dir": "output_logs",
                "log_filename": "output_log.txt",
                "enabled": True
            },
            "recent_files": [],
            "version": "1.0.0"
        }
    
    def load(self) -> bool:
        """从文件加载设置"""
        try:
            settings_file = get_settings_path()
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                # 合并设置，保留默认值
                self._merge_settings(self._settings, loaded_settings)
                print(f"已加载设置文件: {settings_file}")
                return True
            else:
                print("未找到设置文件，使用默认设置")
                return False
        except Exception as e:
            print(f"加载设置失败: {e}")
            return False
    
    def save(self) -> bool:
        """保存设置到文件"""
        try:
            settings_file = get_settings_path()
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            print(f"已保存设置到: {settings_file}")
            return True
        except Exception as e:
            print(f"保存设置失败: {e}")
            return False
    
    def _merge_settings(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """递归合并设置"""
        for key, value in source.items():
            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    self._merge_settings(target[key], value)
                else:
                    target[key] = value
            else:
                target[key] = value
    
    def get(self, key: str, default=None) -> Any:
        """获取设置值"""
        keys = key.split('.')
        value = self._settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """设置值"""
        keys = key.split('.')
        settings = self._settings
        
        # 导航到目标字典
        for i, k in enumerate(keys[:-1]):
            if k not in settings:
                settings[k] = {}
            settings = settings[k]
        
        # 设置值
        settings[keys[-1]] = value
    
    def add_recent_file(self, filepath: str) -> None:
        """添加最近使用的文件"""
        recent_files = self.get("recent_files", [])
        
        # 移除重复项
        if filepath in recent_files:
            recent_files.remove(filepath)
        
        # 添加到开头
        recent_files.insert(0, filepath)
        
        # 限制数量
        if len(recent_files) > 10:
            recent_files = recent_files[:10]
        
        self.set("recent_files", recent_files)
        self.save()
    
    def get_recent_files(self) -> List[str]:
        """获取最近使用的文件列表"""
        return self.get("recent_files", [])
    
    def clear_recent_files(self) -> None:
        """清除最近使用的文件列表"""
        self.set("recent_files", [])
        self.save()


# 全局设置实例
settings = Settings()