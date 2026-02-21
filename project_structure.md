# 项目结构设计文档

## 项目概述

简易中文节点编辑器 - 基于 PySide6 的图形化节点编辑器，支持自定义 Python 节点函数、参数输入、JSON 持久化存储、主题切换。

## 目录结构

```
node-python/
├── main.py                     # 应用入口，初始化 Qt 应用和主窗口
├── main_flow_2.py             # 流程图示例 2（备用入口）
├── main_flow_line.py          # 线性流程图示例（备用入口）
├── requirements.txt            # 依赖：PySide6>=6.5.0
├── README.md                   # 项目说明文档
├── AGENTS.md                   # AI 助手上下文文档
├── project_structure.md        # 本文件，项目结构设计
├── logo/                       # 图标和截图
│   └── node-python-logo.ico   # 应用图标
├── config/                     # 配置文件
│   ├── __init__.py
│   └── settings.py            # 应用配置管理（窗口状态、用户偏好、主题等）
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
│   │   ├── simple_node_item.py# 图形节点类（含参数值存储、主题支持）
│   │   └── node_graphics_view.py# 画布视图（缩放、平移、主题支持）
│   └── engine/                # 执行引擎
│       ├── __init__.py
│       ├── graph_executor.py  # 拓扑排序和执行逻辑
│       └── embedded_executor.py # 嵌入式 Python 执行器
├── ui/                         # 用户界面
│   ├── __init__.py
│   ├── main_window.py         # 主窗口，工具栏和面板布局
│   ├── dialogs/               # 对话框
│   │   ├── __init__.py
│   │   ├── custom_node_dialog.py  # 自定义节点代码编辑器
│   │   ├── category_dialog.py     # 新建分类对话框
│   │   ├── ai_node_generator_dialog.py # AI 节点生成器
│   │   ├── path_selector_dialog.py # 路径选择对话框
│   │   └── package_manager_dialog.py # 依赖包管理器
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
    ├── console_stream.py      # 控制台输出重定向
    ├── theme_manager.py       # 主题管理器（黑白模式切换）
    ├── sandbox.py             # 沙箱执行环境
    └── setup_embedded_python.py # 嵌入式 Python 环境初始化
```

## 核心模块说明

### 1. 配置模块 (config/)

**settings.py**
- 应用设置管理类 `Settings`
- 支持设置项：窗口状态、图形选项、节点选项、执行选项、UI 主题
- 自动保存和加载设置到 `.node-python/settings.json`
- 支持 PyInstaller 打包后的路径处理
- 主题设置键：`ui.theme`（值为 "dark" 或 "light"）

### 2. 核心模块 (core/)

#### 2.1 节点模块 (nodes/)

**base_nodes.py**
- 内置节点函数定义
- 常量节点：布尔、整数、浮点数、字符串、列表、字典
- 输出节点：打印节点
- `NODE_CODE_EXAMPLE`：自定义节点代码示例模板

**node_library.py**
- `NODE_LIBRARY_CATEGORIZED`：分类存储的节点库
- `LOCAL_NODE_LIBRARY`：扁平索引，方便查找
- `CUSTOM_CATEGORIES`：用户自定义分类列表
- 函数：`add_node_to_library()`、`remove_node_from_library()`、`get_node_function()`、`get_node_source_code()`、`is_custom_node()`

#### 2.2 图形模块 (graphics/)

**port_item.py**
- `PortItem`：输入/输出端口类
- 处理端口连接、位置计算
- 支持主题切换：`update_theme()` 方法

**connection_item.py**
- `ConnectionItem`：节点间连接线
- 处理连接拖拽、路径绘制
- 支持主题切换：`update_theme()` 方法

**simple_node_item.py**
- `SimpleNodeItem`：图形节点类
- 节点位置、大小、颜色（支持主题）
- `param_types`：参数类型字典
- `param_values`：参数值字典（存储用户输入）
- `setup_ports()`：根据函数签名自动创建端口
- `update_theme()`：更新节点主题颜色
- `itemChange()`：处理选中状态变化，更新主题

**node_graphics_view.py**
- `NodeGraphicsView`：画布视图
- 处理缩放（滚轮）、平移（中键）、框选、节点拖拽
- 支持主题切换：`update_theme()` 方法
- 右键菜单支持搜索和分类浏览

#### 2.3 执行引擎 (engine/)

**graph_executor.py**
- `topological_sort()`：拓扑排序计算执行顺序
- `execute_graph()`：执行图表
- `execute_graph_embedded()`：在嵌入式环境中执行
- 优先使用连接值，否则使用 `param_values` 中的预设值
- 使用 `func(**kwargs)` 方式调用节点函数

**embedded_executor.py**
- `EmbeddedPythonExecutor`：嵌入式 Python 执行器
- 管理外部 Python 进程
- 支持依赖包安装
- 提供执行隔离环境

### 3. UI 模块 (ui/)

