#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置管理模块
负责加载和管理项目的所有配置信息
"""

import os
import re
from datetime import datetime
from dotenv import load_dotenv
from utils.logger import logger


class ConfigManager:
    """
    配置管理器类 - 负责加载和提供所有配置信息
    """
    
    def __init__(self):
        """
        初始化配置管理器
        """
        # 设置根目录
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 加载.env文件
        env_file = os.path.join(self.root_dir, '.env')
        if os.path.exists(env_file):
            load_dotenv(env_file)
            logger.info(f"已加载.env文件: {env_file}")
        else:
            logger.warning(f".env文件不存在: {env_file}")
        
        # 基本路径配置 - 支持从环境变量配置
        self.data_folder = os.environ.get('DATA_FOLDER', os.path.join(self.root_dir, 'data'))
        self.results_folder = os.environ.get('RESULTS_FOLDER', os.path.join(self.root_dir, 'results'))
        self.logs_folder = os.environ.get('LOGS_FOLDER', os.path.join(self.root_dir, 'logs'))
        
        # 关键词相关配置
        self.default_keyword_columns = [
            'Keyword', 'keyword', 'Query', 'query', 'Search Term', 
            'search term', '搜索词', '关键词'
        ]
        self.default_volume_columns = [
            'volume', 'search volume', 'Volume', 'Search Volume', 
            '搜索量', '月搜索量'
        ]
        
        # 先设置临时默认值，避免循环依赖
        self.default_keyword_patterns = ''
        logger.info("开始从keywords.md文件读取关键词")
        # 然后从keywords.md文件读取关键词
        keyword_patterns = self.load_keyword_patterns_from_markdown()
        logger.info(f"从keywords.md读取到的关键词模式: {keyword_patterns}")
        if keyword_patterns:
            self.default_keyword_patterns = keyword_patterns
            logger.info(f"已设置默认关键词模式: {self.default_keyword_patterns}")
        else:
            logger.warning("未从keywords.md文件读取到关键词，使用空默认模式")
        
        # 输出文件配置 - 支持从环境变量配置
        self.default_output_filename_prefix = os.environ.get('OUTPUT_FILENAME_PREFIX', '关键词分析结果')
        
        # AI模型类型配置
        self.ai_model_type = os.environ.get('AI_MODEL_TYPE', 'deepseek').lower()
        
        # DeepSeek模型配置
        self.deepseek_endpoint = os.environ.get('DEEPSEEK_ENDPOINT', '')
        self.deepseek_api_key = os.environ.get('DEEPSEEK_API_KEY', '')
        
        # 通义模型配置
        self.tongyi_endpoint = os.environ.get('TONGYI_ENDPOINT', '')
        self.tongyi_api_key = os.environ.get('TONGYI_API_KEY', '')
        
        # 通用AI参数
        self.ai_max_batch_size = int(os.environ.get('AI_MAX_BATCH_SIZE', 50))
        self.ai_timeout = int(os.environ.get('AI_TIMEOUT', 30))
        self.ai_retry_attempts = int(os.environ.get('AI_RETRY_ATTEMPTS', 3))
        self.ai_retry_delay = int(os.environ.get('AI_RETRY_DELAY', 2))
        
        # 根据模型类型设置当前使用的API配置
        if self.ai_model_type == 'tongyi':
            logger.info(f"已配置通义模型: {self.ai_model_type}")
            self.ai_api_endpoint = self.tongyi_endpoint
            self.ai_api_key = self.tongyi_api_key
        else:  # 默认使用deepseek
            logger.info(f"已配置DeepSeek模型: {self.ai_model_type}")
            self.ai_api_endpoint = self.deepseek_endpoint
            self.ai_api_key = self.deepseek_api_key
            self.ai_model_type = 'deepseek'
        
        # 确保必要的文件夹存在
        self._ensure_directories()
        
    def _get_config_value(self, config_name, default_value=''):
        """
        获取配置值，可以从环境变量读取
        
        参数:
        - config_name: 配置名称
        - default_value: 默认值
        
        返回:
        - 配置值
        """
        return os.environ.get(config_name, default_value)
    
    def _ensure_directories(self):
        """
        确保必要的文件夹存在
        """
        for folder in [self.data_folder, self.results_folder, self.logs_folder]:
            if not os.path.exists(folder):
                os.makedirs(folder)
                logger.info(f"创建文件夹: {folder}")
    
    def get_ai_api_config(self):
        """
        获取AI API配置
        
        返回:
        - 包含endpoint和key的字典
        """
        return {
            'model_type': self.ai_model_type,
            'endpoint': self.ai_api_endpoint,
            'key': self.ai_api_key,
            'max_batch_size': self.ai_max_batch_size,
            'timeout': self.ai_timeout,
            'retry_attempts': self.ai_retry_attempts,
            'retry_delay': self.ai_retry_delay,
            # 同时返回所有模型的配置，便于切换
            'deepseek': {
                'endpoint': self.deepseek_endpoint,
                'key': self.deepseek_api_key
            },
            'tongyi': {
                'endpoint': self.tongyi_endpoint,
                'key': self.tongyi_api_key
            }
        }
    
    def get_keyword_config(self):
        """
        获取关键词相关配置
        
        返回:
        - 关键词配置字典
        """
        return {
            'keyword_columns': self.default_keyword_columns,
            'volume_columns': self.default_volume_columns,
            'default_patterns': self.default_keyword_patterns
        }
    
    def get_path_config(self):
        """
        获取路径相关配置
        
        返回:
        - 路径配置字典
        """
        return {
            'root_dir': self.root_dir,
            'data_folder': self.data_folder,
            'results_folder': self.results_folder,
            'logs_folder': self.logs_folder
        }
    
    def get_export_config(self):
        """
        获取导出相关配置
        
        返回:
        - 导出配置字典
        """
        return {
            'output_filename_prefix': self.default_output_filename_prefix,
            'excel_format': {
                'header_bg_color': '#4472C4',
                'header_text_color': '#FFFFFF',
                'alternating_row_colors': ['#FFFFFF', '#F2F2F2']
            }
        }
    
    def load_keyword_patterns_from_markdown(self, custom_folder=None):
        """
        从markdown文件加载关键词筛选规则
        
        参数:
        - custom_folder: 自定义的markdown文件所在文件夹
        
        返回:
        - 关键词筛选规则字符串
        """
        folder = custom_folder or self.data_folder
        
        if not os.path.exists(folder):
            logger.warning(f"数据文件夹不存在: {folder}")
            return self.default_keyword_patterns
            
        logger.info(f"开始从markdown文件读取关键词筛选规则，文件夹: {folder}")
        
        # 查找文件夹中的所有markdown文件
        md_files = []
        for file in os.listdir(folder):
            if file.endswith(('.md', '.markdown')):
                file_path = os.path.join(folder, file)
                md_files.append(file_path)
                logger.info(f"发现markdown文件: {file_path}")
        
        if not md_files:
            logger.info("未发现markdown文件，使用默认关键词筛选规则")
            return self.default_keyword_patterns
        
        # 合并所有markdown文件中的关键词筛选规则
        patterns = []
        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 简单的处理：读取所有非空行作为关键词
                    lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('#')]
                    if lines:
                        patterns.extend(lines)
                        logger.info(f"从 {md_file} 读取了 {len(lines)} 个关键词")
            except Exception as e:
                logger.error(f"读取markdown文件 {md_file} 时出错: {str(e)}")
        
        # 如果找到关键词，返回合并后的规则
        if patterns:
            # 创建正则表达式模式，使用OR连接所有关键词
            pattern_str = '|'.join([re.escape(pattern) for pattern in patterns])
            logger.info(f"已加载关键词筛选规则，共 {len(patterns)} 个关键词")
            return pattern_str
        else:
            logger.warning("markdown文件中未找到有效关键词")
            return self.default_keyword_patterns
    
    def set_ai_api_config(self, endpoint, api_key):
        """
        设置AI API配置
        
        参数:
        - endpoint: API端点
        - api_key: API密钥
        """
        self.ai_api_endpoint = endpoint
        self.ai_api_key = api_key
        logger.info("已更新AI API配置")
    
    def save_config_to_env(self, config_dict=None, env_file=None):
        """
        将当前配置保存到.env文件
        
        参数:
        - config_dict: 要保存的配置字典，None则使用当前配置
        - env_file: .env文件路径，None则使用默认路径
        
        返回:
        - 是否保存成功
        """
        try:
            if env_file is None:
                env_file = os.path.join(self.root_dir, '.env')
            
            # 准备配置数据
            config_to_save = config_dict or {
                'DATA_FOLDER': self.data_folder,
                'RESULTS_FOLDER': self.results_folder,
                'LOGS_FOLDER': self.logs_folder,
                'OUTPUT_FILENAME_PREFIX': self.default_output_filename_prefix,
                'AI_API_ENDPOINT': self.ai_api_endpoint,
                'AI_API_KEY': self.ai_api_key,
                'AI_MAX_BATCH_SIZE': self.ai_max_batch_size,
                'AI_TIMEOUT': self.ai_timeout,
                'AI_RETRY_ATTEMPTS': self.ai_retry_attempts,
                'AI_RETRY_DELAY': self.ai_retry_delay
            }
            
            # 读取现有内容，排除需要更新的配置
            existing_config = {}
            if os.path.exists(env_file):
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            # 只保留不在config_to_save中的配置项
                            if key not in config_to_save:
                                existing_config[key] = value
            
            # 合并配置
            existing_config.update(config_to_save)
            
            # 写入.env文件
            with open(env_file, 'w', encoding='utf-8') as f:
                # 添加注释说明
                f.write(f"# SEO关键词分析工具配置文件\n")
                f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # 路径配置
                f.write("# 路径配置\n")
                for key in ['DATA_FOLDER', 'RESULTS_FOLDER', 'LOGS_FOLDER']:
                    if key in existing_config:
                        f.write(f"{key}={existing_config[key]}\n")
                
                # AI API配置
                f.write("\n# AI API配置\n")
                ai_keys = ['AI_API_ENDPOINT', 'AI_API_KEY', 'AI_MAX_BATCH_SIZE', 'AI_TIMEOUT', 'AI_RETRY_ATTEMPTS', 'AI_RETRY_DELAY']
                for key in ai_keys:
                    if key in existing_config:
                        f.write(f"{key}={existing_config[key]}\n")
                
                # 导出配置
                f.write("\n# 导出配置\n")
                if 'OUTPUT_FILENAME_PREFIX' in existing_config:
                    f.write(f"OUTPUT_FILENAME_PREFIX={existing_config['OUTPUT_FILENAME_PREFIX']}\n")
                
                # 其他配置
                other_configs = {k: v for k, v in existing_config.items() if k not in ['DATA_FOLDER', 'RESULTS_FOLDER', 'LOGS_FOLDER', 'OUTPUT_FILENAME_PREFIX'] + ai_keys}
                if other_configs:
                    f.write("\n# 其他配置\n")
                    for key, value in other_configs.items():
                        f.write(f"{key}={value}\n")
            
            logger.info(f"配置已保存到: {env_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置到.env文件时出错: {str(e)}")
            return False
            
    # 保持向后兼容
    def save_to_env_file(self):
        """
        将当前配置保存到.env文件（向后兼容方法）
        
        返回:
        - 是否保存成功
        """
        return self.save_config_to_env()


# 创建全局配置实例
config_manager = ConfigManager()