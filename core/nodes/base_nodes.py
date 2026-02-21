"""基础节点函数定义"""

def node_print(data):
    """
    打印输出节点。
    将输入的数据打印到下方的控制台中。
    """
    print(data)


def const_bool(value: bool = True) -> bool:
    """
    布尔常量节点。
    返回一个布尔值。
    """
    return value


def const_int(value: int = 0) -> int:
    """
    整数常量节点。
    返回一个整数值。
    """
    return value


def const_float(value: float = 0.0) -> float:
    """
    浮点数常量节点。
    返回一个浮点数值。
    """
    return value


def const_string(value: str = "") -> str:
    """
    字符串常量节点。
    返回一个字符串值。
    """
    return value


def const_list(value: list = None) -> list:
    """
    列表常量节点。
    返回一个列表值。
    """
    if value is None:
        return []
    return value


def const_dict(value: dict = None) -> dict:
    """
    字典常量节点。
    返回一个字典值。
    """
    if value is None:
        return {}
    return value


def extract_data(data: dict, path: str = "") -> any:
    """
    数据提取节点。
    从输入的结构化数据（字典/JSON）中提取指定路径的字段内容。
    
    参数:
        data: 原始的结构化数据（字典类型）
        path: 提取路径，使用点号分隔嵌套层级，例如 "input.img_url"
              支持数组索引访问，例如 "items.0.name" 或 "items[0].name"
    
    返回:
        指定路径下的值，保留原始类型（列表返回列表，字典返回字典等）
    
    示例:
        输入数据: {"input": {"img_url": ["url1", "url2"]}}
        路径: "input.img_url"
        输出: ["url1", "url2"]
    """
    if not data or not path:
        return None
    
    if not isinstance(data, dict):
        try:
            import json
            data = json.loads(data) if isinstance(data, str) else data
        except Exception:
            return None
    
    # 解析路径（支持点号和方括号两种格式）
    import re
    # 将 "items[0].name" 或 "items.0.name" 统一处理
    tokens = re.findall(r'([^\.\[\]]+)|\[(\d+)\]', path)
    keys = []
    for token in tokens:
        if token[0]:  # 字段名
            keys.append(token[0])
        elif token[1]:  # 数组索引
            keys.append(int(token[1]))
    
    # 如果没有解析到任何key，尝试直接按点号分割
    if not keys:
        keys = path.split('.')
    
    # 遍历路径
    current = data
    try:
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                if isinstance(key, int) and 0 <= key < len(current):
                    current = current[key]
                else:
                    return None
            else:
                return None
            if current is None:
                return None
        return current
    except Exception:
        return None


def type_test(data) -> None:
    """
    数据类型检测节点。
    检测并打印输入数据的类型信息。
    """
    print(type(data))

# 节点代码验证标准示例
NODE_CODE_EXAMPLE = '''\
def my_node(a: int, b: int) -> int:
    """
    节点说明文档。
    """
    return a + b

# 规则：
# 1. 必须定义且仅定义一个顶层函数（def）
# 2. 不填写自定义名称：函数名即为节点名
# 3. 参数即为输入端口，带返回类型注解则有输出端口
# 4. 代码必须是合法的 Python 语法
'''