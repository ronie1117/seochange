#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
关键词分析器核心模块
负责关键词的加载、筛选、分类和分析
"""

import os
import re
import pandas as pd
import requests
import json
from collections import defaultdict
from utils.logger import logger
from utils.excel_writer import ExcelWriter
from core.config import config_manager


class KeywordAnalyzer:
    """
    关键词分析器类 - 用于分析和分类Excel文件中的关键词
    
    支持通过调用AI模型进行智能分类，或使用自定义分类函数
    """
    
    def __init__(self, data_folder=None, keyword_patterns=None, categorize_func=None,
                 keyword_columns=None, volume_columns=None, output_filename_prefix=None,
                 ai_api_endpoint=None, ai_api_key=None, progress_callback=None):
        """
        初始化关键词分析器
        
        参数:
        - data_folder: 数据文件夹路径（可选，默认从配置管理器获取）
        - keyword_patterns: 用于筛选关键词的正则表达式模式（可选）
        - categorize_func: 自定义的主题分类函数（可选）
        - keyword_columns: 可能的关键词列名列表（可选，默认从配置管理器获取）
        - volume_columns: 可能的搜索量列名列表（可选，默认从配置管理器获取）
        - output_filename_prefix: 输出文件名前缀（可选，默认从配置管理器获取）
        - ai_api_endpoint: AI模型API端点（可选，默认从配置管理器获取）
        - ai_api_key: AI模型API密钥（可选，默认从配置管理器获取）
        """
        # 保存配置管理器引用
        self.config_manager = config_manager
        
        # 从配置管理器获取默认配置
        path_config = config_manager.get_path_config()
        keyword_config = config_manager.get_keyword_config()
        export_config = config_manager.get_export_config()
        ai_config = config_manager.get_ai_api_config()
        
        # 初始化配置，传入的参数优先于配置管理器的默认值
        self.data_folder = data_folder or path_config['data_folder']
        
        # 先设置默认关键词模式，确保不会为None
        fallback_keywords = ['slide', 'ppt', 'powerpoint', 'presentation']
        self.keyword_patterns = '|'.join([re.escape(pattern) for pattern in fallback_keywords])
        logger.info(f"初始化时设置默认关键词模式: {self.keyword_patterns}")
        
        # 如果传入了自定义模式，使用它
        if keyword_patterns:
            self.keyword_patterns = keyword_patterns
            logger.info(f"使用传入的关键词模式")
        
        self.categorize_func = categorize_func or self.ai_categorize  # 默认使用AI分类
        self.keyword_columns = keyword_columns or keyword_config['keyword_columns']
        self.volume_columns = volume_columns or keyword_config['volume_columns']
        self.output_filename_prefix = output_filename_prefix or export_config['output_filename_prefix']
        
        # 初始化数据存储
        self.all_keywords = {}
        self.filtered_keywords = pd.DataFrame()
        
        # AI API配置
        self.ai_api_endpoint = ai_api_endpoint or ai_config['endpoint']
        self.ai_api_key = ai_api_key or ai_config['key']
        
        # 初始化Excel写入器
        self.excel_writer = ExcelWriter(filename_prefix=self.output_filename_prefix)
        
        # 使用配置管理器中的结果文件夹路径
        self.results_folder = path_config['results_folder']

        # 进度回调（可选），用于向外部报告分析进度
        self.progress_callback = progress_callback
        
        # 从markdown文件读取关键词筛选规则 - 这可能会覆盖上面设置的默认值
        logger.info("调用read_keyword_patterns_from_markdown方法")
        self.read_keyword_patterns_from_markdown()
    
    def ai_categorize(self, keyword):
        """
        通过AI模型对关键词进行分类
        
        参数:
        - keyword: 待分类的关键词
        
        返回:
        - 分类结果
        """
        keyword_str = str(keyword).strip()
        
        # 如果API配置不存在，使用简单的默认分类
        if not self.ai_api_endpoint or not self.ai_api_key:
            logger.warning(f"AI API未配置，使用简单分类: {keyword_str}")
            # 简单的默认分类逻辑作为兜底
            keyword_lower = keyword_str.lower()
            if not keyword_lower:
                return '未分类'
            
            # 通用分类规则
            if '教程' in keyword_lower or 'how to' in keyword_lower or 'guide' in keyword_lower:
                return '教程指南'
            elif '工具' in keyword_lower or 'tool' in keyword_lower:
                return '工具软件'
            elif '模板' in keyword_lower or 'template' in keyword_lower:
                return '模板资源'
            elif '免费' in keyword_lower or 'free' in keyword_lower:
                return '免费资源'
            elif '价格' in keyword_lower or 'price' in keyword_lower or 'cost' in keyword_lower:
                return '价格相关'
            elif '比较' in keyword_lower or 'vs' in keyword_lower or 'compare' in keyword_lower:
                return '比较评测'
            else:
                return '一般查询'
        
        try:
            # 获取当前使用的模型类型
            ai_config = self.config_manager.get_ai_api_config()
            model_type = ai_config.get('model_type', 'deepseek')
            
            # 构建提示，从专业角度提取英文主题词
            prompt = f"""Analyze the following keyword professionally and extract its core topic term in English.
