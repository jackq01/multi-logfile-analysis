import re
import logging
import datetime
import os
import io
from typing import List, Generator, Optional, Iterable
from concurrent.futures import ThreadPoolExecutor
from PyQt5.QtWidgets import QMessageBox
from .utils import LogEntry, parse_log_time

class LogProcessor:
    def __init__(self, log_regex_pattern, time_regex_pattern, parent=None):
        self.LOG_REGEX_PATTERN = log_regex_pattern
        self.TIME_REGEX_PATTERN = time_regex_pattern
        self.parent = parent

    def extract_log_info(self, log_entry: str, source_file: str) -> LogEntry:
        """从日志条目中提取信息 - 优化2：使用namedtuple节省内存"""
        # 尝试匹配更宽泛的时间格式
        time_match = re.search(self.TIME_REGEX_PATTERN, log_entry)
        if time_match:
            time_str = time_match.group(0)
            timestamp = parse_log_time(time_str, self.TIME_REGEX_PATTERN)
            logging.debug(f"[时间戳提取] 日志条目: {log_entry}, 时间戳: {timestamp}")
        else:
            time_str = ""
            timestamp = None
            logging.debug(f"[时间戳提取失败] 日志条目: {log_entry}")
            logging.debug(f"[正则表达式] TIME_REGEX_PATTERN: {self.TIME_REGEX_PATTERN}")
        
        return LogEntry(
            content=log_entry,
            timestamp=timestamp,
            source_file=source_file,
            time_str=time_str
        )

    def parse_log_entries(self, content: str, log_regex_edit, time_regex_edit) -> Generator[str, None, None]:
        """解析日志内容，提取每条日志条目 - 优化2：使用生成器节省内存"""
        content = content.replace('\r\n', '\n')
        
        try:
            # 获取用户设置的正则表达式，如果无效则使用默认值
            log_pattern_text = log_regex_edit.toPlainText().strip() or self.LOG_REGEX_PATTERN
            log_pattern = re.compile(log_pattern_text, re.DOTALL)
        except re.error:
            logging.warning("日志匹配正则表达式无效，使用默认值")
            log_pattern = re.compile(self.LOG_REGEX_PATTERN, re.DOTALL)
        
        try:
            # 获取用户设置的时间正则表达式
            time_pattern_text = time_regex_edit.toPlainText().strip() or self.TIME_REGEX_PATTERN
            time_pattern = re.compile(time_pattern_text)
        except re.error:
            logging.warning("时间匹配正则表达式无效，使用默认值")
            time_pattern = re.compile(self.TIME_REGEX_PATTERN)
        
        for match in log_pattern.finditer(content):
            entry = match.group(1).strip()
            if entry:
                yield entry

    def process_log_files(self, uploaded_files: List[io.BytesIO], file_names: List[str], log_regex_edit, time_regex_edit, progress_callback=None) -> tuple[list, list]:
        total_files = len(uploaded_files)
        def process_file_content(file_obj: io.BytesIO, file_name: str) -> tuple[list, str]:
            """处理单个文件的内容"""
            result_logs = []
            content = None
            decode_error = None
            try:
                file_obj.seek(0)
                raw = file_obj.read()
                # 优先：charset-normalizer 自动检测
                try:
                    from charset_normalizer import from_bytes
                    best = from_bytes(raw).best()
                    if best:
                        content = str(best)
                except Exception:
                    # 回退：chardet 自动检测
                    try:
                        import chardet
                        detected = chardet.detect(raw)
                        enc = detected.get('encoding')
                        if enc:
                            content = raw.decode(enc, errors='replace')
                    except Exception as e:
                        decode_error = e
                # 最终回退：手动编码列表
                if content is None:
                    encodings = ['utf-8', 'gbk', 'gb2312', 'big5', 'utf-16', 'utf-16le', 'utf-16be', 'latin1']
                    for encoding in encodings:
                        try:
                            content = raw.decode(encoding)
                            break
                        except (UnicodeDecodeError, UnicodeError) as e:
                            decode_error = e
            except Exception as e:
                decode_error = e
            if content is None:
                logging.error(f"无法解码文件: {file_name}, 尝试编码: {', '.join(encodings)}")
                if self.parent:
                    QMessageBox.warning(self.parent, "解码错误", 
                        f"无法解码文件：\n{file_name}\n"
                        f"尝试编码：{', '.join(encodings)}\n"
                        f"错误信息：{str(decode_error) if decode_error else '未知错误'}")
                return [], file_name
            # 修正：整体处理，不分块，避免日志被截断
            entries = list(self.parse_log_entries(content, log_regex_edit, time_regex_edit))
            logging.debug(f"[正则解析] 文件: {file_name}, 解析日志条数: {len(entries)}")
            entry_count = 0
            for entry in entries:
                try:
                    log_info = self.extract_log_info(entry, file_name)
                    result_logs.append(log_info)
                    entry_count += 1
                except Exception as e:
                    logging.error(f"提取日志信息时出错: {e}")
            if entry_count == 0:
                logging.warning(f"[警告] 文件: {file_name} 未解析出任何日志条目！")
            else:
                logging.info(f"[完成] 文件: {file_name} 共解析日志条目: {entry_count}")
            return result_logs, file_name
            
        # 使用线程池并行处理文件
        all_logs = []
        failed_files = []
        with ThreadPoolExecutor(max_workers=min(os.cpu_count() or 1, len(uploaded_files))) as executor:
            futures = []
            for file_obj, file_name in zip(uploaded_files, file_names):
                try:
                    future = executor.submit(process_file_content, file_obj, file_name)
                    futures.append(future)
                except Exception as e:
                    logging.error(f"提交文件处理任务时出错: {e}")
            for idx, future in enumerate(futures):
                try:
                    result_logs, file_name = future.result()
                    if not result_logs:
                        failed_files.append(file_name)
                    else:
                        all_logs.extend(result_logs)
                except Exception as e:
                    logging.error(f"处理文件时发生异常: {e}")
                # 新增：进度回调
                if progress_callback:
                    progress = int(((idx + 1) / total_files) * 50)
                    progress_callback(progress)
        all_logs.sort(key=lambda x: x.timestamp if x.timestamp else datetime.datetime.min)
        
        if progress_callback:
            progress_callback(60)  # 处理完文件后，进度到60%
        
        return all_logs, failed_files

    def filter_logs_by_time_range(
        self, 
        logs: Iterable[LogEntry], 
        start_time: Optional[datetime.datetime], 
        end_time: Optional[datetime.datetime]
    ) -> List[LogEntry]:
        """根据时间范围过滤日志 - 优化2：使用生成器节省内存"""
        result = []
        for log in logs:
            timestamp = log.timestamp
            if not timestamp:
                logging.debug(f"[过滤] 无时间戳被过滤: {log.content}")
                continue
            if start_time and timestamp < start_time:
                logging.debug(f"[过滤] 早于开始时间被过滤: {log.content}")
                continue
            if end_time and timestamp > end_time:
                logging.debug(f"[过滤] 晚于结束时间被过滤: {log.content}")
                continue
            result.append(log)
        return result

    def filter_logs_by_keywords(self, logs: Iterable[LogEntry], keywords: List[str]) -> List[LogEntry]:
        """根据关键词过滤日志 - 优化2：分批处理避免内存溢出"""
        if not keywords:
            return list(logs)
        
        valid_keywords = [k.strip() for k in keywords if k.strip()]
        
        if not valid_keywords:
            return list(logs)
        
        # 检查是否有正则表达式特殊字符
        has_regex_chars = any(re.search(r'[.*+?^${}()|[\]\\]', k) for k in valid_keywords)
        
        filtered_logs = []
        batch_size = 10000  # 分批处理大小
        batch = []
        
        if has_regex_chars:
            try:
                combined_pattern = re.compile("|".join(k for k in valid_keywords), re.IGNORECASE)
                use_combined = True
            except Exception:
                patterns = [re.compile(k, re.IGNORECASE) for k in valid_keywords]
                use_combined = False
            
            for log in logs:
                content = log.content
                
                if use_combined:
                    if combined_pattern.search(content):
                        batch.append(log)
                else:
                    if any(p.search(content) for p in patterns):
                        batch.append(log)
                
                # 分批处理，避免内存溢出
                if len(batch) >= batch_size:
                    filtered_logs.extend(batch)
                    batch = []
        else:
            lowercase_keywords = [k.lower() for k in valid_keywords]
            
            for log in logs:
                content = log.content.lower()
                
                if any(keyword in content for keyword in lowercase_keywords):
                    batch.append(log)
                
                # 分批处理，避免内存溢出
                if len(batch) >= batch_size:
                    filtered_logs.extend(batch)
                    batch = []
        
        # 添加最后一批
        filtered_logs.extend(batch)
        return filtered_logs
