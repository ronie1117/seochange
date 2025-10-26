#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
关键词管理器模块
负责关键词筛选规则的保存和管理
"""

import os
import re
from utils.logger import logger
from core.config import config_manager


class KeywordManager:
    """
    关键词管理器类
    提供关键词筛选规则的保存功能
    """
    
    def __init__(self, data_folder=None):
        """
        初始化关键词管理器
        
        参数:
        - data_folder: 数据文件夹路径，默认使用配置管理器中的数据文件夹
        """
        # 使用配置管理器中的数据文件夹或自定义路径
        self.data_folder = data_folder or config_manager.data_folder
        # 关键词文件路径
        self.keyword_file_path = os.path.join(self.data_folder, 'keywords.md')
        
        # 确保数据文件夹存在
        self._ensure_data_folder_exists()
        
    def _ensure_data_folder_exists(self):
        """
        确保数据文件夹存在，如果不存在则创建
        """
        try:
            if not os.path.exists(self.data_folder):
                os.makedirs(self.data_folder)
                logger.info(f"创建数据文件夹: {self.data_folder}")
        except Exception as e:
            logger.error(f"创建数据文件夹时出错: {str(e)}")
    
    def save_keywords(self, keyword_input):
        """
        保存关键词筛选规则到keywords.md文件
        
        参数:
        - keyword_input: 输入框中的关键词规则字符串，可以是逗号分隔、换行分隔或空格分隔
        
        返回:
        - bool: 保存是否成功
        - list: 提取出的关键词列表
        """
        try:
            # 检查输入是否为空
            if not keyword_input or not keyword_input.strip():
                logger.warning("关键词输入为空，未保存")
                return False, []
            
            # 处理输入字符串，支持多种分隔方式
            # 首先按逗号分割
            keywords = keyword_input.split(',')
            
            # 然后对每个分割后的部分按换行和空格进一步分割并清理
            cleaned_keywords = []
            for kw in keywords:
                # 按换行分割
                lines = kw.split('\n')
                for line in lines:
                    # 按空格分割
                    words = line.split()
                    for word in words:
                        # 清理并添加非空关键词
                        cleaned_word = word.strip()
                        if cleaned_word:
                            cleaned_keywords.append(cleaned_word)
            
            # 去重
            unique_keywords = list(set(cleaned_keywords))
            unique_keywords.sort()  # 排序以便于阅读
            
            logger.info(f"提取到 {len(unique_keywords)} 个关键词规则")
            
            # 写入到keywords.md文件
            with open(self.keyword_file_path, 'w', encoding='utf-8') as f:
                # 写入文件头说明
                f.write("# 关键词筛选规则\n")
                f.write("# 每行一个关键词，系统会使用这些关键词来筛选数据\n")
                f.write("\n")
                
                # 写入每个关键词
                for keyword in unique_keywords:
                    f.write(f"{keyword}\n")
            
            logger.info(f"关键词规则已成功保存到: {self.keyword_file_path}")
            return True, unique_keywords
            
        except Exception as e:
            logger.error(f"保存关键词规则时出错: {str(e)}")
            return False, []
    
    def load_keywords(self):
        """
        从keywords.md文件加载关键词规则
        
        返回:
        - list: 关键词规则列表，如果文件不存在则返回空列表
        """
        try:
            if not os.path.exists(self.keyword_file_path):
                logger.warning(f"关键词文件不存在: {self.keyword_file_path}")
                return []
            
            keywords = []
            with open(self.keyword_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释行和空行
                    if line and not line.startswith('#') and not line.startswith('---'):
                        keywords.append(line)
            
            logger.info(f"从文件加载了 {len(keywords)} 个关键词规则")
            return keywords
            
        except Exception as e:
            logger.error(f"加载关键词规则时出错: {str(e)}")
            return []
    
    def clear_keyword_rules(self):
        """
        清空关键词规则文件
        
        返回:
        - bool: 清空是否成功
        """
        try:
            if os.path.exists(self.keyword_file_path):
                os.remove(self.keyword_file_path)
                logger.info(f"关键词规则文件已删除: {self.keyword_file_path}")
            else:
                logger.info(f"关键词规则文件不存在，无需删除: {self.keyword_file_path}")
            return True
        except Exception as e:
            logger.error(f"清空关键词规则时出错: {str(e)}")
            return False
    
    def create_keyword_pattern(self, keywords):
        """
        将关键词列表转换为正则表达式模式
        
        参数:
        - keywords: 关键词列表
        
        返回:
        - str: 正则表达式模式字符串
        """
        if not keywords:
            logger.warning("关键词列表为空，返回空模式")
            return ''
        
        # 转义关键词并使用OR连接
        escaped_keywords = [re.escape(keyword) for keyword in keywords]
        pattern = '|'.join(escaped_keywords)
        
        logger.info(f"已创建关键词正则表达式模式，包含 {len(keywords)} 个关键词")
        return pattern


# 创建全局关键词管理器实例，方便其他模块使用
keyword_manager = KeywordManager()