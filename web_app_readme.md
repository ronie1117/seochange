# SEO关键词分析工具 - Web应用版

本文档介绍如何将SEO关键词分析工具集成到网页端，以便第三方用户使用。

## 功能概述

- 支持用户上传Excel文件
- 允许用户自定义关键词筛选规则
- 提供在线分析功能
- 自动生成并下载分析结果Excel文件
- 美观的用户界面，支持响应式设计

## 技术栈

- **后端**: Flask (Python)
- **前端**: HTML, Tailwind CSS, Font Awesome
- **数据处理**: Pandas

## 快速开始

### 1. 安装依赖

确保已安装所有必需的依赖：

```bash
pip install flask pandas openpyxl
```

### 2. 启动Web服务

在项目根目录运行：

```bash
python web_app.py
```

服务将在 http://localhost:5000 启动。

## 使用说明

1. 访问Web应用首页
2. 上传包含关键词数据的Excel文件
3. 在文本框中输入关键词筛选规则（每行一个）
4. 点击"开始分析"按钮
5. 分析完成后，系统将自动下载结果文件

## 部署建议

### 开发环境

- 使用Flask内置服务器进行开发和测试
- 运行命令：`python web_app.py`

### 生产环境

对于生产环境部署，建议：

1. **使用WSGI服务器**

   ```bash
   # 安装Gunicorn
   pip install gunicorn
   
   # 启动服务
   gunicorn -w 4 -b 0.0.0.0:8000 web_app:app
   ```

2. **配置反向代理**

   使用Nginx作为反向代理，配置示例：

   ```nginx
   server {
       listen 80;
       server_name example.com;
       
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. **启用HTTPS**

   配置SSL证书以启用HTTPS连接，保护用户数据安全。

## 安全建议

1. **文件上传安全**
   - 限制文件类型和大小
   - 对上传的文件进行病毒扫描
   - 使用随机文件名存储上传的文件

2. **数据处理**
   - 清理并验证用户输入
   - 避免在响应中泄露敏感信息
   - 设置合理的超时时间

3. **资源管理**
   - 定期清理临时文件
   - 监控资源使用情况
   - 考虑添加用户认证和配额限制

## 扩展功能

以下是可能的扩展功能：

1. **用户认证系统**
   - 注册/登录功能
   - 用户权限管理

2. **分析历史记录**
   - 保存用户的分析历史
   - 允许重新下载之前的分析结果

3. **高级分析选项**
   - 提供更多自定义分析参数
   - 可视化分析结果

4. **API接口**
   - 提供RESTful API供其他应用调用

## 故障排除

1. **文件上传失败**
   - 检查文件大小是否超过限制
   - 确保文件格式正确（xlsx, xls）

2. **分析过程错误**
   - 检查Excel文件格式是否符合要求
   - 验证关键词筛选规则格式

3. **服务器错误**
   - 查看日志文件获取详细错误信息
   - 确保所有依赖已正确安装

## 许可证

保留所有权利。