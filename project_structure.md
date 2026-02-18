# 项目结构设计文档

## 项目概述

简易中文节点编辑器 - 基于 PySide6 的图形化节点编辑器，支持自定义 Python 节点函数、参数输入、JSON 持久化存储。

## 目录结构

```
node-python/
├── main.py                     # 应用入口，初始化 Qt 应用和主窗口
├── requirements.txt            # 依赖：PySide6>=6.5.0
├── README.md                   # 项目说明文档
├── AGENTS.md                   # AI 助手上下文文档
├── project_structure.md        # 本文件，项目结构设计
├── config/                     # 配置文件
│   ├── __init__.py
│   └── settings.py            # 应用配置管理（窗口状态、用户偏好等）
├── core/                       # 核心模块
│   ├── __init__.py
│   ├── nodes/                 # 节点相关
│   │   ├── __init__.py
│   │   ├── base_nodes.py      # 内置节点函数（加法、打印、常量等）
│   │   └── node_library.py    # 节点库管理，分类存储
│   ├── graphics/              # 图形组件
│   │   ├── __init__.py
│   │   ├── port_item.py       # 输入/输出端口
│   │   ├── connection_item.py # 节点间连接线
│   │   ├── simple_node_item.py# 图形节点类（含参数值存储）
│   │   └── node_graphics_view.py# 画布视图（缩放、平移）
│   └── engine/                # 执行引擎
│       ├── __init__.py
│       └── graph_executor.py  # 拓扑排序和执行逻辑
├── ui/                         # 用户界面
│   ├── __init__.py
│   ├── main_window.py         # 主窗口，工具栏和面板布局
│   ├── dialogs/               # 对话框
│   │   ├── __init__.py
│   │   ├── custom_node_dialog.py  # 自定义节点代码编辑器
│   │   └── category_dialog.py     # 新建分类对话框
│   └── widgets/               # 自定义控件
│       ├── __init__.py
│       └── draggable_node_tree.py # 可拖拽节点列表
├── storage/                    # 存储模块
│   ├── __init__.py
│   ├── custom_node_storage.py # 自定义节点持久化存储
│   └── graph_storage.py       # 图表 JSON 保存/加载
└── utils/                      # 工具函数
    ├── __init__.py
    ├── constants.py           # 颜色、尺寸、文件路径常量
    └── console_stream.py      # 控制台输出重定向
```

## 核心模块说明

### 1. 配置模块 (config/)

**settings.py**
- 应用设置管理类 `Settings`
- 支持设置项：窗口状态、图形选项、节点选项、执行选项、UI 主题
- 自动保存和加载设置到 `.node-python/settings.json`
- 支持 PyInstaller 打包后的路径处理

### 2. 核心模块 (core/)

#### 2.1 节点模块 (nodes/)

**base_nodes.py**
- 内置节点函数定义
- 常量节点：布尔、整数、浮点数、字符串、列表、字典
- 运算节点：加法节点
- 输出节点：打印节点
- `NODE_CODE_EXAMPLE`：自定义节点代码示例模板

**node_library.py**
- `NODE_LIBRARY_CATEGORIZED`：分类存储的节点库
- `LOCAL_NODE_LIBRARY`：扁平索引，方便查找
- `CUSTOM_CATEGORIES`：用户自定义分类列表
- 函数：`add_node_to_library()`、`remove_node_from_library()`、`get_node_function()`

#### 2.2 图形模块 (graphics/)

**port_item.py**
- `PortItem`：输入/输出端口类
- 处理端口连接、位置计算

**connection_item.py**
- `ConnectionItem`：节点间连接线
- 处理连接拖拽、路径绘制

**simple_node_item.py**
- `SimpleNodeItem`：图形节点类
- 节点位置、大小、颜色
- `param_types`：参数类型字典
- `param_values`：参数值字典（存储用户输入）
- `setup_ports()`：根据函数签名自动创建端口

