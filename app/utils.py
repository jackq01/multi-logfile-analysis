import logging
import sys
import re
import datetime
import colorsys
import os
import io
from collections import namedtuple
from typing import List, Dict, Tuple, Optional, Set, Any, Generator, Iterable
from PyQt5.QtGui import QColor

# 使用namedtuple优化内存占用
LogEntry = namedtuple('LogEntry', ['content', 'timestamp', 'source_file', 'time_str'])

def generate_light_colors(count, file_list) -> dict:
    """生成浅色系背景颜色并确保区分度高（支持最多100个文件）"""
    colors_by_file = {}
    
    # 固定饱和度范围0.3-0.5，亮度范围0.85-0.95，生成浅色系
    saturation_range = (0.3, 0.5)
    lightness_range = (0.85, 0.95)
    
    # 使用黄金角分布确保颜色均匀分布
    golden_angle = 0.618033988749895
    hue = 0.0
    
    for idx, file_path in enumerate(file_list):
        # 使用固定算法确保一致性
        hue = (hue + golden_angle) % 1.0
        saturation = saturation_range[0] + (saturation_range[1] - saturation_range[0]) * (idx % 3)/3
        lightness = lightness_range[0] + (lightness_range[1] - lightness_range[0]) * (idx % 5)/5
        
        # 转换为RGB
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        color = QColor(int(r * 255), int(g * 255), int(b * 255))
        
        # 特殊处理：确保颜色是浅色（如果超过阈值则调整）
        if color.lightness() < 200:  # 确保是浅色背景
            color = color.lighter(150)
            
        colors_by_file[file_path] = color
    
    return colors_by_file

def generate_fixed_light_colors(n: int) -> List[str]:
    """生成n个固定的、区分度高的浅色系颜色"""
    fixed_colors = [
        "#AEDFF7", "#C7E9B0", "#FFD6A5", "#ECCAFA", "#FFF1A7",
        "#FFBDBD", "#A5F7E1", "#D9D9D9", "#FFC4BC", "#BDD7FF"
    ]
    
    if n > len(fixed_colors):
        for i in range(len(fixed_colors), n):
            hue = (i * 0.618033988749895) % 1
            saturation = 0.5
            lightness = 0.85
            r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
            color = "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))
            fixed_colors.append(color)
    
    return fixed_colors[:n]

def parse_log_time(time_str: str, time_regex_pattern: str) -> Optional[datetime.datetime]:
    """解析日志中的时间字符串"""
    try:
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        # 更健壮的时间匹配正则表达式
        match = re.search(time_regex_pattern, time_str)
        if match:
            month_str, day, hour, minute, second, millisecond, year = match.groups()
            month = month_map.get(month_str, 1)
            
            dt = datetime.datetime(
                int(year), month, int(day), 
                int(hour), int(minute), int(second), 
                int(millisecond) * 1000
            )
            return dt
    except Exception:
        return None
    
    return None
