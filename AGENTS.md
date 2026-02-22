# 简易中文节点编辑器 - AGENTS.md

## 项目概述

这是一个基于 PySide6 的图形化节点编辑器，允许用户通过拖拽和连接节点来创建可执行的数据流图。项目采用纯 Python 开发，支持自定义节点函数、持久化存储和实时执行。

### 核心特性

- **可视化节点编辑**：拖拽式界面，支持节点连接、选择和移动
- **动态参数输入**：选中节点后可在右侧面板直接编辑参数值
- **节点组功能**：支持多节点组合、解组、嵌套编辑
- **智能搜索**：支持拼音首字母、模糊匹配搜索节点
- **拓扑排序执行**：自动确定节点执行顺序
- **自定义节点**：支持通过 Python 代码动态创建新节点
- **主题切换**：支持暗黑/明亮模式切换
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
│   └── settings.py            # 应用配置管理（窗口状态、用户偏好、主题等）
├── core/
│   ├── nodes/
│   │   ├── base_nodes.py      # 内置节点函数（打印、常量、数据提取等）
│   │   └── node_library.py    # 节点库管理，分类存储
│   ├── graphics/
│   │   ├── simple_node_item.py    # 图形节点类
│   │   ├── port_item.py           # 输入/输出端口
│   │   ├── connection_item.py     # 连接线
│   │   ├── node_graphics_view.py  # 画布视图（缩放、平移）
│   │   └── node_group.py          # 节点组功能（组合、解组、嵌套）
│   └── engine/
│       ├── graph_executor.py      # 拓扑排序和执行引擎
│       └── embedded_executor.py   # 嵌入式 Python 执行器
├── ui/
│   ├── main_window.py         # 主窗口，工具栏和面板布局
│   ├── dialogs/
│   │   ├── custom_node_dialog.py      # 自定义节点编辑器
│   │   ├── ai_node_generator_dialog.py # AI 节点生成器
│   │   ├── package_manager_dialog.py  # 依赖包管理器
│   │   └── category_dialog.py         # 新建分类对话框
│   └── widgets/
│       ├── draggable_node_tree.py # 可拖拽节点列表
│       └── node_search_menu.py    # 节点搜索菜单（瀑布流展示）
├── storage/
│   ├── custom_node_storage.py # 自定义节点持久化
│   └── graph_storage.py       # 图表 JSON 保存/加载
└── utils/
    ├── constants.py           # 颜色、尺寸等常量定义
    ├── console_stream.py      # 控制台输出重定向
    ├── theme_manager.py       # 主题管理器（黑白模式切换）
    └── node_search.py         # 节点搜索匹配（拼音、模糊匹配）
```

## 节点系统详解

### 内置节点

位于 `core/nodes/base_nodes.py`：

| 节点名 | 类型 | 参数 | 说明 |
|-------|------|------|------|
| 打印节点 | 输出 | data: any | 打印到控制台 |
| 布尔 | 常量 | value: bool = True | 返回布尔值 |
| 整数 | 常量 | value: int = 0 | 返回整数值 |
| 浮点数 | 常量 | value: float = 0.0 | 返回浮点数值 |
| 字符串 | 常量 | value: str = "" | 返回字符串值 |
| 列表 | 常量 | value: list = None | 返回列表值 |
| 字典 | 常量 | value: dict = None | 返回字典值 |
| 数据提取 | 提取 | data: dict, path: str = "" | 从字典中提取指定路径的数据 |
| 数据类型检测 | Debug | data: any | 检测并打印输入数据的类型 |

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
- `list` → JSON 格式文本输入框
- `dict` → JSON 格式文本输入框
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
- **内容**：节点列表（含位置和参数值）、连接关系、节点组信息
- **操作**：通过工具栏"保存"/"加载"按钮操作

## 节点组系统

位于 `core/graphics/node_group.py`：

- **NodeGroup 类**：节点组图形项
- **组合功能**：将多个节点合并为一个组
- **解组功能**：将组解散为独立节点
- **嵌套支持**：支持组内创建子组
- **编辑模式**：双击组进入/退出组内编辑

### 组操作

1. **创建组**：选中多个节点 → 右键 → "创建组"
2. **进入组**：双击节点组
3. **退出组**：组内右键 → "退出组" 或双击组外区域
4. **解组**：右键点击组 → "解组"

## 智能搜索系统

位于 `utils/node_search.py` 和 `ui/widgets/node_search_menu.py`：

### 搜索匹配算法

- **完全匹配**（优先级 0）：文本完全一致
- **前缀匹配**（优先级 1）：节点名以搜索文本开头
- **包含匹配**（优先级 2）：节点名包含搜索文本
- **拼音首字母前缀**（优先级 3）：如"fd"匹配"浮点数"
- **拼音包含匹配**（优先级 4）：如"fds"匹配"浮点数"
- **英文子序列匹配**（优先级 5）：如"fot"匹配"float"

### 使用方式

- 在画布空白处右键打开搜索菜单
- 输入搜索文本实时过滤节点
- 支持中文拼音首字母搜索

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

在 `utils/theme_manager.py` 中修改主题颜色：
- `THEMES['dark']`：暗黑模式配色
- `THEMES['light']`：明亮模式配色
- 节点颜色：`node_bg`, `node_border`, `node_text`
- 端口颜色：`input_port`, `output_port`
- 连接线颜色：`connection`, `connection_selected`

### 扩展功能

- **新节点类型**：修改 `base_nodes.py` 和 `node_library.py`
- **新存储格式**：在 `storage/` 中添加新模块
- **新对话框**：在 `ui/dialogs/` 中创建
- **节点组功能**：在 `core/graphics/node_group.py` 中扩展
- **搜索功能**：在 `utils/node_search.py` 中修改匹配算法

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
| 创建组 | 选中多个节点后右键 → "创建组" |
| 进入/退出组 | 双击节点组 |
| 解组 | 右键点击组 → "解组" |
| 打开搜索菜单 | 右键点击画布空白处 |

## 最近变更

- 新增节点组功能：支持多节点组合、解组、嵌套编辑
- 新增智能搜索：支持拼音首字母、模糊匹配搜索节点
- 新增主题切换：支持暗黑/明亮模式切换
- 新增 AI 节点生成器：自然语言描述生成节点代码
- 新增依赖包管理器：管理嵌入式 Python 环境的第三方库
- 新增数据提取节点：从字典/JSON 中提取指定路径数据
- 新增数据类型检测节点：检测输入数据的类型
- 常量节点类型（布尔、整数、浮点数、字符串、列表、字典）
- 支持在属性面板直接编辑节点参数值
- 图表保存为 JSON 文件，支持完整导入导出
- 参数值随图表一起保存和加载
