#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Excel写入工具模块
用于处理Excel文件的写入和格式化
"""

import os
import pandas as pd
from datetime import datetime
from .logger import logger


class ExcelWriter:
    """
    Excel写入器类
    负责将分析结果写入Excel文件并设置格式
    """
    
    def __init__(self, output_dir=None, filename_prefix="关键词分析结果"):
        """
        初始化Excel写入器
        
        参数:
        - output_dir: 输出目录路径
        - filename_prefix: 文件名前缀
        """
        # 确保results文件夹存在
        self.output_dir = output_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
        os.makedirs(self.output_dir, exist_ok=True)
        self.filename_prefix = filename_prefix
    
    def export_to_excel(self, summary_df, additional_sheets=None, export_folder=None):
        """
        导出数据到Excel文件并设置格式
        
        参数:
        - summary_df: 汇总数据的DataFrame
        - additional_sheets: 额外的工作表数据字典 {sheet_name: df}
        - export_folder: 导出文件夹路径（可选）
        
        返回:
        - 输出文件路径
        """
        # 将NaN值替换为空字符串
        summary_df = summary_df.fillna('')
        
        # 确定导出文件夹
        if export_folder:
            results_folder = export_folder
        else:
            # 默认路径
            results_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')
        
        # 创建结果文件夹（如果不存在）
        if not os.path.exists(results_folder):
            os.makedirs(results_folder)
            logger.info(f"创建结果文件夹: {results_folder}")
        
        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(results_folder, f'{self.filename_prefix}_{timestamp}.xlsx')
        
        logger.info(f"开始导出Excel文件: {output_file}")
        
        try:
            with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                # 保存汇总数据
                summary_df.to_excel(writer, sheet_name='关键词分析汇总', index=False)
                
                # 保存额外的工作表
                if additional_sheets:
                    for sheet_name, df in additional_sheets.items():
                        df = df.fillna('')
                        df.to_excel(writer, sheet_name=sheet_name[:31], index=False)  # Excel工作表名称最多31个字符
                
                # 获取xlsxwriter工作簿和工作表对象
                workbook = writer.book
                worksheet = writer.sheets['关键词分析汇总']
                
                # 设置Excel格式
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1})
                
                # 设置列宽
                worksheet.set_column('A:A', 30)  # 主题列宽
                worksheet.set_column('B:B', 50)  # 关键词列宽
                worksheet.set_column('C:C', 15)  # 搜索量列宽
                
                # 设置标题格式
                for col_num, value in enumerate(summary_df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # 自动筛选
                worksheet.autofilter(0, 0, len(summary_df), 2)
                
                # 添加条件格式，使相同主题词的行有相似的背景色
                self._apply_theme_colors(worksheet, summary_df, workbook)
            
            logger.info(f"Excel文件导出成功: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"导出Excel文件时出错: {str(e)}")
            return None
    
    def _apply_theme_colors(self, worksheet, df, workbook):
        """
        为相同主题词的行应用相似的背景色
        
        参数:
        - worksheet: xlsxwriter worksheet对象
        - df: 数据DataFrame
        - workbook: xlsxwriter workbook对象
        """
        theme_colors = {}
        current_color_index = 0
        colors = ['#FFEEEE', '#EEFFEE', '#EEEEFF', '#FFFFEE', '#FFEEFF', '#EEFFFF']
        
        # 为每个主题词分配一个颜色
        for row_num, topic in enumerate(df['主题词'], start=1):
            if topic not in theme_colors:
                theme_colors[topic] = colors[current_color_index % len(colors)]
                current_color_index += 1
            
            row_format = workbook.add_format({'bg_color': theme_colors[topic]})
            worksheet.set_row(row_num, cell_format=row_format)
    
    def export_detailed_report(self, results_dict):
        """
        导出详细报告，包含每个主题的单独工作表
        
        参数:
        - results_dict: 结果字典，格式为 {topic: [{keyword, search_volume}, ...]}
        
        返回:
        - 输出文件路径
        """
        # 创建汇总数据
        summary_data = []
        sheets_data = {}
        
        for topic, keywords_data in results_dict.items():
            # 添加到汇总数据
            for item in keywords_data:
                summary_data.append({
                    '主题词': topic,
                    '关键词': item['keyword'],
                    '搜索量': item['search_volume']
                })
            
            # 创建主题单独的工作表数据
            topic_df = pd.DataFrame(keywords_data)
            topic_df = topic_df.sort_values(by='search_volume', ascending=False)
            sheets_data[topic] = topic_df
        
        # 创建汇总DataFrame并排序
        summary_df = pd.DataFrame(summary_data)
        summary_df = summary_df.sort_values(by=['主题词', '搜索量'], ascending=[True, False])
        
        # 导出到Excel
        return self.export_to_excel(summary_df, sheets_data)