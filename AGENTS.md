# 简易中文节点编辑器 - AGENTS.md

## 项目概述

这是一个基于 PySide6 的图形化节点编辑器，允许用户通过拖拽和连接节点来创建可执行的数据流图。项目采用纯 Python 开发，支持自定义节点函数、持久化存储和实时执行。

### 核心特性

- **可视化节点编辑**：拖拽式界面，支持节点连接、选择和移动
- **动态参数输入**：选中节点后可在右侧面板直接编辑参数值
- **拓扑排序执行**：自动确定节点执行顺序
- **自定义节点**：支持通过 Python 代码动态创建新节点
- **JSON 持久化**：图表可保存为 JSON 文件，支持导入导出

## 技术栈

- **GUI 框架**：PySide6 >= 6.5.0
- **语言**：Python 3.10+
- **架构**：MVC 模式，模块化设计

## 项目结构

```
node-python/
├── main.py                     # 应用入口，初始化 Qt 应用和主窗口
├── requirements.txt            # 依赖：PySide6>=6.5.0
├── config/
│   └── settings.py            # 应用配置管理（窗口状态、用户偏好等）
├── core/
│   ├── nodes/
│   │   ├── base_nodes.py      # 内置节点函数（加法、打印、常量等）
│   │   └── node_library.py    # 节点库管理，分类存储
│   ├── graphics/
│   │   ├── simple_node_item.py    # 图形节点类
│   │   ├── port_item.py           # 输入/输出端口
│   │   ├── connection_item.py     # 连接线
│   │   └── node_graphics_view.py  # 画布视图（缩放、平移）
│   └── engine/
│       └── graph_executor.py  # 拓扑排序和执行引擎
├── ui/
│   ├── main_window.py         # 主窗口，工具栏和面板布局
│   ├── dialogs/
│   │   └── custom_node_dialog.py  # 自定义节点编辑器
│   └── widgets/
│       └── draggable_node_tree.py # 可拖拽节点列表
├── storage/
│   ├── custom_node_storage.py # 自定义节点持久化
│   └── graph_storage.py       # 图表 JSON 保存/加载
└── utils/
    ├── constants.py           # 颜色、尺寸等常量定义
    └── console_stream.py      # 控制台输出重定向
```

## 节点系统详解

### 内置节点

位于 `core/nodes/base_nodes.py`：

| 节点名 | 类型 | 参数 | 说明 |
|-------|------|------|------|
| 加法节点 | 运算 | a, b: int | 返回两数之和 |
| 打印节点 | 输出 | data: any | 打印到控制台 |
| 布尔 | 常量 | value: bool | 返回布尔值 |
| 整数 | 常量 | value: int | 返回整数值 |
| 浮点数 | 常量 | value: float | 返回浮点数值 |
| 字符串 | 常量 | value: str | 返回字符串值 |
| 列表 | 常量 | value: list | 返回列表值 |
| 字典 | 常量 | value: dict | 返回字典值 |

### 节点函数规范

创建自定义节点的代码必须符合以下规范：

```python
def 节点名(参数1: 类型, 参数2: 类型) -> 返回类型:
    """
    节点说明文档（显示在属性面板）。
    """
    return 结果
```

**规则**：
1. 必须定义且仅定义一个顶层函数
2. 函数名即为节点名
3. 参数类型决定输入控件的类型
4. 返回类型注解决定是否有输出端口

### 参数输入系统

位于 `ui/main_window.py` 的 `_setup_param_inputs()` 方法：

选中节点时，右侧面板会根据参数类型自动生成对应的输入控件：
- `bool` → QCheckBox（复选框）
- `int` → QSpinBox（整数输入）
- `float` → QDoubleSpinBox（浮点数输入）
- 其他 → QLineEdit（文本输入）

参数值存储在节点的 `param_values` 字典中，执行时优先使用。

## 执行引擎

位于 `core/engine/graph_executor.py`：

1. **拓扑排序**：根据节点连接关系计算执行顺序
2. **参数解析**：每个输入端口优先使用连接值，否则使用预设值
3. **函数调用**：使用 `func(**kwargs)` 方式调用
4. **结果传递**：节点结果通过端口连接传递给下游节点

## 存储系统

### 设置存储

- **位置**：`.node-python/settings.json`
- **内容**：窗口状态、图形设置、执行选项等
- **类**：`config/settings.py` 中的 `Settings` 类

### 自定义节点存储

- **位置**：`.node-python/custom_nodes.json`
- **格式**：包含源代码、分类、创建时间等元数据
- **自动加载**：应用启动时自动加载，退出时自动保存

### 图表存储

- **格式**：JSON
- **内容**：节点列表（含位置和参数值）、连接关系
- **操作**：通过工具栏"保存"/"加载"按钮操作

## 运行和构建

### 开发运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行应用
python main.py
```

### 打包为可执行文件

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name node-editor main.py
```

打包后，自定义节点和设置将保存在可执行文件同级目录的 `.node-python` 文件夹中。

## 开发约定

### 添加内置节点

1. 在 `core/nodes/base_nodes.py` 中添加函数
2. 在 `core/nodes/node_library.py` 的 `NODE_LIBRARY_CATEGORIZED` 中注册

### 修改界面样式

在 `utils/constants.py` 中修改颜色常量，例如：
- `COLOR_NODE_BG`：节点背景色
- `COLOR_INPUT_PORT`：输入端口颜色
- `COLOR_OUTPUT_PORT`：输出端口颜色

### 扩展功能

- **新节点类型**：修改 `base_nodes.py` 和 `node_library.py`
- **新存储格式**：在 `storage/` 中添加新模块
- **新对话框**：在 `ui/dialogs/` 中创建

## 快捷键和操作

| 操作 | 说明 |
|------|------|
| 拖拽节点 | 从左侧节点库拖拽到画布 |
| 连接节点 | 从输出端口拖拽到输入端口 |
| 选中节点 | 单击节点 |
| 框选多选 | 左键拖动框选 |
| 删除节点 | 选中后按 Delete 键 |
| 平移视图 | 按住中键拖动 |
| 缩放视图 | 滚轮 |

## 最近变更

- 新增常量节点类型（布尔、整数、浮点数、字符串、列表、字典）
- 支持在属性面板直接编辑节点参数值
- 图表保存为 JSON 文件，支持完整导入导出
- 参数值随图表一起保存和加载
