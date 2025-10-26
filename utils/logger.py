#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志记录工具模块
用于处理项目中的日志记录功能
"""

import os
import logging
import sys
from datetime import datetime


def setup_logger(log_file_prefix="keyword_analysis"):
    """
    设置日志记录器
    
    参数:
    - log_file_prefix: 日志文件名前缀
    
    返回:
    - 配置好的logger实例
    """
    # 确保logs文件夹存在
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 生成日志文件名
    current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f"{log_file_prefix}_{current_time}.log")
    
    # 创建logger
    logger = logging.getLogger('keyword_analyzer')
    logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if not logger.handlers:
        # 在Windows控制台强制使用UTF-8，避免中文乱码
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

        # 创建文件handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建控制台handler（绑定到UTF-8的stdout）
        console_handler = logging.StreamHandler(stream=sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # 定义日志格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加handler到logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    logger.info(f"日志文件已创建: {log_file}")
    return logger


# 创建默认logger实例
logger = setup_logger()