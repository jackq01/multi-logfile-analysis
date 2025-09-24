from PyQt5.QtWidgets import (QStyledItemDelegate, QApplication, QStyle, QStyleOptionViewItem)
from PyQt5.QtGui import QColor, QFontMetrics
from PyQt5.QtCore import Qt, QRect

class HighlightDelegate(QStyledItemDelegate):
    """自定义委托用于高亮显示关键词"""
    
    def paint(self, painter, option, index):
        painter.save()
        
        # 获取文本区域和复选框区域
        style = self.parent().style() if self.parent() else QApplication.style()
        check_rect = style.subElementRect(QStyle.SE_ItemViewItemCheckIndicator, option, self.parent())
        text_rect = option.rect
        
        # 设置文本区域，为右侧复选框预留空间
        text_rect.setRight(text_rect.right() - check_rect.width() - 10)
        
        # 绘制文本背景
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            bg = index.data(Qt.BackgroundRole)
            if bg is None:
                bg = QColor("#FFFFFF")
            painter.fillRect(option.rect, bg)
        
        # 多行文本处理，逐行绘制并高亮关键词
        text = index.data(Qt.DisplayRole)
        highlight_data = index.data(Qt.UserRole + 1)
        lines = text.splitlines() if text else []
        y = text_rect.top()
        line_height = QFontMetrics(option.font).height()
        for line_idx, line in enumerate(lines):
            # 计算当前行的rect
            line_rect = QRect(text_rect.left(), y, text_rect.width(), line_height)
            x_cursor = line_rect.left()
            # 获取本行的高亮片段
            if highlight_data:
                # 找出属于本行的高亮片段
                line_start = sum(len(l)+1 for l in lines[:line_idx])  # +1 for '\n'
                line_end = line_start + len(line)
                # 过滤出本行的高亮片段
                line_highlights = [(start, end, fmt) for start, end, fmt in highlight_data if start >= line_start and end <= line_end]
                # 按顺序绘制本行内容
                cursor = 0
                for h_start, h_end, fmt in line_highlights:
                    # 相对本行的索引
                    rel_start = h_start - line_start
                    rel_end = h_end - line_start
                    # 普通文本
                    normal_text = line[cursor:rel_start]
                    if normal_text:
                        painter.setPen(option.palette.color(option.palette.Text))
                        painter.setFont(option.font)
                        rect_left = x_cursor
                        seg_rect = QRect(rect_left, line_rect.top(), line_rect.width() - (rect_left - line_rect.left()), line_rect.height())
                        painter.drawText(seg_rect, Qt.AlignLeft | Qt.AlignVCenter, normal_text)
                        fm = QFontMetrics(painter.font())
                        try:
                            advance = fm.horizontalAdvance(normal_text)
                        except AttributeError:
                            advance = fm.width(normal_text)
                        x_cursor += advance
                    # 高亮文本
                    highlight_text = line[rel_start:rel_end]
                    if highlight_text:
                        painter.setPen(fmt.foreground().color())
                        painter.setFont(fmt.font() if fmt.font() else option.font)
                        rect_left = x_cursor
                        seg_rect = QRect(rect_left, line_rect.top(), line_rect.width() - (rect_left - line_rect.left()), line_rect.height())
                        painter.drawText(seg_rect, Qt.AlignLeft | Qt.AlignVCenter, highlight_text)
                        fm_h = QFontMetrics(painter.font())
                        try:
                            advance_h = fm_h.horizontalAdvance(highlight_text)
                        except AttributeError:
                            advance_h = fm_h.width(highlight_text)
                        x_cursor += advance_h
                    cursor = rel_end
                # 剩余普通文本
                if cursor < len(line):
                    painter.setPen(option.palette.color(option.palette.Text))
                    painter.setFont(option.font)
                    remaining_text = line[cursor:]
                    rect_left = x_cursor
                    seg_rect = QRect(rect_left, line_rect.top(), line_rect.width() - (rect_left - line_rect.left()), line_rect.height())
                    painter.drawText(seg_rect, Qt.AlignLeft | Qt.AlignVCenter, remaining_text)
            else:
                painter.setPen(option.palette.color(option.palette.Text))
                painter.setFont(option.font)
                painter.drawText(line_rect, Qt.AlignLeft | Qt.AlignVCenter, line)
            y += line_height
        
        # 绘制复选框
        if option.features & QStyleOptionViewItem.HasCheckIndicator:
            checkbox_option = QStyleOptionViewItem(option)
            checkbox_option.rect = check_rect
            checkbox_option.state = checkbox_option.state & ~QStyle.State_HasFocus
            
            if index.data(Qt.CheckStateRole) == Qt.Checked:
                checkbox_option.state |= QStyle.State_On
            else:
                checkbox_option.state |= QStyle.State_Off
            
            style.drawPrimitive(QStyle.PE_IndicatorViewItemCheck, checkbox_option, painter)
        
        painter.restore()