**node_graphics_view.py**
- `NodeGraphicsView`：画布视图
- 处理缩放（滚轮）、平移（中键）、框选、节点拖拽

#### 2.3 执行引擎 (engine/)

**graph_executor.py**
- `topological_sort()`：拓扑排序计算执行顺序
- `execute_graph()`：执行图表
- 优先使用连接值，否则使用 `param_values` 中的预设值
- 使用 `func(**kwargs)` 方式调用节点函数

### 3. UI 模块 (ui/)

**main_window.py**
- `SimplePyFlowWindow`：主窗口类
- 工具栏：运行、停止、保存 JSON、加载 JSON
- 左侧面板：节点库（分类 + 自定义节点按钮）
- 右侧面板：属性面板（参数输入、文档、源代码）
- 底部面板：控制台输出
- `_setup_param_inputs()`：根据参数类型生成输入控件

**dialogs/custom_node_dialog.py**
- 自定义节点代码编辑器对话框
- 语法检查和验证（AST 解析）
- 选择/创建分类

**dialogs/category_dialog.py**
- 新建分类对话框

**widgets/draggable_node_tree.py**
- 可拖拽的节点树形列表
- 支持分类展开/折叠

### 4. 存储模块 (storage/)

**custom_node_storage.py**
- `save_custom_nodes()`：保存自定义节点到 `.node-python/custom_nodes.json`
- `load_custom_nodes()`：从文件加载自定义节点
- 包含源代码、分类、函数签名等元数据
- AST 验证和编译执行

**graph_storage.py**
- `save_graph_to_file()`：保存图表到 JSON 文件
- `load_graph_from_file()`：从 JSON 文件加载图表
- `export_graph_to_json()`：导出图表数据
- `import_graph_from_json()`：导入图表数据

### 5. 工具模块 (utils/)

**constants.py**
- 应用名称、窗口尺寸
- 节点尺寸、端口半径
- 颜色定义（节点、端口、连接线、选中状态）
- 控制台和代码编辑器样式
- 存储路径常量

**console_stream.py**
- `EmittingStream`：重定向 stdout 到 QTextEdit
- 实现实时控制台输出

## 数据流

```
用户操作 -> ui/main_window.py -> core/graphics/*.py (图形更新)
                                  |
                                  v
                           core/engine/graph_executor.py (执行)
                                  |
                                  v
                           core/nodes/base_nodes.py (节点函数)
                                  |
                                  v
                           控制台输出 / 结果传递
```

## 持久化存储

### 存储位置

- 开发环境：`./.node-python/`
- 打包后：`可执行文件目录/.node-python/`

### 文件说明

| 文件 | 内容 | 说明 |
|------|------|------|
| `settings.json` | 应用设置 | 窗口状态、用户偏好 |
| `custom_nodes.json` | 自定义节点 | 源代码、分类、元数据 |
| `*.json` (用户保存) | 图表数据 | 节点位置、连接关系、参数值 |

## 扩展点

### 添加内置节点

1. 在 `core/nodes/base_nodes.py` 中添加函数
2. 在 `core/nodes/node_library.py` 的 `NODE_LIBRARY_CATEGORIZED` 中注册

### 添加新参数类型

1. 在 `ui/main_window.py` 的 `_setup_param_inputs()` 中添加类型判断和控件创建
2. 更新 `core/graphics/simple_node_item.py` 的端口设置逻辑（如需要）

### 添加新存储格式

1. 在 `storage/` 中创建新模块
2. 实现保存/加载函数
3. 在 UI 中添加对应的操作按钮

## 依赖关系

```
main.py
├── config/settings.py
├── storage/custom_node_storage.py
├── ui/main_window.py
│   ├── core/graphics/node_graphics_view.py
│   ├── core/engine/graph_executor.py
│   ├── core/nodes/node_library.py
│   └── utils/console_stream.py
└── PySide6
```
