"""正则表达式生成对话框"""

import re
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QLineEdit,
                               QMessageBox, QSplitter, QWidget, QGroupBox)
from PySide6.QtCore import Qt


class RegexGeneratorDialog(QDialog):
    """
    正则表达式生成对话框。
    允许用户输入示例文本和期望提取的内容，自动生成正则表达式。
    """

    def __init__(self, parent=None, current_regex=""):
        super().__init__(parent)
        self.setWindowTitle("正则表达式生成器")
        self.resize(900, 600)

        self.selected_regex = current_regex

        layout = QVBoxLayout(self)

        # 顶部说明
        info_label = QLabel("输入示例文本，标记需要提取的内容，自动生成正则表达式")
        info_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(info_label)

        # 分割器：左侧输入，右侧预览
        splitter = QSplitter(Qt.Horizontal)

        # 左侧：输入区域
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 示例文本输入
        left_layout.addWidget(QLabel("📝 示例文本（多行输入，每行一个示例）："))
        self.sample_text = QPlainTextEdit()
        self.sample_text.setPlaceholderText('''每行输入一个示例文本，例如：
CG 渲染_2026-02-26_21-11-27
彩虹小马_2026-02-26_21-18-55
国产 3D_2026-02-27_08-31-44

或者：
姓名：张三，年龄：25 岁
姓名：李四，年龄：30 岁''')
        self.sample_text.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; font-family: Consolas; font-size: 12px;"
        )
        self.sample_text.textChanged.connect(self._on_sample_changed)
        left_layout.addWidget(self.sample_text)

        # 提取目标输入
        left_layout.addWidget(QLabel("🎯 期望提取的内容（用 [] 标记）："))
        self.target_text = QPlainTextEdit()
        self.target_text.setPlaceholderText('''复制上面的一行示例文本，并用 [] 标记需要提取的部分，例如：
[CG 渲染]_2026-02-26_21-11-27
或
[彩虹小马]_2026-02-26_21-18-55

系统会自动分析所有示例，生成通用的正则表达式。
捕获组会自动添加，例如：^(.+?)_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}''')
        self.target_text.setStyleSheet(
            "background-color: #1e1e1e; color: #a9b7c6; font-family: Consolas; font-size: 12px;"
        )
        self.target_text.textChanged.connect(self._on_target_changed)
        left_layout.addWidget(self.target_text)

        # 生成按钮
        gen_btn = QPushButton("🪄 智能生成正则表达式")
        gen_btn.setStyleSheet("background: #9C27B0; color: white; padding: 10px; font-weight: bold;")
        gen_btn.clicked.connect(self._generate_regex)
        left_layout.addWidget(gen_btn)

        splitter.addWidget(left_widget)

        # 右侧：结果预览区域
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 正则表达式输入
        right_layout.addWidget(QLabel("📐 生成的正则表达式："))
        self.regex_input = QLineEdit()
        self.regex_input.setText(current_regex)
        self.regex_input.setPlaceholderText("点击左侧生成按钮，或手动输入正则表达式")
        self.regex_input.setStyleSheet(
            "background-color: #2b2b2b; color: #4CAF50; font-family: Consolas; font-size: 13px; padding: 5px;"
        )
        self.regex_input.textChanged.connect(self._on_regex_changed)
        right_layout.addWidget(self.regex_input)

        # 常用正则模板
        template_group = QGroupBox("📋 常用正则模板（点击使用）")
        template_layout = QVBoxLayout()

        templates = [
            ("文件名前缀（下划线分隔）", r"^(.+?)_"),
            ("日期时间格式", r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}"),
            ("邮箱地址", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
            ("手机号码", r"1[3-9]\d{9}"),
            ("电话号码", r"\d{3,4}-?\d{7,8}"),
            ("URL 链接", r"https?://[^\s]+"),
            ("IP 地址", r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"),
            ("身份证号码", r"\d{17}[\dXx]"),
            ("日期 (YYYY-MM-DD)", r"\d{4}-\d{2}-\d{2}"),
            ("中文文字", r"[\u4e00-\u9fa5]+"),
            ("数字", r"\d+"),
            ("字母", r"[a-zA-Z]+"),
            ("单词", r"\w+"),
            ("任意字符（非贪婪）", r".+?"),
            ("任意字符（贪婪）", r".+"),
        ]

        for name, pattern in templates:
            btn = QPushButton(f"{name}: {pattern}")
            btn.setStyleSheet("text-align: left; font-family: Consolas; font-size: 11px; padding: 5px;")
            btn.clicked.connect(lambda checked, p=pattern: self._use_template(p))
            template_layout.addWidget(btn)

        template_group.setLayout(template_layout)
        right_layout.addWidget(template_group)

        # 测试区域
        right_layout.addWidget(QLabel("🧪 测试提取结果："))
        self.test_result = QPlainTextEdit()
        self.test_result.setReadOnly(True)
        self.test_result.setPlaceholderText("点击测试按钮查看提取结果")
        self.test_result.setStyleSheet(
            "background-color: #1e1e1e; color: #FF9800; font-family: Consolas; font-size: 12px;"
        )
        self.test_result.setMaximumHeight(200)
        right_layout.addWidget(self.test_result)

        # 测试按钮
        test_btn = QPushButton("▶ 测试提取")
        test_btn.setStyleSheet("background: #FF9800; color: white; padding: 8px;")
        test_btn.clicked.connect(self._test_regex)
        right_layout.addWidget(test_btn)

        splitter.addWidget(right_widget)
        splitter.setSizes([450, 450])

        layout.addWidget(splitter)

        # 底部按钮
        btn_layout = QHBoxLayout()

        help_btn = QPushButton("❓ 正则语法帮助")
        help_btn.setStyleSheet("background: #607D8B; color: white;")
        help_btn.clicked.connect(self._show_regex_help)
        btn_layout.addWidget(help_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        confirm_btn = QPushButton("✓ 确认使用")
        confirm_btn.setStyleSheet("background: #4CAF50; color: white; font-weight: bold;")
        confirm_btn.clicked.connect(self._confirm_selection)
        btn_layout.addWidget(confirm_btn)

        layout.addLayout(btn_layout)

    def _on_sample_changed(self):
        """示例文本变化"""
        pass

    def _on_target_changed(self):
        """目标文本变化"""
        pass

    def _on_regex_changed(self, text):
        """正则表达式变化"""
        self.selected_regex = text

    def _use_template(self, pattern):
        """使用预设模板"""
        self.regex_input.setText(pattern)
        self.selected_regex = pattern

    def _generate_regex(self):
        """生成正则表达式 - 增强版"""
        sample = self.sample_text.toPlainText().strip()
        target = self.target_text.toPlainText().strip()

        if not sample:
            QMessageBox.warning(self, "提示", "请先输入示例文本")
            return

        if not target:
            QMessageBox.warning(self, "提示", "请输入期望提取的内容（用 [] 标记）或描述提取目标")
            return

        # 尝试从标记的文本中提取
        if '[' in target and ']' in target:
            # 用户用 [] 标记了要提取的内容
            # 获取多行示例
            sample_lines = [line.strip() for line in sample.split('\n') if line.strip()]
            
            # 从标记的模板中提取固定部分和可变部分
            regex = self._smart_infer_regex(target, sample_lines)
            if regex:
                self.regex_input.setText(regex)
                self.selected_regex = regex
                QMessageBox.information(self, "生成成功", f"已生成正则表达式:\n{regex}")
                return
        else:
            # 尝试根据描述生成
            sample_lines = [line.strip() for line in sample.split('\n') if line.strip()]
            regex = self._generate_regex_from_description(target, sample_lines)
            if regex:
                self.regex_input.setText(regex)
                self.selected_regex = regex
                QMessageBox.information(self, "生成成功", f"已生成正则表达式:\n{regex}")
                return

        QMessageBox.warning(self, "生成失败", "无法自动生成正则表达式，请手动输入或修改输入内容")

    def _smart_infer_regex(self, marked_template, sample_lines):
        """
        智能推断正则表达式。
        根据标记的模板和多个示例，分析固定模式和可变模式。
        """
        # 提取标记的值和位置
        marked_parts = []
        last_end = 0
        for match in re.finditer(r'\[([^\]]+)\]', marked_template):
            marked_parts.append({
                'start': match.start(),
                'end': match.end(),
                'value': match.group(1),
                'text_before': marked_template[last_end:match.start()]
            })
            last_end = match.end()
        
        if not marked_parts:
            return None
        
        # 添加最后一部分
        if last_end < len(marked_template):
            marked_parts.append({
                'start': last_end,
                'end': len(marked_template),
                'value': None,
                'text_before': marked_template[last_end:]
            })
        
        # 移除标记，获取模板结构
        template_clean = re.sub(r'\[([^\]]+)\]', r'(?P<extract>.+?)', marked_template)
        
        # 分析所有示例，推断每个捕获部分的模式
        regex_parts = []
        capture_groups = []
        
        # 重新解析模板，构建正则
        pos = 0
        group_index = 0
        for match in re.finditer(r'\[([^\]]+)\]', marked_template):
            # 添加标记前的固定文本
            fixed_text = marked_template[pos:match.start()]
            if fixed_text:
                # 转义固定文本中的特殊字符
                escaped = re.escape(fixed_text)
                regex_parts.append(escaped)
            
            # 分析标记部分的模式
            marked_value = match.group(1)
            group_index += 1
            
            # 从所有示例中提取对应位置的值
            extracted_values = self._extract_at_position(marked_template, marked_value, sample_lines)
            
            # 推断这部分的模式
            pattern = self._infer_pattern_for_value(extracted_values, marked_value)
            regex_parts.append(f'({pattern})')
            capture_groups.append(pattern)
            
            pos = match.end()
        
        # 添加最后的固定文本
        if pos < len(marked_template):
            fixed_text = marked_template[pos:]
            if fixed_text:
                regex_parts.append(re.escape(fixed_text))
        
        # 构建完整正则
        regex = ''.join(regex_parts)
        
        # 优化：如果正则以固定文本结尾，尝试使其更通用
        # 检查所有示例是否有相同的结尾模式
        if len(sample_lines) > 1:
            common_suffix = self._find_common_suffix_pattern(sample_lines)
            if common_suffix:
                # 替换末尾的固定文本为通用模式
                regex = self._optimize_regex(regex, common_suffix, sample_lines)
        
        return regex

    def _extract_at_position(self, template, marked_value, sample_lines):
        """从所有示例中提取标记位置的值"""
        # 移除模板中的标记
        clean_template = template.replace(f'[{marked_value}]', '(.+?)')
        # 转义其他特殊字符
        clean_template = re.escape(clean_template).replace(r'\(\.\+\?\)', '(.+?)')
        
        values = []
        for line in sample_lines:
            match = re.search(clean_template, line)
            if match:
                values.append(match.group(1))
        
        return values if values else [marked_value]

    def _infer_pattern_for_value(self, values, original_value):
        """根据提取的值推断正则模式"""
        if not values:
            return '.+?'
        
        # 使用第一个值作为参考
        value = values[0]
        
        # 分析值的特征
        all_digits = all(v.isdigit() for v in values)
        all_chinese = all(all('\u4e00' <= c <= '\u9fff' for c in v) for v in values)
        all_letters = all(v.isalpha() and all(c.isascii() for c in v) for v in values)
        has_chinese = any('\u4e00' <= c <= '\u9fff' for c in value)
        has_letters = any(c.isalpha() for c in value)
        has_digits = any(c.isdigit() for c in value)
        
        # 检查长度是否一致
        lengths = [len(v) for v in values]
        same_length = len(set(lengths)) == 1
        
        # 检查是否有固定格式
        has_date = any(re.match(r'\d{4}-\d{2}-\d{2}', v) for v in values)
        has_time = any(re.match(r'\d{2}:\d{2}:\d{2}', v) for v in values)
        
        if all_digits:
            if same_length:
                return f'\\d{{{lengths[0]}}}'
            return r'\d+'
        elif all_chinese:
            return r'[\u4e00-\u9fa5]+'
        elif all_letters:
            if same_length:
                return f'[a-zA-Z]{{{lengths[0]}}}'
            return r'[a-zA-Z]+'
        elif has_date:
            return r'\d{4}-\d{2}-\d{2}'
        elif has_time:
            return r'\d{2}:\d{2}:\d{2}'
        elif has_chinese or (has_letters and has_digits):
            # 中文、字母、数字混合 - 使用非贪婪匹配到下一个特殊字符
            return r'[^_]+'
        elif has_letters and has_digits:
            return r'\w+'
        else:
            # 通用模式：匹配到下一个特殊字符之前
            return r'[^_]+'

    def _find_common_suffix_pattern(self, sample_lines):
        """查找所有示例的共同后缀模式"""
        if len(sample_lines) < 2:
            return None
        
        # 从后向前查找共同模式
        common_parts = []
        min_len = min(len(line) for line in sample_lines)
        
        for i in range(1, min_len + 1):
            chars = [line[-i] for line in sample_lines]
            if len(set(chars)) == 1:
                common_parts.append(chars[0])
            else:
                break
        
        if len(common_parts) > 0:
            return ''.join(reversed(common_parts))
        return None

    def _optimize_regex(self, regex, common_suffix, sample_lines):
        """优化正则表达式，使用通用模式替换固定值"""
        # 检查后缀是否是日期时间格式
        date_time_pattern = r'_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$'
        if re.search(r'_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$', common_suffix):
            # 替换为通用日期时间模式
            regex = re.sub(r'_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$', 
                          r'_\\d{4}-\\d{2}-\\d{2}_\\d{2}-\\d{2}-\\d{2}', regex)
        elif re.search(r'_\d{4}-\d{2}-\d{2}$', common_suffix):
            regex = re.sub(r'_\d{4}-\d{2}-\d{2}$', r'_\\d{4}-\\d{2}-\\d{2}', regex)
        
        return regex

    def _generate_regex_from_description(self, description, sample_lines):
        """根据描述生成正则表达式"""
        desc_lower = description.lower()

        # 关键词匹配
        if any(kw in desc_lower for kw in ['前缀', '开头', '文件名']):
            # 提取下划线前的部分
            return r'^(.+?)_'
        elif any(kw in desc_lower for kw in ['后缀', '结尾']):
            return r'_(.+?)$'
        elif any(kw in desc_lower for kw in ['邮箱', 'email', 'mail']):
            return r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        elif any(kw in desc_lower for kw in ['手机', '电话', '号码']):
            return r"1[3-9]\d{9}"
        elif any(kw in desc_lower for kw in ['url', '链接', '网址']):
            return r"https?://[^\s]+"
        elif any(kw in desc_lower for kw in ['ip', '地址']):
            return r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        elif any(kw in desc_lower for kw in ['日期', '时间']):
            return r"\d{4}-\d{2}-\d{2}"
        elif any(kw in desc_lower for kw in ['中文', '汉字']):
            return r"[\u4e00-\u9fa5]+"
        elif any(kw in desc_lower for kw in ['数字', '整数']):
            return r"\d+"
        elif any(kw in desc_lower for kw in ['字母', '英文']):
            return r"[a-zA-Z]+"
        elif any(kw in desc_lower for kw in ['姓名', '名字']):
            return r"[\u4e00-\u9fa5]{2,4}"
        elif any(kw in desc_lower for kw in ['年龄', '岁数']):
            return r"\d{1,3}"
        elif any(kw in desc_lower for kw in ['身份证']):
            return r"\d{17}[\dXx]"

        return None

    def _test_regex(self):
        """测试正则表达式"""
        regex = self.regex_input.text().strip()
        sample = self.sample_text.toPlainText().strip()

        if not regex:
            QMessageBox.warning(self, "提示", "请先输入或生成正则表达式")
            return

        if not sample:
            QMessageBox.warning(self, "提示", "请输入示例文本用于测试")
            return

        try:
            # 尝试编译正则
            pattern = re.compile(regex)

            # 执行匹配
            all_results = []
            for line in sample.split('\n'):
                line = line.strip()
                if not line:
                    continue
                matches = pattern.findall(line)
                if matches:
                    if isinstance(matches[0], tuple):
                        # 多个捕获组
                        for match in matches:
                            all_results.append(' | '.join(str(m) for m in match))
                    else:
                        all_results.extend(str(m) for m in matches)

            # 格式化输出结果
            if all_results:
                result = "找到以下匹配项:\n\n"
                for i, match in enumerate(all_results, 1):
                    result += f"{i}. {match}\n"

                if len(all_results) > 20:
                    result += f"\n... 共 {len(all_results)} 条匹配结果"
            else:
                result = "未找到匹配项，请检查正则表达式或示例文本"

            self.test_result.setPlainText(result)

        except re.error as e:
            self.test_result.setPlainText(f"正则表达式错误:\n{e}")
            QMessageBox.warning(self, "正则错误", f"正则表达式语法错误:\n{e}")

    def _show_regex_help(self):
        """显示正则语法帮助"""
        help_text = """
正则表达式快速参考:

基本语法:
  .     匹配任意单个字符
  \\d    匹配数字 (0-9)
  \\w    匹配字母、数字或下划线
  \\s    匹配空白字符
  [abc]  匹配方括号中的任意字符
  [^abc] 匹配除方括号中字符外的任意字符

数量限定:
  *     匹配 0 次或多次
  +     匹配 1 次或多次
  ?     匹配 0 次或 1 次
  {n}   匹配恰好 n 次
  {n,}  匹配至少 n 次
  {n,m} 匹配 n 到 m 次

位置锚点:
  ^     匹配字符串开头
  $     匹配字符串结尾
  \\b    匹配单词边界

分组:
  ()    捕获组
  (?:)  非捕获组
  |     或操作

常用示例:
  文件名前缀：^(.+?)_
  邮箱：[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}
  手机：1[3-9]\\d{9}
  日期：\\d{4}-\\d{2}-\\d{2}
  中文：[\\u4e00-\\u9fa5]+
  
智能生成技巧:
  1. 在示例文本区输入多个相似格式的示例
  2. 在目标区复制一行并用 [] 标记要提取的部分
  3. 系统会自动分析固定模式和可变模式
  4. 生成的正则会自动适配所有示例
"""
        QMessageBox.information(self, "正则表达式语法帮助", help_text)

    def _confirm_selection(self):
        """确认选择"""
        self.selected_regex = self.regex_input.text().strip()
        if not self.selected_regex:
            QMessageBox.warning(self, "提示", "请先输入或生成正则表达式")
            return

        # 验证正则表达式
        try:
            re.compile(self.selected_regex)
        except re.error as e:
            QMessageBox.warning(self, "正则错误", f"正则表达式语法错误:\n{e}")
            return

        self.accept()

    def get_selected_regex(self):
        """获取选中的正则表达式"""
        return self.selected_regex


def show_regex_generator(parent=None, current_regex=""):
    """显示正则表达式生成对话框，返回选中的正则表达式或 None"""
    dialog = RegexGeneratorDialog(parent, current_regex)
    if dialog.exec() == QDialog.Accepted:
        return dialog.get_selected_regex()
    return None
