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
        path: 提取路径,使用点号分隔嵌套层级,例如 "input.img_url"
              支持数组索引访问,例如 "items.0.name" 或 "items[0].name"

    返回:
        指定路径下的值,保留原始类型（列表返回列表,字典返回字典等）

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

    # 如果没有解析到任何key,尝试直接按点号分割
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
        path: 提取路径,使用点号分隔嵌套层级,例如 "input.img_url"
              支持数组索引访问,例如 "items.0.name" 或 "items[0].name"

    返回:
        指定路径下的值,保留原始类型（列表返回列表,字典返回字典等）

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

    # 如果没有解析到任何key,尝试直接按点号分割
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
        file_filter: 文件过滤器,例如 "图片文件 (*.png *.jpg);;文本文件 (*.txt)"
                     默认为 "全部文件 (*)"
        selected_file_path: 已选择的文件路径（通过属性面板的【选取】按钮设置）
    返回:
        选中文件的绝对路径,如果未选择则返回空字符串
    """
    return selected_file_path

file_picker._source = '''def file_picker(file_filter: str = "全部文件 (*)", selected_file_path: str = "") -> str:
    """
    文件选择器节点。
    返回在属性面板中选择的文件绝对路径。
    参数:
        file_filter: 文件过滤器,例如 "图片文件 (*.png *.jpg);;文本文件 (*.txt)"
                     默认为 "全部文件 (*)"
        selected_file_path: 已选择的文件路径（通过属性面板的【选取】按钮设置）
    返回:
        选中文件的绝对路径,如果未选择则返回空字符串
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
        选中文件夹的绝对路径,如果未选择则返回空字符串
    """
    return folder_path

folder_picker._source = '''def folder_picker(folder_path: str = "") -> str:
    """
    文件夹选择器节点。
    返回在属性面板中选择的文件夹绝对路径。
    参数:
        folder_path: 已选择的文件夹路径（通过属性面板的【选取】按钮设置）
    返回:
        选中文件夹的绝对路径,如果未选择则返回空字符串
    """
    return folder_path
'''




def regex_extract(input_text: str = "", pattern: str = "") -> str:
    """
    正则提取节点。
    使用正则表达式从输入文本中提取匹配的内容。

    参数:
        input_text: 需要处理的输入文本
        pattern: 正则表达式模式，用于匹配和提取内容

    返回:
        匹配到的内容，如果有多个匹配则用换行符连接；如果没有匹配则返回空字符串

    示例:
        输入文本："姓名：张三，年龄：25；姓名：李四，年龄：30"
        正则模式："姓名：([\u4e00-\u9fa5]+)"
        输出："张三\n李四"
    """
    import re
    if not input_text or not pattern:
        return ""
    
    try:
        matches = re.findall(pattern, input_text)
        if matches:
            # 如果有捕获组，返回捕获组内容；否则返回整个匹配
            if isinstance(matches[0], tuple):
                # 多个捕获组，返回第一个捕获组
                return chr(10).join(str(m[0]) if m else "" for m in matches)
            return chr(10).join(str(m) for m in matches)
        return ""
    except Exception:
        return ""

regex_extract._source = '''def regex_extract(input_text: str = "", pattern: str = "") -> str:
    """
    正则提取节点。
    使用正则表达式从输入文本中提取匹配的内容。

    参数:
        input_text: 需要处理的输入文本
        pattern: 正则表达式模式，用于匹配和提取内容

    返回:
        匹配到的内容，如果有多个匹配则用换行符连接；如果没有匹配则返回空字符串

    示例:
        输入文本："姓名：张三，年龄：25；姓名：李四，年龄：30"
        正则模式："姓名：([\\u4e00-\\u9fa5]+)"
        输出："张三\\n 李四"
    """
    import re
    if not input_text or not pattern:
        return ""
    
    try:
        matches = re.findall(pattern, input_text)
        if matches:
            # 如果有捕获组，返回捕获组内容；否则返回整个匹配
            if isinstance(matches[0], tuple):
                # 多个捕获组，返回第一个捕获组
                return chr(10).join(str(m[0]) if m else "" for m in matches)
            return chr(10).join(str(m) for m in matches)
        return ""
    except Exception:
        return ""
'''

# ==========================================
# 循环节点函数
# 注意:循环节点是特殊节点,实际执行由 loop_executor 处理
# 这里定义的是节点函数签名,用于在属性面板中显示参数
# ==========================================

def range_loop(最小值:int = 0, 最大值:int = 10, 步长:int = 1) -> list:
    """
    区间循环节点。
    按照指定的整数范围和步长进行循环迭代。

    参数:
        最小值:循环起始值（包含）
        最大值:循环结束值（不包含）
        步长:每次迭代的增量

    返回:
        循环迭代结果列表

    使用说明:
        1. 将需要循环处理的节点添加到循环节点内部
        2. 内部节点通过连接"迭代值"端口获取当前循环值
        3. 循环执行完成后,"汇总结果"端口输出所有迭代结果的列表
    """
    # 实际执行由 loop_executor 处理,这里仅返回范围列表用于预览
    return list(range(最小值,最大值,步长))


range_loop._source = '''def range_loop(最小值:int = 0, 最大值:int = 10, 步长:int = 1) -> list:
    """
    区间循环节点。
    按照指定的整数范围和步长进行循环迭代。

    参数:
        最小值:循环起始值（包含）
        最大值:循环结束值（不包含）
        步长:每次迭代的增量

    返回:
        循环迭代结果列表

    使用说明:
        1. 将需要循环处理的节点添加到循环节点内部
        2. 内部节点通过连接"迭代值"端口获取当前循环值
        3. 循环执行完成后,"汇总结果"端口输出所有迭代结果的列表
    """
    return list(range(最小值,最大值,步长))
'''


def list_loop(列表数据:list = None) -> list:
    """
    List 循环节点。
    遍历列表中的每个元素进行循环迭代。

    参数:
        列表数据:要迭代的列表数据

    返回:
        循环迭代结果列表

    使用说明:
        1. 将需要循环处理的节点添加到循环节点内部
        2. 内部节点通过连接"迭代值"端口获取当前循环元素
        3. 循环执行完成后,"汇总结果"端口输出所有迭代结果的列表
    """
    if 列表数据 is None:
        return []
    return 列表数据


list_loop._source = '''def list_loop(列表数据:list = None) -> list:
    """
    List 循环节点。
    遍历列表中的每个元素进行循环迭代。

    参数:
        列表数据:要迭代的列表数据

    返回:
        循环迭代结果列表

    使用说明:
        1. 将需要循环处理的节点添加到循环节点内部
        2. 内部节点通过连接"迭代值"端口获取当前循环元素
        3. 循环执行完成后,"汇总结果"端口输出所有迭代结果的列表
    """
    if 列表数据 is None:
        return []
    return 列表数据
'''


def 多线程处理(输入列表: list = None, 线程数量: int = 4, 返回顺序: str = "按输入顺序") -> list:
    """
    多线程处理节点。
    使用多线程并发处理列表中的每个元素。

    参数:
        输入列表: 待处理的列表数据
        线程数量: 开启的子线程数（默认 4，自动修正：<=0→1，>列表长度→列表长度）
        返回顺序: "按输入顺序" 或 "按完成顺序"

    返回:
        所有线程完成后的汇总结果列表

    使用说明:
        1. 将"迭代值"端口连接到需要并发处理的节点
        2. 每个线程处理列表中的一个元素
        3. 所有线程完成后，"汇总结果"端口输出完整结果列表
    """
    # 实际执行由 thread_executor 处理，这里仅作占位
    if 输入列表 is None:
        return []
    return 输入列表


多线程处理._source = '''def 多线程处理(输入列表: list = None, 线程数量: int = 4, 返回顺序: str = "按输入顺序") -> list:
    """
    多线程处理节点。
    使用多线程并发处理列表中的每个元素。

    参数:
        输入列表: 待处理的列表数据
        线程数量: 开启的子线程数（默认 4，自动修正：<=0→1，>列表长度→列表长度）
        返回顺序: "按输入顺序" 或 "按完成顺序"

    返回:
        所有线程完成后的汇总结果列表
    """
    if 输入列表 is None:
        return []
    return 输入列表
'''


# 节点代码验证标准示例
NODE_CODE_EXAMPLE = '''\
常用形式:

def my_node(a: int, b: int) -> int:
    """
    节点说明文档。
    """
    return a + b
    
多函数嵌套节点:
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

# 规则:
# 1. 必须定义且仅定义一个顶层函数（def）,但支持嵌套函数复用
# 2. 不填写自定义名称:函数名即为节点名
# 3. 参数即为输入端口,带返回类型注解则有输出端口
# 4. 代码必须是合法的 Python 语法
'''