Keyword: {keyword_str}

As a professional SEO analyst, identify the most essential, single-word or concise multi-word topic that represents the primary subject of this keyword. The topic should be brief, specific, and in English.

Example guidelines:
- For keywords like "xhamster video download", "download xhamster videos", "download videos from xhamster": the topic is "xhamster"
- For keywords about PowerPoint: the topic might be "powerpoint"
- For keywords about specific software tools: extract the tool name
- For industry-specific terms: use the standard industry term

Please output ONLY the topic term in English, with no additional explanations or formatting."""
            
            # 根据模型类型构建不同的请求
            if model_type == 'tongyi':
                # 通义千问模型配置（使用标准API格式）
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.ai_api_key}'
                }
                
                # 使用通义千问标准API请求格式
                payload = {
                    'model': 'qwen-plus',  # 使用通义千问模型
                    'input': {
                        'messages': [
                            {'role': 'user', 'content': prompt}
                        ]
                    },
                    'parameters': {
                        'max_tokens': 50,
                        'temperature': 0.3
                    }
                }
                
                response = requests.post(self.ai_api_endpoint, headers=headers, data=json.dumps(payload))
                response.raise_for_status()
                
                # 解析通义千问标准API响应
                result = response.json()
                output = result.get('output', {})
                content = output.get('text', '').strip()
                # 检查是否有choices字段作为备用
                if not content:
                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            else:
                # DeepSeek模型配置（默认）
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.ai_api_key}'
                }
                
                payload = {
                    'model': 'deepseek-chat',  # DeepSeek聊天模型
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 50,
                    'temperature': 0.3
                }
                
                response = requests.post(self.ai_api_endpoint, headers=headers, data=json.dumps(payload))
                response.raise_for_status()
                
                # 解析DeepSeek响应
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            # 直接使用响应内容作为主题词（移除可能的额外格式）
            category = content.strip()
            # 移除可能的引号
            category = re.sub(r'^["\']|["\']$', '', category)
                
            if not category:
                raise ValueError("AI未返回有效分类")
            
            logger.debug(f"关键词 '{keyword_str}' 分类结果: {category}")
            return category
            
        except Exception as e:
            logger.error(f"AI分类出错 ({keyword_str}): {str(e)}")
            # 出错时使用默认分类
            return self._fallback_categorize(keyword_str)
    
    def _fallback_categorize(self, keyword):
        """
        当AI分类失败时使用的备用分类方法
        
        参数:
        - keyword: 待分类的关键词
        
        返回:
        - 分类结果
        """
        keyword_lower = str(keyword).lower()
        
        # 根据关键词内容进行简单的文本匹配分类
        # 可以根据实际需求扩展
        if not self.keyword_patterns:
            return '未分类'
        
        # 如果有特定的关键词模式，可以尝试进行基础分类
        pattern_categories = {
            # 可以在这里添加一些基于keyword_patterns的简单映射
            # 例如 {'ppt|powerpoint': '演示软件', '手机|phone': '电子产品'}
        }
        
        for pattern, category in pattern_categories.items():
            if re.search(pattern, keyword_lower):
                return category
        
        return '一般查询'
    
    def _filter_keywords(self, df, column_name):
        """
        根据关键词模式筛选关键词
        
        参数:
        - df: 数据DataFrame
        - column_name: 关键词列名
        
        返回:
        - 筛选后的DataFrame
        """
        if column_name not in df.columns:
            logger.warning(f'列 {column_name} 不存在于数据中')
            return pd.DataFrame()
        
        # 检查keyword_patterns是否有效
        if not self.keyword_patterns or not isinstance(self.keyword_patterns, (str, re.Pattern)):
            logger.error(f'关键词筛选模式无效: {self.keyword_patterns}')
            # 如果模式无效，尝试使用简单的关键词匹配
            if self.keyword_patterns is None:
                logger.warning('关键词筛选模式为None，将返回空结果')
                return pd.DataFrame()
            # 尝试转换为字符串
            try:
                pattern_str = str(self.keyword_patterns)
                logger.warning(f'尝试使用转换后的模式: {pattern_str}')
            except:
                logger.error('无法转换关键词模式为字符串')
                return pd.DataFrame()
        else:
            pattern_str = self.keyword_patterns
        
        df_lower = df.copy()
        df_lower[column_name] = df_lower[column_name].astype(str).str.lower()
        
        try:
            filtered = df[df_lower[column_name].str.contains(pattern_str, case=False, na=False)].copy()
            return filtered

        except Exception as e:
            logger.error(f'筛选关键词时出错: {str(e)}')
            return pd.DataFrame()
    
    
    def load_files(self):
        """
        加载数据文件夹中的所有Excel文件
        """
        if not os.path.exists(self.data_folder):
            logger.error(f'数据文件夹不存在: {self.data_folder}')
            return
        
        files = [f for f in os.listdir(self.data_folder) if f.endswith('.xlsx') and not f.startswith('~$')]
        
        logger.info(f'找到 {len(files)} 个Excel文件')
        for file in files:
            logger.info(f'- {file}')
        
        for file in files:
            file_path = os.path.join(self.data_folder, file)
            try:
                df = pd.read_excel(file_path)
                logger.info(f'处理文件: {file}')
                logger.info(f'文件形状: {df.shape}')
                logger.info(f'列名: {list(df.columns)}')
                
                self.all_keywords[file] = df
                
            except Exception as e:
                logger.error(f'读取文件 {file} 时出错: {str(e)}')
    
    def read_keyword_patterns_from_markdown(self):
        """
        从data文件夹中的markdown文件读取关键词筛选条件
        优先级: 1. keywords.md 2. 任何.md文件 3. 保持原有设置
        不会终止程序，而是记录错误并返回状态
        """
        try:
            # 检查data_folder是否为字符串
            if not isinstance(self.data_folder, str):
                logger.error(f'数据文件夹路径类型错误: {type(self.data_folder)}')
                return False
                
            md_files = [f for f in os.listdir(self.data_folder) if f.endswith('.md')]
            
            if not md_files:
                logger.warning('未找到markdown文件，将使用默认或已设置的关键词规则')
                return False
            
            # 优先使用keywords.md
            target_file = None
            if 'keywords.md' in md_files:
                target_file = 'keywords.md'
            else:
                target_file = md_files[0]
            
            file_path = os.path.join(self.data_folder, target_file)
            logger.info(f'从markdown文件读取关键词筛选条件: {target_file}')
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取关键词（简单处理，提取所有非空行）
            keywords = []
            for line in content.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('---'):
                    keywords.append(line)
            
            if keywords:
                # 将关键词列表转换为正则表达式模式
                self.keyword_patterns = '|'.join([re.escape(keyword) for keyword in keywords])
                logger.info(f'已更新关键词筛选条件，共 {len(keywords)} 个关键词')
                logger.info(f'关键词模式: {self.keyword_patterns}')
                return True
            else:
                logger.warning('markdown文件中未找到有效的关键词，将使用默认或已设置的关键词规则')
                return False
                
        except Exception as e:
            logger.error(f'读取markdown文件时出错: {str(e)}')
            logger.warning('将使用默认或已设置的关键词规则')
            return False
    
    def filter_keywords_from_files(self):
        """
        从加载的文件中筛选关键词
        """
        if not self.all_keywords:
            logger.error('没有加载文件，请先调用load_files()方法')
            return
        
        self.filtered_keywords = pd.DataFrame()
        
        for file_name, df in self.all_keywords.items():
            for col in self.keyword_columns:
                if col in df.columns:
                    logger.info(f'在文件 {file_name} 中找到关键词列: {col}')
                    filtered = self._filter_keywords(df, col)
                    logger.info(f'筛选后关键词数量: {len(filtered)}')
                    
                    # 添加文件名作为来源
                    filtered['source'] = file_name
                    
                    # 查找搜索量列
                    file_volume_col = None
                    for v_col in df.columns:
                        v_col_lower = v_col.lower()
                        if v_col_lower in [vol_col.lower() for vol_col in self.volume_columns]:
                            file_volume_col = v_col
                            logger.info(f'在文件 {file_name} 中找到搜索量列: {file_volume_col}')
                            
                            # 确保file_volume_col在filtered的columns中
                            if file_volume_col in filtered.columns:
                                # 重命名为统一的volume列名以避免合并冲突
                                filtered['volume'] = filtered[file_volume_col].fillna(0)
                                # 尝试转换为数字
                                try:
                                    filtered['volume'] = filtered['volume'].astype(float)
                                except (ValueError, TypeError):
                                    filtered['volume'] = 0
                            else:
                                logger.warning(f'搜索量列 {file_volume_col} 不在筛选后的结果中，使用默认值0')
                                filtered['volume'] = 0
                            break
                    
                    if file_volume_col is None:
                        logger.warning(f'在文件 {file_name} 中未找到搜索量列，将使用默认值0')
                        filtered['volume'] = 0
                    
                    self.filtered_keywords = pd.concat([self.filtered_keywords, filtered])
                    break
        
        logger.info(f'所有文件合并后筛选的关键词总数: {len(self.filtered_keywords)}')
    
    def analyze_and_export(self):
        """
        分析关键词并导出结果
        
        返回:
            结果字典
        """
        if self.filtered_keywords.empty:
            logger.warning("没有筛选出关键词，无法分析")
            return None
        
        logger.info(f"开始分析关键词 - 总数量: {len(self.filtered_keywords)}")
        
        # 识别关键词列
        keyword_cols = [col for col in self.filtered_keywords.columns 
                       if col.lower() in [k_col.lower() for k_col in self.keyword_columns]]
        
        if not keyword_cols:
            logger.warning('未找到关键词列')
            return None
        
        keyword_col = keyword_cols[0]
        logger.info(f'使用关键词列: {keyword_col}')
        
        # 去重
        filtered_keywords_unique = self.filtered_keywords.drop_duplicates(subset=[keyword_col]).copy()
        logger.info(f'去重后关键词数量: {len(filtered_keywords_unique)}')
        
        # 已经在处理每个文件时确保了统一的volume列
        volume_col = 'volume'
        logger.info(f'使用搜索量列: {volume_col}')
        
        # 批量处理关键词，减少API调用次数
        logger.info("开始批量处理关键词分类")
        categories = []
        total_to_process = len(filtered_keywords_unique)
        processed_count = 0
        
        # 检查是否可以批量调用AI API
        if self.ai_api_endpoint and self.ai_api_key and self.categorize_func == self.ai_categorize:
            # 这里可以实现批量AI分类逻辑，减少API调用次数
            # 为了简化，这里仍使用循环处理
            for idx, keyword in enumerate(filtered_keywords_unique[keyword_col]):
                if (idx + 1) % 10 == 0:
                    logger.info(f"已处理 {idx + 1}/{len(filtered_keywords_unique)} 个关键词")
                categories.append(self.categorize_func(keyword))
                processed_count = idx + 1
                if self.progress_callback:
                    try:
                        self.progress_callback(processed_count, total_to_process)
                    except Exception:
                        pass
        else:
            # 使用普通循环处理
            for idx, keyword in enumerate(filtered_keywords_unique[keyword_col]):
                if (idx + 1) % 50 == 0:
                    logger.info(f"已处理 {idx + 1}/{len(filtered_keywords_unique)} 个关键词")
                categories.append(self.categorize_func(keyword))
                processed_count = idx + 1
                if self.progress_callback:
                    try:
                        self.progress_callback(processed_count, total_to_process)
                    except Exception:
                        pass
        
        filtered_keywords_unique['主题词'] = categories
        logger.info("关键词分类完成")
        
        # 按主题分组并排序
        theme_results = {}
        for theme, group in filtered_keywords_unique.groupby('主题词'):
            # 按搜索量降序排序
            sorted_group = group.sort_values(volume_col, ascending=False)
            # 存储结果
            theme_results[theme] = sorted_group.apply(lambda row: {
                '关键词': row[keyword_col],
                '搜索量': row[volume_col]
            }, axis=1).tolist()
        
        # 计算每个主题的关键词数量
        theme_counts = filtered_keywords_unique['主题词'].value_counts().to_dict()
        
        # 按主题词数量排序
        sorted_themes = sorted(theme_results.items(), key=lambda x: len(x[1]), reverse=True)
        
        # 准备导出数据
        # 转换为ExcelWriter需要的格式
        summary_data = []
        for theme, keywords in sorted_themes:
            for item in keywords:
                summary_data.append({
                    '主题词': theme,
                    '关键词': item['关键词'],
                    '搜索量': item['搜索量']
                })
        
        summary_df = pd.DataFrame(summary_data)
        
        # 额外的工作表数据
        additional_sheets = {
            '主题统计': pd.DataFrame(list(theme_counts.items()), columns=['主题词', '关键词数量']).sort_values('关键词数量', ascending=False),
            '原始数据': filtered_keywords_unique[[keyword_col, volume_col, '主题词', 'source']]
        }
        
        # 使用ExcelWriter导出到配置的results文件夹
        output_file = self.excel_writer.export_to_excel(summary_df, additional_sheets, export_folder=self.results_folder)
        
        if output_file:
            logger.info(f"分析完成，结果已导出到: {output_file}")
            return {
                'output_file': output_file,
                'total_keywords': len(filtered_keywords_unique),
                'theme_counts': theme_counts
            }
        else:
            logger.error("导出Excel文件失败")
            return None
    
    def run_full_analysis(self):
        """
        运行完整的分析流程
        
        返回:
            dict: 包含分析结果和可能的警告信息
        """
        logger.info('开始关键词分析流程...')
        warnings = []
        
        # 尝试从markdown文件读取关键词筛选条件
        if not self.read_keyword_patterns_from_markdown():
            warnings.append('未找到有效关键词规则文件，使用默认关键词规则')
        
        # 加载文件
        self.load_files()
        
        # 筛选关键词
        self.filter_keywords_from_files()
        
        # 分析并导出
        results = self.analyze_and_export()
        
        if results:
            logger.info('关键词分析完成！')
            logger.info(f'总关键词数量: {results["total_keywords"]}')
            logger.info(f'主题数量: {len(results["theme_counts"])}')
            logger.info(f'结果文件: {results["output_file"]}')
            # 添加警告信息到结果中
            results['warnings'] = warnings
            # 添加matched_keywords字段，与total_keywords相同（因为所有筛选后的关键词都被视为匹配）
            results['matched_keywords'] = results['total_keywords']
        else:
            warning_msg = '未生成分析结果'
            logger.warning(warning_msg)
            warnings.append(warning_msg)
            # 即使没有结果，也返回包含警告信息的字典
            results = {
                'output_file': None,
                'warnings': warnings
            }
        
        return results

# 直接运行时的示例
if __name__ == "__main__":
    print("请使用 python main.py 运行整个系统")
    print("或者导入本模块中的 KeywordAnalyzer 类进行自定义分析")
    
    # 简单的演示运行
    try:
        analyzer = KeywordAnalyzer()
        analyzer.run_full_analysis()
    except Exception as e:
        print(f"运行演示出错: {str(e)}")
        print("建议使用 python main.py 运行")