#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
关键词分析系统主入口
用于启动整个关键词分析流程
"""

import os
import sys
from utils.logger import logger, setup_logger
from core.keyword_analyzer import KeywordAnalyzer
from core.config import config_manager


def main():
    """
    主函数
    """
    # 设置日志记录
    logger = setup_logger("keyword_analysis_main")
    logger.info("启动关键词分析系统...")
    
    try:
        # 初始化配置管理器（自动加载环境变量和.env文件）
        logger.info("加载配置信息")
        
        # 创建关键词分析器实例（将自动使用配置管理器中的默认配置）
        analyzer = KeywordAnalyzer(
            # 注意：keyword_patterns会在read_keyword_patterns_from_markdown方法中被覆盖
            # 如果data文件夹中有markdown文件的话
            output_filename_prefix='关键词分析结果'
        )
        
        # 运行完整分析
        results = analyzer.run_full_analysis()
        
        if results:
            logger.info(f"分析成功完成！")
            logger.info(f"结果已保存到: {results['output_file']}")
            print(f"\n分析完成！")
            print(f"- 总关键词数量: {results['total_keywords']}")
            print(f"- 主题数量: {len(results['theme_counts'])}")
            print(f"- 结果文件: {results['output_file']}")
            print(f"- 日志文件: {logger.handlers[0].baseFilename}")
        else:
            logger.warning("分析未生成结果")
            print("\n分析未生成结果，请检查日志获取详细信息")
            
    except KeyboardInterrupt:
        logger.info("用户中断操作")
        print("\n操作已中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}", exc_info=True)
        print(f"\n程序运行出错: {str(e)}")
        print("请查看日志文件获取详细错误信息")
        sys.exit(1)


def custom_analysis_example():
    """
    自定义分析示例
    演示如何使用自定义的分类函数和配置
    """
    # 自定义分类函数示例
    def custom_categorization(keyword):
        """
        自定义分类函数示例
        """
        keyword_lower = str(keyword).lower()
        
        # 产品类别
        if '手机' in keyword_lower or 'phone' in keyword_lower:
            return '手机产品'
        elif '电脑' in keyword_lower or 'computer' in keyword_lower or 'laptop' in keyword_lower:
            return '电脑产品'
        elif '平板' in keyword_lower or 'tablet' in keyword_lower:
            return '平板产品'
        
        # 品牌类别
        if '苹果' in keyword_lower or 'apple' in keyword_lower:
            return '苹果品牌'
        elif '华为' in keyword_lower or 'huawei' in keyword_lower:
            return '华为品牌'
        elif '小米' in keyword_lower or 'xiaomi' in keyword_lower:
            return '小米品牌'
        
        # 功能类别
        if '游戏' in keyword_lower or 'game' in keyword_lower:
            return '游戏功能'
        elif '摄影' in keyword_lower or 'camera' in keyword_lower:
            return '摄影功能'
        
        # 兜底类别
        return '其他电子产品相关'
    
    # 从配置管理器获取基础配置
    path_config = config_manager.get_path_config()
    keyword_config = config_manager.get_keyword_config()
    
    # 创建自定义分析器
    custom_analyzer = KeywordAnalyzer(
        data_folder=os.path.join(path_config['project_root'], 'data'),
        keyword_patterns='手机|电脑|平板|apple|iphone|huawei|xiaomi',  # 自定义关键词筛选模式
        categorize_func=custom_categorization,  # 使用自定义分类函数
        keyword_columns=keyword_config['keyword_columns'],  # 使用配置中的关键词列名
        volume_columns=keyword_config['volume_columns'],  # 使用配置中的搜索量列名
        output_filename_prefix='自定义电子产品关键词分析'  # 自定义输出文件名前缀
    )
    
    return custom_analyzer.run_full_analysis()


if __name__ == "__main__":
    # 运行标准分析
    main()
    
    # 如果需要运行自定义分析，可以取消下面的注释
    # print("\n" + "="*50)
    # print("运行自定义分析示例...")
    # custom_analysis_example()