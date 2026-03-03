"""通用类型转换器模块"""

import json


class TypeConverter:
    """通用类型转换器
    
    提供宽容输入、严格输出的类型转换功能。
    遵循最小惊讶原则，无法转换时返回默认值而非抛出异常。
    """

    @staticmethod
    def to_bool(value) -> bool:
        """转换为布尔值
        
        转换规则:
        - 字符串 "false", "0", "no", "off", "none" (不区分大小写) → False
        - 空值 (None, "", [], {}) → False
        - 数字 0, 0.0 → False
        - 其他情况 → True
        
        Args:
            value: 任意类型的输入值
            
        Returns:
            转换后的布尔值
        """
        # 特殊字符串处理
        if isinstance(value, str):
            lower_val = value.strip().lower()
            if lower_val in ('false', '0', 'no', 'off', 'none'):
                return False
            if lower_val in ('true', '1', 'yes', 'on'):
                return True
        
        # 默认 Python 布尔转换
        return bool(value)

    @staticmethod
    def to_int(value, default: int = 0) -> int:
        """转换为整数
        
        转换规则:
        - 数字类型 (int/float) → 截断取整
        - 布尔类型 → True=1, False=0
        - 字符串 → 尝试解析为数字，失败返回默认值
        - 其他类型 → 返回默认值
        
        Args:
            value: 任意类型的输入值
            default: 无法转换时的默认值，默认为 0
            
        Returns:
            转换后的整数值
        """
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)  # 截断
        if isinstance(value, str):
            try:
                # 先尝试直接转 int
                return int(value.strip())
            except ValueError:
                try:
                    # 再尝试转 float 后取整
                    return int(float(value.strip()))
                except ValueError:
                    return default
        return default

    @staticmethod
    def to_float(value, default: float = 0.0) -> float:
        """转换为浮点数
        
        转换规则:
        - 数字类型 (int/float) → 直接转换
        - 布尔类型 → True=1.0, False=0.0
        - 字符串 → 尝试解析为 float，失败返回默认值
        - 其他类型 → 返回默认值
        
        Args:
            value: 任意类型的输入值
            default: 无法转换时的默认值，默认为 0.0
            
        Returns:
            转换后的浮点数值
        """
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return default
        return default

    @staticmethod
    def to_string(value, default: str = "") -> str:
        """转换为字符串
        
        转换规则:
        - None → 空字符串
        - 其他类型 → 使用 str() 转换
        
        Args:
            value: 任意类型的输入值
            default: 无法转换时的默认值，默认为空字符串
            
        Returns:
            转换后的字符串值
        """
        if value is None:
            return default
        return str(value)

    @staticmethod
    def to_list(value, default: list = None) -> list:
        """转换为列表
        
        转换规则:
        - None → 空列表
        - list/tuple/set → 直接转换
        - dict → 转为键值对列表
        - 字符串 → 尝试 JSON 解析，失败则逗号分割，再失败则单元素列表
        - 其他标量类型 → 包装为单元素列表
        
        Args:
            value: 任意类型的输入值
            default: 无法转换时的默认值，默认为空列表
            
        Returns:
            转换后的列表值
        """
        if default is None:
            default = []

        if value is None:
            return default
        if isinstance(value, list):
            return value
        if isinstance(value, (tuple, set)):
            return list(value)
        if isinstance(value, dict):
            return list(value.items())
        if isinstance(value, str):
            # 尝试 JSON 解析
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # 尝试逗号分割
            if ',' in value:
                return [item.strip() for item in value.split(',')]
            # 单元素列表
            return [value]
        # 其他类型包装为列表
        return [value]

    @staticmethod
    def to_dict(value, default: dict = None) -> dict:
        """转换为字典
        
        转换规则:
        - None → 空字典
        - dict → 原样返回
        - 字符串 → 尝试 JSON 解析，失败则尝试键值对格式，再失败返回默认值
        - 列表 → 如果是键值对列表则转换，否则转为索引字典
        - 其他类型 → 返回默认值
        
        Args:
            value: 任意类型的输入值
            default: 无法转换时的默认值，默认为空字典
            
        Returns:
            转换后的字典值
        """
        if default is None:
            default = {}

        if value is None:
            return default
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            # 尝试 JSON 解析
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
            # 尝试键值对格式 (a=1,b=2)
            try:
                result = {}
                for pair in value.split(','):
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        result[k.strip()] = v.strip()
                if result:
                    return result
            except Exception:
                pass
            return default
        if isinstance(value, list):
            # 检查是否为键值对列表
            if all(isinstance(item, (tuple, list)) and len(item) == 2 for item in value):
                return dict(value)
            # 否则转为索引字典
            return {i: v for i, v in enumerate(value)}
        return default
