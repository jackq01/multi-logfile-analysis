import sys
import os
import io
import logging
import traceback
import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, QFileDialog, QCheckBox, 
                             QDateEdit, QTimeEdit, QListWidget, QListWidgetItem, 
                             QSplitter, QMessageBox, QRadioButton, QGroupBox, QProgressBar, QAbstractItemView)
from PyQt5.QtGui import QFont, QColor, QTextCharFormat
from PyQt5.QtCore import Qt, QTimer

from .utils import generate_light_colors
from .log_processor import LogProcessor
from .highlight_delegate import HighlightDelegate

class LogAnalyzerApp(QMainWindow):
    LOG_REGEX_PATTERN = r'(%@\d+%[\s\S]*?(?=%@\d+%|\Z))'
    TIME_REGEX_PATTERN = r'(\w+)\s+(\d{1,2})\s+(\d{1,2}):(\d{1,2}):(\d{1,2}):(\d{1,3})\s+(\d{4})'

    def __init__(self):
        super().__init__()
        sys.excepthook = self.handle_uncaught_exception
        
        self.cache = {}
        self.page_size = 1000
        self.current_page = 0
        self.total_pages = 0
        
        self.log_display = QListWidget()
        self.log_display.setSelectionMode(QAbstractItemView.SingleSelection)
        self.log_display.setItemDelegate(HighlightDelegate(self.log_display))
        self.log_display.itemChanged.connect(self.on_log_item_changed)
        self.log_display.verticalScrollBar().valueChanged.connect(self.handle_scroll)
        
        font = QFont()
        font.setPointSize(12)
        font.setBold(False)
        self.log_display.setFont(font)
        
        self.log_display.setStyleSheet("""
            QListWidget::item {
                padding: 8px 5px;
                margin: 2px 0px;
            }
        """)
        self.log_display.installEventFilter(self)
        
        self.setWindowTitle("日志分析系统")
        self.resize(1200, 800)
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        center_point = screen.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())
        
        self.uploaded_files = []
        self.file_names = []
        self.all_logs = []
        self.current_logs = []
        self.watched_logs = []
        self.colors_by_file = {}
        self.analysis_started = False
        self.log_id_map = {}
        self.entry_to_id_map = {}
        
        self.log_processor = LogProcessor(self.LOG_REGEX_PATTERN, self.TIME_REGEX_PATTERN, self)
        
        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        
        splitter = QSplitter(Qt.Horizontal)
        
        left_panel = QWidget()
        left_panel.setMinimumWidth(280)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)
        left_layout.setContentsMargins(10, 12, 10, 12)
        
        app_font = QFont("Microsoft YaHei", 10)
        QApplication.setFont(app_font)
        
        group_title_font = QFont("Microsoft YaHei", 12)
        group_title_font.setBold(True)
        
        content_font = QFont("Microsoft YaHei", 10)
        
        file_group = QGroupBox("文件操作")
        file_group.setFont(group_title_font)
        file_layout = QVBoxLayout()
        file_layout.setSpacing(6)
        file_layout.setContentsMargins(10, 8, 10, 8)
        
        self.upload_btn = QPushButton("上传日志文件")
        self.upload_btn.setFont(content_font)
        self.upload_btn.setFixedHeight(30)
        self.upload_btn.setStyleSheet("""
            QPushButton {
                padding: 4px;
                border-radius: 4px;
                background-color: #4CAF50;
                color: white;
                font-family: "Microsoft YaHei";
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.upload_btn.clicked.connect(self.handle_file_upload)
        file_layout.addWidget(self.upload_btn)
        
        self.file_list = QListWidget()
        self.file_list.setFont(content_font)
        self.file_list.setStyleSheet("""
            QListWidget { 
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-family: "Microsoft YaHei";
            }
            QListWidget::item {
                margin: 2px 0px; 
                padding: 6px 5px;
            }
            QListWidget::item:hover {
                background-color: #e8e8e8;
            }
        """)
        file_layout.addWidget(self.file_list)
        file_group.setLayout(file_layout)
        left_layout.addWidget(file_group, 20)
        
        time_group = QGroupBox("时间范围")
        time_group.setFont(group_title_font)
        time_layout = QVBoxLayout()
        time_layout.setSpacing(8)
        time_layout.setContentsMargins(10, 8, 10, 8)
        
        self.time_range_check = QCheckBox("启用")
        self.time_range_check.setFont(content_font)
        time_layout.addWidget(self.time_range_check)
        
        start_time_group = QWidget()
        start_layout = QHBoxLayout()
        start_time_group.setLayout(start_layout)
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_layout.setSpacing(6)
        
        label_start = QLabel("开始:")
        label_start.setFont(content_font)
        start_layout.addWidget(label_start)
        
        self.start_date = QDateEdit()
        self.start_date.setFont(content_font)
        self.start_date.setFixedHeight(26)
        self.start_date.setStyleSheet("QDateEdit { padding: 2px 4px; font-family: 'Microsoft YaHei'; }")
        self.start_date.setDate(datetime.date(2025, 5, 1))
        start_layout.addWidget(self.start_date)
        
        self.start_time = QTimeEdit()
        self.start_time.setFont(content_font)
        self.start_time.setFixedHeight(26)
        self.start_time.setStyleSheet("QTimeEdit { padding: 2px 4px; font-family: 'Microsoft YaHei'; }")
        self.start_time.setTime(datetime.time(0, 0))
        start_layout.addWidget(self.start_time)
        
        time_layout.addWidget(start_time_group)
        
        end_time_group = QWidget()
        end_layout = QHBoxLayout()
        end_time_group.setLayout(end_layout)
        end_layout.setContentsMargins(0, 0, 0, 0)
        end_layout.setSpacing(6)
        
        label_end = QLabel("结束:")
        label_end.setFont(content_font)
        end_layout.addWidget(label_end)
        
        self.end_date = QDateEdit()
        self.end_date.setFont(content_font)
        self.end_date.setFixedHeight(26)
        self.end_date.setStyleSheet("QDateEdit { padding: 2px 4px; font-family: 'Microsoft YaHei'; }")
        self.end_date.setDate(datetime.date(2025, 5, 31))
        end_layout.addWidget(self.end_date)
        
        self.end_time = QTimeEdit()
        self.end_time.setFont(content_font)
        self.end_time.setFixedHeight(26)
        self.end_time.setStyleSheet("QTimeEdit { padding: 2px 4px; font-family: 'Microsoft YaHei'; }")
        self.end_time.setTime(datetime.time(23, 59))
        end_layout.addWidget(self.end_time)
        
        time_layout.addWidget(end_time_group)
        time_group.setLayout(time_layout)
        left_layout.addWidget(time_group, 23)
        
        search_group = QGroupBox("搜索设置")
        search_group.setFont(group_title_font)
        search_layout = QVBoxLayout()
        search_layout.setSpacing(8)
        search_layout.setContentsMargins(10, 8, 10, 8)
        
        self.search_edit = QTextEdit()
        self.search_edit.setFont(content_font)
        self.search_edit.setPlaceholderText("输入关键词（每行一个）")
        self.search_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 6px;
                background-color: #f5f5f5;
                font-family: "Microsoft YaHei";
            }
            QTextEdit:focus {
                border-color: #4CAF50;
                background-color: white;
            }
        """)
        search_layout.addWidget(self.search_edit)
        
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(20)
        mode_layout.setAlignment(Qt.AlignCenter)
        self.filter_mode_radio = QRadioButton("过滤模式")
        self.filter_mode_radio.setFont(content_font)
        self.filter_mode_radio.setChecked(True)
        self.highlight_mode_radio = QRadioButton("高亮模式")
        self.highlight_mode_radio.setFont(content_font)
        mode_layout.addWidget(self.filter_mode_radio)
        mode_layout.addWidget(self.highlight_mode_radio)
        search_layout.addLayout(mode_layout)
        
        search_group.setLayout(search_layout)
        left_layout.addWidget(search_group, 22)
        
        regex_group = QGroupBox("正则设置")
        regex_group.setFont(group_title_font)
        regex_layout = QVBoxLayout()
        regex_layout.setSpacing(6)
        regex_layout.setContentsMargins(10, 8, 10, 8)
        
        label = QLabel("日志匹配正则表达式：")
        label.setFont(content_font)
        regex_layout.addWidget(label)
        self.log_regex_edit = QTextEdit()
        self.log_regex_edit.setFont(content_font)
        self.log_regex_edit.setPlaceholderText("用于匹配单条日志的正则表达式")
        self.log_regex_edit.setText(self.LOG_REGEX_PATTERN)
        self.log_regex_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 6px;
                background-color: #f5f5f5;
                font-family: "Microsoft YaHei";
            }
            QTextEdit:focus {
                border-color: #4CAF50;
                background-color: white;
            }
        """)
        regex_layout.addWidget(self.log_regex_edit)
        
        label_time = QLabel("时间匹配正则表达式：")
        label_time.setFont(content_font)
        regex_layout.addWidget(label_time)
        self.time_regex_edit = QTextEdit()
        self.time_regex_edit.setFont(content_font)
        self.time_regex_edit.setPlaceholderText("用于匹配日志中时间的正则表达式")
        self.time_regex_edit.setText(self.TIME_REGEX_PATTERN)
        self.time_regex_edit.setStyleSheet(self.log_regex_edit.styleSheet())
        regex_layout.addWidget(self.time_regex_edit)
        
        regex_group.setLayout(regex_layout)
        left_layout.addWidget(regex_group, 25)
        
        button_container = QWidget()
        button_layout = QVBoxLayout()
        button_layout.setContentsMargins(0, 8, 0, 8)
        button_layout.setSpacing(8)
        
        self.analyze_btn = QPushButton("开始分析")
        self.analyze_btn.clicked.connect(self.process_files)
        self.analyze_btn.setFont(group_title_font)
        self.analyze_btn.setFixedHeight(36)
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 30px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-family: "Microsoft YaHei";
                font-size: 12px;
                min-width: 180px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        button_layout.addWidget(self.analyze_btn)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(24)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 4px;
                text-align: center;
                background-color: #f5f5f5;
                font-family: "Microsoft YaHei";
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        button_layout.addWidget(self.progress_bar)
        button_container.setLayout(button_layout)
        left_layout.addWidget(button_container, 10)
        
        left_panel.setLayout(left_layout)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setStyleSheet("""
            QSplitter::handle {
                height: 6px;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSI0IiBjeT0iMiIgcj0iMiIgZmlsbD0iIzk5OSIvPjxjaXJjbGUgY3g9IjEwIiBjeT0iMiIgcj0iMiIgZmlsbD0iIzk5OSIvPjxjaXJjbGUgY3g9IjE2IiBjeT0iMiIgcj0iMiIgZmlsbD0iIzk5OSIvPjwvc3ZnPg==);
                background: transparent;
                background-repeat: no-repeat;
                background-position: center;
            }
            QSplitter::handle:hover {
                background-color: rgba(0, 0, 0, 0.05);
            }
            QSplitter::handle:pressed {
                background-color: rgba(0, 0, 0, 0.1);
            }
        """)
        
        upper_widget = QWidget()
        upper_layout = QVBoxLayout()
        display_title_layout = QHBoxLayout()
        display_label = QLabel("日志显示")
        display_label.setFont(group_title_font)
        self.display_count_label = QLabel()
        self.display_count_label.setFont(content_font)
        self.display_count_label.setStyleSheet("color: #888; margin-left: 10px;")
        self.display_count_label.setText("")
        self.log_export_btn = QPushButton("导出当前日志")
        self.log_export_btn.setFont(content_font)
        self.log_export_btn.setMinimumWidth(120)
        self.log_export_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 20px;
                background-color: #FF9800;
                color: white;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.log_export_btn.clicked.connect(self.export_displayed_logs)
        display_title_layout.addWidget(display_label)
        display_title_layout.addWidget(self.display_count_label)
        display_title_layout.addStretch()
        self.display_source_check = QCheckBox("附带来源")
        self.display_source_check.setFont(content_font)
        self.display_source_check.setChecked(False)
        display_title_layout.addWidget(self.display_source_check)
        display_title_layout.addWidget(self.log_export_btn)
        upper_layout.addLayout(display_title_layout)
        upper_layout.addWidget(self.log_display)
        upper_widget.setLayout(upper_layout)

        lower_widget = QWidget()
        lower_layout = QVBoxLayout()
        watched_title_layout = QHBoxLayout()
        watched_label = QLabel("关注日志")
        watched_label.setFont(group_title_font)
        self.watched_count_label = QLabel()
        self.watched_count_label.setFont(content_font)
        self.watched_count_label.setStyleSheet("color: #888; margin-left: 10px;")
        self.watched_count_label.setText("")
        self.export_btn = QPushButton("导出关注日志")
        self.export_btn.clicked.connect(self.export_logs)
        self.export_btn.setFont(content_font)
        self.export_btn.setMinimumWidth(120)
        self.export_btn.setStyleSheet("""
            QPushButton {
                padding: 5px 20px;
                background-color: #008CBA;
                color: white;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #007B9E;
            }
        """)
        watched_title_layout.addWidget(watched_label)
        watched_title_layout.addWidget(self.watched_count_label)
        watched_title_layout.addStretch()
        self.watched_source_check = QCheckBox("附带来源")
        self.watched_source_check.setFont(content_font)
        self.watched_source_check.setChecked(False)
        watched_title_layout.addWidget(self.watched_source_check)
        watched_title_layout.addWidget(self.export_btn)
        lower_layout.addLayout(watched_title_layout)
        
        self.watched_logs_display = QListWidget()
        self.watched_logs_display.setSelectionMode(QAbstractItemView.SingleSelection)
        self.watched_logs_display.installEventFilter(self)
        watched_font = QFont()
        watched_font.setPointSize(12)
        watched_font.setBold(False)
        self.watched_logs_display.setFont(watched_font)
        self.watched_logs_display.setStyleSheet(self.log_display.styleSheet())
        lower_layout.addWidget(self.watched_logs_display)
        
        shortcut_label = QLabel("说明：CTRL D添加/删除，CTRL C复制，CTRL +放大，CTRL -缩小")
        shortcut_label.setFont(content_font)
        shortcut_label.setStyleSheet("color: #888; margin-top: 2px; margin-bottom: 2px;")
        lower_layout.addWidget(shortcut_label, alignment=Qt.AlignLeft)
        
        info_label = QLabel("注意：如解码问题显示告警为空，请复制内容到文本文件，重新上传尝试")
        info_label.setFont(content_font)
        info_label.setStyleSheet("color: #e53935; margin-top: 2px; margin-bottom: 2px;")
        lower_layout.addWidget(info_label, alignment=Qt.AlignLeft)
        lower_widget.setLayout(lower_layout)

        right_splitter.addWidget(upper_widget)
        right_splitter.addWidget(lower_widget)
        right_splitter.setSizes([500, 300])

        right_layout.addWidget(right_splitter)
        right_panel.setLayout(right_layout)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 900])

        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)

        self.statusBar().showMessage("开发者：运营商服务部 任富强（如有建议，请帮忙反馈）")

    def handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """处理未捕获的异常"""
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logging.error(f"未捕获的异常:\n{error_msg}")
        
        error_dialog = QMessageBox(self)
        error_dialog.setIcon(QMessageBox.Critical)
        error_dialog.setWindowTitle("程序错误")
        error_dialog.setText("程序发生未处理的异常")
        error_dialog.setDetailedText(error_msg)
        error_dialog.exec_()
        
        QApplication.quit()

    def export_logs(self):
        """导出关注日志到文件，保持原有顺序并添加来源信息"""
        if not self.watched_logs:
            QMessageBox.warning(self, "导出失败", "没有关注的日志可导出")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存日志文件", "", "文本文件 (*.txt);;所有文件 (*)")
            
        if not file_path:
            return
            
        try:
            logs_with_id = [(self.entry_to_id_map.get(log), log) for log in self.watched_logs if self.entry_to_id_map.get(log) is not None]
            logs_with_id.sort(key=lambda x: int(x[0]))
            with open(file_path, 'w', encoding='utf-8') as f:
                for log_id, log in logs_with_id:
                    if self.watched_source_check.isChecked():
                        file_name = log.source_file.split('/')[-1]
                        source_info = f"来源: {file_name}\n"
                        f.write(source_info)
                    f.write(log.content)
                    f.write("\n\n")
            QMessageBox.information(self, "导出成功", f"日志已成功导出到 {file_path}")
        except Exception as e:
            logging.error(f"导出日志失败: {str(e)}")
            QMessageBox.critical(self, "导出错误", f"导出日志时发生错误: {str(e)}")

    def export_displayed_logs(self):
        """导出当前日志显示区的所有日志，按id排序，与显示顺序一致"""
        if not self.current_logs:
            QMessageBox.warning(self, "导出失败", "没有可导出的日志")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存日志文件", "", "文本文件 (*.txt);;所有文件 (*)")
        if not file_path:
            return
        try:
            logs_with_id = [(self.entry_to_id_map.get(log), log) for log in self.current_logs if self.entry_to_id_map.get(log) is not None]
            logs_with_id.sort(key=lambda x: int(x[0]))
            with open(file_path, 'w', encoding='utf-8') as f:
                for log_id, log in logs_with_id:
                    if self.display_source_check.isChecked():
                        file_name = log.source_file.split('/')[-1]
                        source_info = f"来源: {file_name}\n"
                        f.write(source_info)
                    f.write(log.content)
                    f.write("\n\n")
            QMessageBox.information(self, "导出成功", f"日志已成功导出到 {file_path}")
        except Exception as e:
            logging.error(f"导出日志失败: {str(e)}")
            QMessageBox.critical(self, "导出错误", f"导出日志时发生错误: {str(e)}")

    def handle_file_upload(self):
        """处理文件上传，保留已上传文件并追加新文件"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择日志文件", "", "日志文件 (*.txt *.log)")
        if not files:
            return

        if not hasattr(self, 'file_names'):
            self.file_names = []
        if not hasattr(self, 'uploaded_files'):
            self.uploaded_files = []
        if not hasattr(self, 'colors_by_file'):
            self.colors_by_file = {}

        new_files = [f for f in files if f not in self.file_names]
        self.file_names.extend(new_files)

        for f in self.file_names:
            try:
                size = os.path.getsize(f)
            except Exception:
                size = -1
            logging.debug(f"[上传] 文件: {f}, 大小: {size}")

        color_count = len(self.file_names)
        self.colors_by_file.update(generate_light_colors(color_count, self.file_names))

        for file_path in new_files:
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                    self.uploaded_files.append(io.BytesIO(content))
                    logging.debug(f"[上传] 读取文件: {file_path}, 字节数: {len(content)}")
            except Exception as e:
                logging.error(f"读取文件 {file_path} 失败: {str(e)}")
                QMessageBox.warning(self, "文件错误", f"读取文件失败：\n{file_path}\n错误信息：{str(e)}")

        self.refresh_file_list()

        self.watched_logs = []
        self.update_watched_logs_display()
        self.analysis_started = False

    def refresh_file_list(self):
        """刷新文件列表显示，供上传和删除调用"""
        self.file_list.clear()
        for idx, file_path in enumerate(self.file_names):
            file_name = file_path.split('/')[-1]
            item_widget = QWidget()
            layout = QHBoxLayout(item_widget)
            layout.setContentsMargins(8, 0, 8, 0)
            layout.setSpacing(8)
            label = QLabel(file_name)
            label.setToolTip(file_path)
            label.setStyleSheet("padding-left:4px;")
            layout.addWidget(label, alignment=Qt.AlignVCenter)
            btn = QPushButton("删除")
            btn.setMinimumSize(60, 24)
            btn.setMaximumSize(60, 24)
            btn.setStyleSheet("""
                QPushButton {
                    padding: 2px 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: #ffffff;
                    color: #e53935;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #ffecec;
                    border-color: #e53935;
                }
            """)
            btn.setToolTip("删除该文件")
            btn.clicked.connect(lambda _, idx=idx: self.delete_file_item(idx))
            layout.addStretch()
            layout.addWidget(btn, alignment=Qt.AlignRight | Qt.AlignVCenter)
            
            list_item = QListWidgetItem()
            bg_color = self.colors_by_file.get(file_path, QColor("#EEEEEE"))
            list_item.setBackground(bg_color)
            self.file_list.addItem(list_item)
            self.file_list.setItemWidget(list_item, item_widget)

        self.watched_logs = []
        self.update_watched_logs_display()
        self.analysis_started = False

    def delete_file_item(self, idx):
        """删除文件列表中的某个文件，并同步移除相关内容"""
        try:
            if idx < 0 or idx >= len(self.file_names):
                return
            file_path = self.file_names[idx]
            del self.file_names[idx]
            del self.uploaded_files[idx]
            if file_path in self.colors_by_file:
                del self.colors_by_file[file_path]
            self.refresh_file_list()
        except Exception as e:
            logging.error(f"删除文件项时出错: {str(e)}")
            QMessageBox.warning(self, "删除错误", f"删除文件时发生错误: {str(e)}")

    def process_files(self):
        """处理上传的文件内容"""
        if not self.uploaded_files:
            QMessageBox.information(self, "提示", "请先上传日志文件")
            return
        
        if self.time_range_check.isChecked():
            start_datetime = datetime.datetime.combine(
                self.start_date.date().toPyDate(),
                self.start_time.time().toPyTime()
            )
            end_datetime = datetime.datetime.combine(
                self.end_date.date().toPyDate(),
                self.end_time.time().toPyTime()
            )
        else:
            start_datetime = None
            end_datetime = None
            
        keywords = [kw.strip() for kw in self.search_edit.toPlainText().split("\n") if kw.strip()]
        logging.debug(f"[分析] 启用时间范围: {self.time_range_check.isChecked()}, start: {start_datetime}, end: {end_datetime}")
        logging.debug(f"[分析] 关键词列表: {keywords}")
        
        try:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            QApplication.processEvents()
            
            def progress_callback(percent):
                self.progress_bar.setValue(percent)
                QApplication.processEvents()
            
            self.all_logs, failed_files = self.log_processor.process_log_files(self.uploaded_files, self.file_names, self.log_regex_edit, self.time_regex_edit, progress_callback=progress_callback)
            
            if failed_files:
                self.file_names = [f for f in self.file_names if f not in failed_files]
                self.uploaded_files = [self.uploaded_files[i] for i, f in enumerate(self.file_names) if f not in failed_files]
                self.refresh_file_list()
                QMessageBox.warning(self, "解析提示", f"以下文件未能解析到任何日志，已从列表中移除：\n\n" + "\n".join(failed_files))

            self.progress_bar.setValue(60)
            QApplication.processEvents()
            
            filtered_logs = self.log_processor.filter_logs_by_time_range(self.all_logs, start_datetime, end_datetime)
            self.progress_bar.setValue(80)
            QApplication.processEvents()
            
            if self.filter_mode_radio.isChecked():
                filtered_logs2 = self.log_processor.filter_logs_by_keywords(filtered_logs, keywords)
                self.progress_bar.setValue(90)
                QApplication.processEvents()
                self.display_logs(filtered_logs2)
            else:
                self.display_logs(filtered_logs, highlight_keywords=keywords)
                
            self.progress_bar.setValue(100)
            QApplication.processEvents()
            QTimer.singleShot(800, lambda: self.progress_bar.setVisible(False))
            self.analysis_started = True
        except Exception as e:
            self.progress_bar.setVisible(False)
            logging.error(f"处理文件时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self, "处理错误", f"处理文件时发生错误: {str(e)}")

    def _load_page(self, page_number, highlight_keywords=None):
        """加载指定页码的日志内容"""
        if not self.current_logs:
            if hasattr(self, 'display_count_label'):
                self.display_count_label.setText("(0)")
            return

        self.current_page = page_number
        start_idx = page_number * self.page_size
        end_idx = min(start_idx + self.page_size, len(self.current_logs))

        self.log_display.clear()

        for idx in range(start_idx, end_idx):
            log = self.current_logs[idx]
            is_watched = log in self.watched_logs
            display_text = log.content
            
            item = QListWidgetItem(display_text)

            log_id = str(idx)
            item.setData(Qt.UserRole, log_id)

            bg_color = self.colors_by_file.get(log.source_file, QColor("#FFFFFF"))
            item.setBackground(bg_color)

            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if is_watched else Qt.Unchecked)

            if highlight_keywords:
                highlight_data = []
                content_lower = log.content.lower()
                for keyword in highlight_keywords:
                    if not keyword:
                        continue
                    fmt = QTextCharFormat()
                    fmt.setForeground(QColor("#e53935"))
                    keyword_lower = keyword.lower()
                    start_pos = 0
                    while True:
                        pos = content_lower.find(keyword_lower, start_pos)
                        if pos == -1:
                            break
                        highlight_data.append((pos, pos + len(keyword), fmt))
                        start_pos = pos + len(keyword)
                if highlight_data:
                    highlight_data.sort(key=lambda x: x[0])
                    item.setData(Qt.UserRole + 1, highlight_data)

            self.log_display.addItem(item)
        if hasattr(self, 'display_count_label'):
            self.display_count_label.setText(f"({len(self.current_logs)})")

    def display_logs(self, logs, highlight_keywords=None):
        """显示日志内容（带虚拟滚动的分页显示）"""
        try:
            self.log_display.clear()
            self.log_id_map = {}
            self.entry_to_id_map = {}

            sorted_logs = sorted(logs, key=lambda x: x.timestamp if x.timestamp else datetime.datetime.min)
            self.current_logs = sorted_logs
            logging.debug(f"[显示] 当前要显示的日志数量: {len(self.current_logs)}")
            if len(self.current_logs) == 0:
                logging.warning("[显示] 没有任何日志可显示！")
            
            self.total_pages = (len(self.current_logs) + self.page_size - 1) // self.page_size
            self.current_page = 0
            
            for idx, log in enumerate(sorted_logs):
                log_id = str(idx)
                self.log_id_map[log_id] = log
                self.entry_to_id_map[log] = log_id
            
            self._load_page(0, highlight_keywords)
            if hasattr(self, 'display_count_label'):
                self.display_count_label.setText(f"({len(self.current_logs)})")
        except Exception as e:
            logging.error(f"显示日志时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.critical(self, "显示错误", f"显示日志时发生错误: {str(e)}")

    def on_log_item_changed(self, item):
        """勾选状态变化时自动更新关注列表，并刷新对勾标志"""
        try:
            log_id = item.data(Qt.UserRole)
            log_data = self.log_id_map.get(log_id)

            if not log_data:
                return

            self.watched_logs_display.blockSignals(True)

            if item.checkState() == Qt.Checked:
                if log_data not in self.watched_logs:
                    self.watched_logs.append(log_data)
            else:
                if log_data in self.watched_logs:
                    self.watched_logs.remove(log_data)

            self.update_watched_logs_display()
            
            highlight_keywords = None
            if self.highlight_mode_radio.isChecked():
                highlight_keywords = [kw.strip() for kw in self.search_edit.toPlainText().split("\n") if kw.strip()]
            self._load_page(self.current_page, highlight_keywords)
        except Exception as e:
            logging.error(f"处理日志勾选变化时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.warning(self, "操作错误", f"更新关注列表时发生错误: {str(e)}")
        finally:
            self.watched_logs_display.blockSignals(False)

    def update_watched_logs_display(self):
        """更新关注日志显示，所有日志严格按主日志显示区域的ID顺序排序"""
        try:
            self.watched_logs_display.blockSignals(True)
            self.watched_logs_display.clear()

            id_order = [str(i) for i in range(len(self.current_logs))]
            id_to_log = {self.entry_to_id_map.get(log): log for log in self.watched_logs}
            watched_logs_sorted = [id_to_log[log_id] for log_id in id_order if log_id in id_to_log]

            for log in watched_logs_sorted:
                log_id = self.entry_to_id_map.get(log)
                if log_id is None:
                    continue
                item = QListWidgetItem(log.content)
                item.setData(Qt.UserRole, log_id)
                bg_color = self.colors_by_file.get(log.source_file)
                if not bg_color:
                    bg_color = QColor("#EEEEEE")
                elif bg_color.lightness() < 200:
                    bg_color = bg_color.lighter(150)
                item.setBackground(bg_color)
                self.watched_logs_display.addItem(item)
            if hasattr(self, 'watched_count_label'):
                self.watched_count_label.setText(f"({len(watched_logs_sorted)})")
        except Exception as e:
            logging.error(f"更新关注日志显示时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.warning(self, "显示错误", f"更新关注日志显示时出错: {str(e)}")
        finally:
            self.watched_logs_display.blockSignals(False)

    def handle_scroll(self, value):
        """处理滚动事件，实现虚拟滚动加载"""
        if not hasattr(self, 'current_logs') or not self.current_logs:
            return
            
        viewport_height = self.log_display.viewport().height()
        item_height = 40
        visible_items = viewport_height // item_height
        total_height = len(self.current_logs) * item_height
        scroll_percentage = value / (self.log_display.verticalScrollBar().maximum() or 1)
        current_page = int(scroll_percentage * (len(self.current_logs) / self.page_size))
        
        if current_page != self.current_page:
            self._load_page(current_page)

    def adjust_font_size(self, increase=True):
        """调整日志显示和关注日志的字体大小"""
        try:
            current_size = self.log_display.font().pointSize()
            new_size = current_size + (2 if increase else -2)
            new_size = max(8, min(20, new_size))
            
            new_font = QFont(self.log_display.font())
            new_font.setPointSize(new_size)
            
            self.log_display.setFont(new_font)
            self.watched_logs_display.setFont(new_font)
            
        except Exception as e:
            logging.error(f"调整字体大小时出错: {str(e)}")
            traceback.print_exc()

    def eventFilter(self, obj, event):
        if event.type() == event.KeyPress:
            if obj in [self.log_display, self.watched_logs_display]:
                if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_C:
                    selected_items = obj.selectedItems()
                    if selected_items:
                        clipboard = QApplication.clipboard()
                        clipboard.setText(selected_items[0].text())
                if event.modifiers() & Qt.ControlModifier:
                    if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
                        self.adjust_font_size(True)
                    elif event.key() == Qt.Key_Minus:
                        self.adjust_font_size(False)
                if obj == self.log_display:
                    if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_D:
                        selected_items = self.log_display.selectedItems()
                        if selected_items:
                            item = selected_items[0]
                            item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)
                elif obj == self.watched_logs_display:
                    if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_D:
                        selected_items = self.watched_logs_display.selectedItems()
                        if selected_items:
                            self.delete_watched_item(selected_items[0])
                    elif event.key() in [Qt.Key_Delete, Qt.Key_Backspace]:
                        selected_items = self.watched_logs_display.selectedItems()
                        if selected_items:
                            self.delete_watched_item(selected_items[0])
        return super().eventFilter(obj, event)

    def delete_watched_item(self, item=None):
        """删除单个关注日志项，并同步清除主日志显示区域的对勾标志"""
        if item is None:
            item = self.watched_logs_display.currentItem()
            if not item:
                return
        try:
            if self.log_display:
                self.log_display.blockSignals(True)
            if self.watched_logs_display:
                self.watched_logs_display.blockSignals(True)

            log_id = item.data(Qt.UserRole)
            if log_id is None:
                return

            self.watched_logs = [log for log in self.watched_logs if self.entry_to_id_map.get(log) != log_id]
            self.update_watched_logs_display()

            for i in range(self.log_display.count()):
                log_item = self.log_display.item(i)
                if log_item and log_item.data(Qt.UserRole) == log_id:
                    log_item.setCheckState(Qt.Unchecked)

        except Exception as e:
            logging.error(f"删除关注日志项时出错: {str(e)}")
            traceback.print_exc()
            QMessageBox.warning(self, "操作错误", f"删除关注日志项时发生错误: {str(e)}")
        finally:
            if self.log_display:
                self.log_display.blockSignals(False)
            if self.watched_logs_display:
                self.watched_logs_display.blockSignals(False)
