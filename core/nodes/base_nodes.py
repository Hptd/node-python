"""基础节点函数定义"""


def node_print(data):
    """
    打印输出节点。
    将输入的数据打印到下方的控制台中。
    """
    print(data)


node_print._source = '''def node_print(data):
    """
    打印输出节点。
    将输入的数据打印到下方的控制台中。
    """
    print(data)
'''


def const_bool(value: bool = True) -> bool:
    """
    布尔常量节点。
    返回一个布尔值。
    """
    return value


const_bool._source = '''def const_bool(value: bool = True) -> bool:
    """
    布尔常量节点。
    返回一个布尔值。
    """
    return value
'''


def const_int(value: int = 0) -> int:
    """
    整数常量节点。
    返回一个整数值。
    """
    return value


const_int._source = '''def const_int(value: int = 0) -> int:
    """
    整数常量节点。
    返回一个整数值。
    """
    return value
'''


def const_float(value: float = 0.0) -> float:
    """
    浮点数常量节点。
    返回一个浮点数值。
    """
    return value


const_float._source = '''def const_float(value: float = 0.0) -> float:
    """
    浮点数常量节点。
    返回一个浮点数值。
    """
    return value
'''


def const_string(value: str = "") -> str:
    """
    字符串常量节点。
    返回一个字符串值。
    """
    return value


const_string._source = '''def const_string(value: str = "") -> str:
    """
    字符串常量节点。
    返回一个字符串值。
    """
    return value
'''


def const_list(value: list = None) -> list:
    """
    列表常量节点。
    返回一个列表值。
    """
    if value is None:
        return []
    return value


const_list._source = '''def const_list(value: list = None) -> list:
    """
    列表常量节点。
    返回一个列表值。
    """
    if value is None:
        return []
    return value
'''


def const_dict(value: dict = None) -> dict:
    """
    字典常量节点。
    返回一个字典值。
    """
    if value is None:
        return {}
    return value


const_dict._source = '''def const_dict(value: dict = None) -> dict:
    """
    字典常量节点。
    返回一个字典值。
    """
    if value is None:
        return {}
    return value
'''

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

extract_data._source = '''def extract_data(data: dict, path: str = "") -> any:
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
    tokens = re.findall(r'([^\\.\\[\\]]+)|\\[(\\d+)\\]', path)
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
'''

def type_test(data) -> None:
    """
    数据类型检测节点。
    检测并打印输入数据的类型信息。
    """
    print(type(data))

type_test._source = '''def type_test(data) -> None:
    """
    数据类型检测节点。
    检测并打印输入数据的类型信息。
    """
    print(type(data))
'''

def file_picker(file_filter: str = "全部文件 (*)", selected_file_path: str = "") -> str:
    """
    文件选择器节点。
    返回在属性面板中选择的文件绝对路径。
    参数:
        file_filter: 文件过滤器，例如 "图片文件 (*.png *.jpg);;文本文件 (*.txt)"
                     默认为 "全部文件 (*)"
        selected_file_path: 已选择的文件路径（通过属性面板的【选取】按钮设置）
    返回:
        选中文件的绝对路径，如果未选择则返回空字符串
    """
    return selected_file_path

file_picker._source = '''def file_picker(file_filter: str = "全部文件 (*)", selected_file_path: str = "") -> str:
    """
    文件选择器节点。
    返回在属性面板中选择的文件绝对路径。
    参数:
        file_filter: 文件过滤器，例如 "图片文件 (*.png *.jpg);;文本文件 (*.txt)"
                     默认为 "全部文件 (*)"
        selected_file_path: 已选择的文件路径（通过属性面板的【选取】按钮设置）
    返回:
        选中文件的绝对路径，如果未选择则返回空字符串
    """
    return selected_file_path
'''

def folder_picker(folder_path: str = "") -> str:
    """
    文件夹选择器节点。
    返回在属性面板中选择的文件夹绝对路径。
    参数:
        folder_path: 已选择的文件夹路径（通过属性面板的【选取】按钮设置）
    返回:
        选中文件夹的绝对路径，如果未选择则返回空字符串
    """
    return folder_path

folder_picker._source = '''def folder_picker(folder_path: str = "") -> str:
    """
    文件夹选择器节点。
    返回在属性面板中选择的文件夹绝对路径。
    参数:
        folder_path: 已选择的文件夹路径（通过属性面板的【选取】按钮设置）
    返回:
        选中文件夹的绝对路径，如果未选择则返回空字符串
    """
    return folder_path
'''


# 节点代码验证标准示例
NODE_CODE_EXAMPLE = '''\
常用形式：

def my_node(a: int, b: int) -> int:
    """
    节点说明文档。
    """
    return a + b
    
多函数嵌套节点：
def main_fuction():
    """
    主函数
    """
    
    def add():
        """
        内部嵌套函数
        """
        return 1 + 1

    return add()

# 规则：
# 1. 必须定义且仅定义一个顶层函数（def），但支持嵌套函数复用
# 2. 不填写自定义名称：函数名即为节点名
# 3. 参数即为输入端口，带返回类型注解则有输出端口
# 4. 代码必须是合法的 Python 语法
'''