**main_window.py**
- `SimplePyFlowWindow`：主窗口类
- 工具栏：运行、停止、保存 JSON、加载 JSON、AI 节点、依赖管理、初始化环境、主题切换
- 左侧面板：节点库（分类 + 自定义节点按钮 + AI 模板按钮）
- 右侧面板：属性面板（参数输入、文档、源代码）
- 底部面板：控制台输出（含日志路径设置、打开文件夹、清空按钮）
- `_setup_param_inputs()`：根据参数类型生成输入控件
- `_init_theme()`：初始化主题
- `_toggle_theme()`：切换主题
- `_on_theme_changed()`：主题变化回调
- `_update_graphics_theme()`：更新所有图形项主题

**dialogs/custom_node_dialog.py**
- 自定义节点代码编辑器对话框
- 语法检查和验证（AST 解析）
- 选择/创建分类
- 支持编辑模式（修改已有节点）

**dialogs/category_dialog.py**
- 新建分类对话框

**dialogs/ai_node_generator_dialog.py**
- AI 节点生成器对话框
- 根据自然语言描述生成节点代码
- 支持代码预览和编辑

**dialogs/path_selector_dialog.py**
- 数据提取路径选择器
- 可视化选择数据路径

**dialogs/package_manager_dialog.py**
- 依赖包管理器
- 安装、卸载、列出已安装包

**widgets/draggable_node_tree.py**
- 可拖拽的节点树形列表
- 支持分类展开/折叠
- 右键菜单支持编辑和删除

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
- 颜色定义（向后兼容）
- 存储路径常量
- 主题相关常量：`DEFAULT_THEME`、`THEME_SETTING_KEY`

**console_stream.py**
- `EmittingStream`：重定向 stdout 到 QTextEdit
- 实现实时控制台输出
- 支持日志文件写入

**theme_manager.py**
- `ThemeManager`：主题管理器（单例模式）
- `THEMES`：主题定义字典（dark/light）
- `get_color()`：获取颜色值
- `get_qcolor()`：获取 QColor 对象
- `set_theme()`：设置主题
- `toggle_theme()`：切换主题
- `get_stylesheet()`：生成 QSS 样式表
- `theme_changed`：主题切换信号

**sandbox.py**
- 沙箱执行环境
- 代码安全检查和限制

**setup_embedded_python.py**
- `EmbeddedPythonSetup`：嵌入式 Python 环境初始化
- 下载、解压、配置嵌入式 Python
- 安装 pip 支持

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

## 主题系统

### 主题管理架构

```
utils/theme_manager.py (ThemeManager 单例)
         |
         | 信号通知
         v
ui/main_window.py -> 应用 QSS 样式表
         |
         | 遍历更新
         v
core/graphics/*.py -> 更新图形项颜色
```

### 主题切换流程

1. 用户点击工具栏主题切换按钮
2. `main_window._toggle_theme()` 调用 `theme_manager.toggle_theme()`
3. 主题管理器切换主题并发出 `theme_changed` 信号
4. 主窗口接收信号，调用 `_on_theme_changed()`
5. 应用新的 QSS 样式表
6. 遍历所有图形项，调用 `update_theme()` 方法
7. 刷新画布显示

### 主题定义

主题定义在 `ThemeManager.THEMES` 字典中：
- `dark`：暗黑模式，深色背景，高对比度
- `light`：明亮模式，浅色背景，柔和色调

每个主题包含：
- 节点颜色（背景、边框、文本）
- 端口颜色（输入、输出、边框）
- 连接线颜色
- 选择框颜色
- 背景颜色（画布、面板）
- 控制台和代码编辑器颜色
- UI 控件颜色（按钮、输入框、菜单等）

## 持久化存储

### 存储位置

- 开发环境：`./.node-python/`
- 打包后：`可执行文件目录/.node-python/`

### 文件说明

| 文件 | 内容 | 说明 |
|------|------|------|
| `settings.json` | 应用设置 | 窗口状态、用户偏好、主题设置 |
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

### 添加新主题

1. 在 `utils/theme_manager.py` 的 `THEMES` 字典中添加新主题定义
2. 添加主题切换逻辑（如需要）

## 依赖关系

```
main.py
├── config/settings.py
├── storage/custom_node_storage.py
├── ui/main_window.py
│   ├── core/graphics/node_graphics_view.py
│   ├── core/engine/graph_executor.py
│   ├── core/nodes/node_library.py
│   ├── utils/console_stream.py
│   └── utils/theme_manager.py  (新增)
└── PySide6
```

## 最近更新

### 主题切换功能
- 新增 `utils/theme_manager.py` 主题管理器
- 支持暗黑模式和明亮模式切换
- 所有图形组件支持动态主题更新
- 主题设置自动持久化

### AI 节点生成
- 新增 `ui/dialogs/ai_node_generator_dialog.py`
- 支持自然语言描述生成节点代码

### 依赖管理
- 新增 `ui/dialogs/package_manager_dialog.py`
- 支持第三方库的安装和管理

### 嵌入式 Python
- 新增 `core/engine/embedded_executor.py`
- 新增 `utils/setup_embedded_python.py`
- 统一使用外部 Python 环境执行节点