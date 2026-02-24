"""节点搜索匹配工具模块"""

import re
from typing import List, Tuple

# 尝试导入 pypinyin，如果不存在则使用简化版本
try:
    from pypinyin import lazy_pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False


def get_pinyin_initials(text: str) -> str:
    """获取中文文本的拼音首字母
    
    例如："浮点数" -> "fds"
    """
    if not text:
        return ""
    
    if HAS_PYPINYIN:
        # 使用 pypinyin 获取每个字符的首字母
        initials = lazy_pinyin(text, style=Style.FIRST_LETTER)
        return ''.join(initials).lower()
    else:
        # 简化版本：只提取ASCII字母，中文返回空
        result = []
        for char in text:
            if 'a' <= char.lower() <= 'z':
                result.append(char.lower())
        return ''.join(result)


def get_full_pinyin(text: str) -> str:
    """获取中文文本的完整拼音（小写）
    
    例如："浮点数" -> "fudianshu"
    """
    if not text:
        return ""
    
    if HAS_PYPINYIN:
        pinyin_list = lazy_pinyin(text, style=Style.NORMAL)
        return ''.join(pinyin_list).lower()
    else:
        return ""


def is_chinese_char(char: str) -> bool:
    """判断字符是否为中文字符"""
    return '\u4e00' <= char <= '\u9fff'


def contains_chinese(text: str) -> bool:
    """判断文本是否包含中文"""
    return any(is_chinese_char(c) for c in text)


def fuzzy_match_initials(search_text: str, target_text: str) -> bool:
    """拼音首字母模糊匹配
    
    支持连续首字母匹配：
    - "浮点数" 可以匹配: "fds", "fd", "f", "fud", "fudian" 等
    
    Args:
        search_text: 搜索输入文本
        target_text: 目标节点名称
        
    Returns:
        是否匹配
    """
    if not search_text or not target_text:
        return False
    
    search_lower = search_text.lower()
    target_lower = target_text.lower()
    
    # 1. 直接包含匹配（原始文本）
    if search_lower in target_lower:
        return True
    
    # 2. 如果目标是中文，进行拼音匹配
    if contains_chinese(target_text):
        # 获取拼音首字母
        initials = get_pinyin_initials(target_text)
        if search_lower in initials:
            return True
        
        # 获取完整拼音
        full_pinyin = get_full_pinyin(target_text)
        if search_lower in full_pinyin:
            return True
        
        # 首字母顺序匹配：如输入 "fd" 匹配 "浮点数"（f-d-s 的前两个）
        # 检查搜索文本是否是首字母的前缀
        if initials.startswith(search_lower):
            return True
    
    return False


def fuzzy_match_english(search_text: str, target_text: str) -> bool:
    """英文模糊字母匹配
    
    支持子序列匹配：
    - "float" 可以匹配: "float", "flo", "flt", "fot", "ft" 等
    - 只要搜索文本的字符按顺序出现在目标文本中即可
    
    Args:
        search_text: 搜索输入文本
        target_text: 目标节点名称
        
    Returns:
        是否匹配
    """
    if not search_text or not target_text:
        return False
    
    search_lower = search_text.lower()
    target_lower = target_text.lower()
    
    # 1. 直接包含匹配
    if search_lower in target_lower:
        return True
    
    # 2. 子序列匹配（按顺序出现的字符）
    # 例如 "fot" 匹配 "float": f->l->o->a->t，f、o、t 按顺序出现
    search_idx = 0
    for char in target_lower:
        if search_idx < len(search_lower) and char == search_lower[search_idx]:
            search_idx += 1
    
    return search_idx == len(search_lower)


def match_node(search_text: str, node_name: str) -> Tuple[bool, int]:
    """综合匹配节点名称
    
    结合拼音匹配和英文模糊匹配，返回是否匹配及匹配优先级
    
    匹配优先级（数值越小优先级越高）：
    1. 完全匹配（优先级 0）
    2. 前缀匹配（优先级 1）
    3. 包含匹配（优先级 2）
    4. 拼音首字母前缀匹配（优先级 3）
    5. 拼音包含匹配（优先级 4）
    6. 英文子序列匹配（优先级 5）
    
    Args:
        search_text: 搜索输入文本
        node_name: 节点名称
        
    Returns:
        (是否匹配, 优先级)
    """
    if not search_text:
        return True, 0  # 空搜索显示所有
    
    if not node_name:
        return False, 100
    
    search_lower = search_text.lower()
    node_lower = node_name.lower()
    
    # 1. 完全匹配
    if search_lower == node_lower:
        return True, 0
    
    # 2. 前缀匹配
    if node_lower.startswith(search_lower):
        return True, 1
    
    # 3. 包含匹配
    if search_lower in node_lower:
        return True, 2
    
    # 4. 中文拼音匹配
    if contains_chinese(node_name):
        initials = get_pinyin_initials(node_name)
        full_pinyin = get_full_pinyin(node_name)
        
        # 拼音首字母前缀匹配
        if initials.startswith(search_lower):
            return True, 3
        
        # 拼音首字母包含匹配
        if search_lower in initials:
            return True, 4
        
        # 完整拼音前缀匹配
        if full_pinyin.startswith(search_lower):
            return True, 3
        
        # 完整拼音包含匹配
        if search_lower in full_pinyin:
            return True, 4
    
    # 5. 英文子序列匹配
    if fuzzy_match_english(search_text, node_name):
        return True, 5
    
    return False, 100


def search_nodes(search_text: str, node_names: List[str]) -> List[str]:
    """搜索节点并按匹配度排序
    
    Args:
        search_text: 搜索输入文本
        node_names: 所有节点名称列表
        
    Returns:
        匹配的节点名称列表，按匹配优先级排序
    """
    if not search_text:
        return node_names
    
    matched = []
    for name in node_names:
        is_match, priority = match_node(search_text, name)
        if is_match:
            matched.append((name, priority))
    
    # 按优先级排序
    matched.sort(key=lambda x: x[1])
    return [name for name, _ in matched]


if __name__ == "__main__":
    # 测试代码
    test_cases = [
        ("fds", "浮点数"),  # 拼音首字母
        ("fd", "浮点数"),   # 拼音首字母前缀
        ("f", "浮点数"),    # 单字母
        ("fudian", "浮点数"),  # 完整拼音前缀
        ("float", "float"),   # 英文完全匹配
        ("flo", "float"),     # 英文前缀
        ("fot", "float"),     # 英文子序列
        ("flt", "float"),     # 英文子序列
        ("ft", "float"),      # 英文子序列
        ("打印", "打印节点"),  # 中文包含
        ("dy", "打印节点"),   # 拼音首字母
    ]
    
    print("测试搜索匹配功能:")
    print("-" * 50)
    for search, target in test_cases:
        is_match, priority = match_node(search, target)
        status = "✓" if is_match else "✗"
        print(f"{status} 搜索 '{search}' -> '{target}' (优先级: {priority})")
