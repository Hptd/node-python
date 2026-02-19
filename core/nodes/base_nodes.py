"""基础节点函数定义"""

def node_print(data):
    """
    打印输出节点。
    将输入的数据打印到下方的控制台中。
    """
    print(f"执行结果: {data}")


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


# 节点代码验证标准示例
NODE_CODE_EXAMPLE = '''\
def my_node(a: int, b: int) -> int:
    """
    节点说明文档。
    """
    return a + b

# 规则：
# 1. 必须定义且仅定义一个顶层函数（def）
# 2. 函数名即为节点名
# 3. 参数即为输入端口，带返回类型注解则有输出端口
# 4. 代码必须是合法的 Python 语法
'''