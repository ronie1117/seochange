# SEO关键词分析工具

一个高效的关键词分析工具，可以从Excel文件中提取关键词，使用AI模型进行智能分类，并生成详细的分析报告.

## 功能特点

- 自动从Excel文件中提取关键词和搜索量数据
- 支持通过Markdown文件定义关键词筛选规则
- 使用AI模型对关键词进行智能分类
- 生成Excel格式的分析报告，包含主题分类和统计数据
- 灵活的配置系统，支持通过环境变量或配置文件设置参数

## 目录结构

```
seo-select/
├── core/                    # 核心功能模块
│   ├── __init__.py
│   ├── keyword_analyzer.py  # 关键词分析器
│   └── config.py            # 配置管理器
├── utils/                   # 工具函数
│   ├── __init__.py
│   ├── logger.py            # 日志工具
│   └── excel_writer.py      # Excel导出工具
├── data/                    # 数据文件夹（存放Excel和Markdown文件）
├── results/                 # 结果文件夹（存放生成的报告）
├── main.py                  # 主程序入口
├── .env.example             # 环境变量示例文件
└── requirements.txt         # 项目依赖
```

## 安装说明

### 1. 克隆项目

```bash
git clone <项目地址>
cd seo-select
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量示例文件并根据需要修改：

```bash
cp .env.example .env
```

## 配置说明

### 1. 环境变量配置（.env文件）

编辑`.env`文件，设置以下配置项：

```
# 路径配置
DATA_FOLDER=./data          # 数据文件夹路径
RESULTS_FOLDER=./results    # 结果文件夹路径

# AI API配置
AI_API_ENDPOINT=https://api.openai.com/v1/chat/completions  # AI模型API端点
AI_API_KEY=your_api_key_here                               # AI模型API密钥
AI_API_MODEL=gpt-3.5-turbo                                 # AI模型名称
AI_API_MAX_TOKENS=50                                       # 最大token数
AI_API_TEMPERATURE=0.3                                     # 温度参数

# 导出配置
OUTPUT_FILENAME_PREFIX=keyword_analysis                    # 输出文件名前缀
```

### 2. 关键词筛选规则配置

在数据文件夹中创建`keywords.md`文件，每行包含一个关键词或正则表达式：

```markdown
# 关键词筛选规则

PPT
PowerPoint
演示文稿
template
theme
```

## 使用方法

### 1. 准备数据

将包含关键词的Excel文件放入数据文件夹（默认为`./data`）。

Excel文件需包含至少一列关键词，可选包含搜索量列。

### 2. 运行程序

```bash
python main.py
```

### 3. 查看结果

分析完成后，结果报告将保存在结果文件夹（默认为`./results`）中，文件名为`keyword_analysis_日期时间.xlsx`。

## AI模型调用说明

### 提示词设计

系统使用精心设计的提示词引导AI模型进行关键词分类：

1. 提供预定义的主题类别列表
2. 包含分类示例，确保模型理解预期输出格式
3. 指定清晰的输出格式要求

### 支持的主题类别

- 教程指南
- 工具软件
- 模板资源
- 免费资源
- 价格相关
- 比较评测
- 问题解决
- 最新趋势
- 基础概念
- 高级技巧
- 最佳实践
- 行业应用
- 产品推荐
- 案例分析
- 学习资源
- 其他

### 备用分类机制

当AI API调用失败或未配置时，系统会使用基于规则的备用分类方法，确保即使在无法使用AI的情况下也能获得基本的分类结果。

## 自定义使用

除了使用主程序外，还可以直接在Python代码中使用`KeywordAnalyzer`类进行自定义分析：

```python
from core.keyword_analyzer import KeywordAnalyzer

# 创建分析器实例（可传入自定义参数）
analyzer = KeywordAnalyzer(
    data_folder='./custom_data',
    output_filename_prefix='custom_analysis'
)

# 运行分析
results = analyzer.run_full_analysis()

# 获取分析结果
print(f"分析完成，输出文件: {results['output_file']}")
print(f"总关键词数量: {results['total_keywords']}")
print(f"主题统计: {results['theme_counts']}")
```

## 故障排除

### 常见问题

1. **API调用失败**：检查AI API密钥是否正确，网络连接是否正常
2. **找不到Excel文件**：确保Excel文件放在正确的数据文件夹中，且文件名以`.xlsx`结尾
3. **关键词筛选无结果**：检查Markdown文件中的关键词规则是否正确

### 日志信息

程序运行过程中会输出详细的日志信息，帮助诊断问题。日志内容包括：
- 加载的文件列表
- 筛选的关键词数量
- API调用状态
- 导出文件路径

## 许可证

[MIT License](LICENSE)