from flask import Flask, request, render_template_string, jsonify, send_from_directory, Response
import os
import re
import shutil
import logging
import traceback
import json
from core.keyword_analyzer import KeywordAnalyzer
from core.config import ConfigManager
from core.file_uploader import FileUploader, FileTypeError, FileSizeError, FileSaveError
from core.keyword_manager import keyword_manager
from core.file_result_handler import init_file_result_handler, file_result_handler

# 设置基本日志级别
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__)

# 应用配置 - 从环境变量读取配置或使用默认值
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小为16MB

# 初始化文件上传器
file_uploader = FileUploader(
    allowed_extensions={'xlsx', 'xls'},
    max_file_size=16 * 1024 * 1024,  # 16MB
    logger=logger
)

# 配置管理器
config_manager = ConfigManager()

# 初始化文件结果处理器
file_result_handler = init_file_result_handler(file_uploader)

# 简单的进度存储（内存级，按请求提供的progress_key区分）
progress_store = {}

# 主页面
@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SEO关键词分析工具</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet">
        <script>
            tailwind.config = {
                theme: {
                    extend: {
                        colors: {
                            primary: '#3b82f6',
                            secondary: '#10b981',
                            accent: '#6366f1',
                            neutral: '#1f2937',
                        },
                        fontFamily: {
                            sans: ['Inter', 'system-ui', 'sans-serif'],
                        },
                    }
                }
            }
        </script>
        <style type="text/tailwindcss">
            @layer utilities {
                .content-auto { content-visibility: auto; }
                .shadow-soft { box-shadow: 0 2px 15px rgba(0, 0, 0, 0.05); }
                .hover-up { transition: transform 0.2s; }
                .hover-up:hover { transform: translateY(-2px); }
            }
            @layer components {
                .g-input { @apply w-full rounded-full border border-gray-300 bg-white text-gray-900 placeholder-gray-400 shadow-sm transition focus:border-gray-400 focus:ring-0 focus:shadow-md; }
                .g-textarea { @apply w-full rounded-2xl border border-gray-300 bg-white text-gray-900 placeholder-gray-400 shadow-sm transition focus:border-gray-400 focus:ring-0 focus:shadow-md; }
                /* 音乐播放器风格进度条 */
                .player-wrap { @apply w-full mt-3 select-none; }
                .player-track { @apply relative w-full h-2 bg-gray-200 rounded-full overflow-hidden; }
                .player-fill { @apply absolute left-0 top-0 h-full rounded-full bg-gradient-to-r from-green-400 via-emerald-500 to-blue-500; }
                .player-thumb { @apply absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border border-gray-300 shadow; }
                .player-meta { @apply mt-1 text-xs text-gray-500 flex justify-between; }
            }
        </style>
    </head>
    <body class="bg-gray-50 min-h-screen">
        <header class="bg-white shadow-md">
            <div class="container mx-auto px-4 py-4 flex justify-between items-center">
                <div class="flex items-center space-x-2">
                    <i class="fa fa-search text-primary text-2xl"></i>
                    <h1 class="text-xl font-bold text-neutral">SEO关键词分析工具</h1>
                </div>
                <div class="hidden md:flex space-x-6">
                    <a href="#" class="text-gray-600 hover:text-primary transition-colors">首页</a>
                    <a href="#how-it-works" class="text-gray-600 hover:text-primary transition-colors">使用说明</a>
                    <a href="#about" class="text-gray-600 hover:text-primary transition-colors">关于</a>
                </div>
                <button class="md:hidden text-gray-600 focus:outline-none">
                    <i class="fa fa-bars text-xl"></i>
                </button>
            </div>
        </header>

        <main class="container mx-auto px-4 py-8">
            <section class="max-w-3xl mx-auto bg-white rounded-xl shadow-soft p-6 md:p-8">
                <h2 class="text-2xl font-bold text-neutral mb-6 text-center">关键词分析器</h2>
                
                <form id="analysis-form" enctype="multipart/form-data" method="post" action="#" class="space-y-6" novalidate>
                    <!-- 文件上传 -->
                    <div class="space-y-2">
                        <label for="file" class="block text-sm font-medium text-gray-700">
                            <i class="fa fa-file-excel-o text-secondary mr-2"></i>上传Excel文件（可多选）
                        </label>
                        <div class="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-lg hover:border-primary transition-colors">
                            <div class="space-y-1 text-center">
                                <i class="fa fa-cloud-upload text-4xl text-gray-400 mb-3"></i>
                                <div class="flex text-sm text-gray-600">
                                    <label for="file" class="relative cursor-pointer bg-white rounded-md font-medium text-primary hover:text-primary/90">
                                        <span>选择文件</span>
                                        <input id="file" name="file" type="file" accept=".xlsx,.xls" multiple class="sr-only">
                                    </label>
                                    <p class="pl-1"></p>
                                </div>
                                <div id="file-list" class="mt-3 text-sm bg-white border border-gray-200 rounded-md p-2 hidden"></div>
                                <p class="text-xs text-gray-500">
                                    XLSX, XLS (最大 16MB)
                                </p>
                            </div>
                        </div>
                    </div>

                    <!-- 关键词筛选规则 -->
                    <div class="space-y-2">
                        <label for="keywords" class="block text-sm font-medium text-gray-700">
                            <i class="fa fa-tags text-accent mr-2"></i>输入需要筛选的关键词（每行一个）
                        </label>
                        <div class="mt-1">
                            <div class="g-textarea px-4 py-3">
                                <textarea id="keywords" name="keywords" rows="4" placeholder="输入需要筛选的关键词，每行一个\n例如：\nslide\nppt\npowerpoint\npresentation" class="w-full outline-none bg-transparent caret-gray-700 text-sm"></textarea>
                            </div>
                        </div>
                    </div>
                    

                    <!-- AI API配置 -->
                    <div class="space-y-4 mt-6">
                        <h3 class="text-lg font-medium text-gray-800">AI API 配置</h3>
                        
                        <div class="space-y-2">
                            <label for="ai_api_key" class="block text-sm font-medium text-gray-700">
                                <i class="fa fa-key text-accent mr-2"></i>API 密钥
                            </label>
                            <div class="mt-1">
                                <div class="flex items-center g-input px-4 py-2">
                                    <i class="fa fa-key text-gray-400 mr-2"></i>
                                    <input type="password" id="ai_api_key" name="ai_api_key" placeholder="输入您的AI API密钥" class="flex-1 outline-none bg-transparent caret-gray-700 text-sm" />
                                </div>
                            </div>
                        </div>
                        
                        <div class="space-y-2">
                            <label for="ai_api_url" class="block text-sm font-medium text-gray-700">
                                <i class="fa fa-link text-accent mr-2"></i>API 端点 URL
                            </label>
                            <div class="mt-1">
                                <div class="flex items-center g-input px-4 py-2">
                                    <i class="fa fa-link text-gray-400 mr-2"></i>
                                    <input type="text" id="ai_api_url" name="ai_api_url" placeholder="例如: https://api.example.com/v1/chat/completions" class="flex-1 outline-none bg-transparent caret-gray-700 text-sm" />
                                </div>
                            </div>
                            <div class="mt-2 text-xs text-gray-600 space-y-1">
                                <div>
                                    <span class="font-medium">获取 API Key：</span>
                                    <a href="https://platform.deepseek.com/api-keys" target="_blank" rel="noopener" class="text-primary underline">DeepSeek</a>
                                    ｜
                                    <a href="https://dashscope.console.aliyun.com/apiKey" target="_blank" rel="noopener" class="text-primary underline">通义千问（DashScope）</a>
                                </div>
                                <div>
                                    <span class="font-medium">端点示例：</span>
                                    <span class="mr-2">DeepSeek：<code class="bg-gray-100 px-1 rounded">https://api.deepseek.com/v1/chat/completions</code></span>
                                    <span>通义千问：<code class="bg-gray-100 px-1 rounded">https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation</code></span>
                                </div>
                            </div>
                        </div>
                        
                        <div class="space-y-2">
                            <label class="block text-sm font-medium text-gray-700">
                                <i class="fa fa-brain text-accent mr-2"></i>AI模型类型（默认deepseek）
                            </label>
                            <div class="flex space-x-6">
                                <div class="flex items-center">
                                    <input type="radio" id="model_deepseek" name="ai_model" value="deepseek" 
                                           class="h-4 w-4 text-primary focus:ring-primary border-gray-300">
                                    <label for="model_deepseek" class="ml-2 block text-sm text-gray-700">DeepSeek</label>
                                </div>
                                <div class="flex items-center">
                                    <input type="radio" id="model_tongyi" name="ai_model" value="tongyi"
                                           class="h-4 w-4 text-primary focus:ring-primary border-gray-300">
                                    <label for="model_tongyi" class="ml-2 block text-sm text-gray-700">通义千问</label>
                                </div>
                            </div>
                            <div id="model-status" class="text-xs text-gray-500 hidden">保存中...</div>
                        </div>
                    </div>

                    <!-- 提交按钮 -->
                    <div class="mt-6">
                        <button type="button" id="submit-btn" class="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-all duration-200 hover-up">
                            <i class="fa fa-cog fa-spin mr-2 hidden" id="loading-icon"></i>
                            <span id="btn-text">开始分析</span>
                        </button>
                        <div id="progress-wrap" class="player-wrap hidden">
                            <div class="player-track">
                                <div id="progress-bar" class="player-fill" style="width:0%"></div>
                                <div id="progress-thumb" class="player-thumb" style="left:0%"></div>
                            </div>
                            <div class="player-meta">
                                <span id="progress-text">0%</span>
                                <span id="progress-tip">分析中...</span>
                            </div>
                        </div>
                    </div>
                </form>
            </section>

            <!-- 使用说明 -->
            <section id="how-it-works" class="max-w-3xl mx-auto mt-16">
                <h2 class="text-2xl font-bold text-neutral mb-6 text-center">使用说明</h2>
                <div class="bg-white rounded-xl shadow-soft p-6 md:p-8">
                    <ol class="list-decimal list-inside space-y-4">
                        <li class="text-gray-700">上传包含关键词数据的Excel文件</li>
                        <li class="text-gray-700">设置关键词筛选规则，只有包含这些关键词的条目才会被分析</li>
                        <li class="text-gray-700">点击"开始分析"按钮</li>
                        <li class="text-gray-700">等待分析完成后，系统将自动下载分析结果Excel文件</li>
                    </ol>
                </div>
            </section>

            <!-- 关于 -->
            <section id="about" class="max-w-3xl mx-auto mt-16 mb-16">
                <h2 class="text-2xl font-bold text-neutral mb-6 text-center">关于工具</h2>
                <div class="bg-white rounded-xl shadow-soft p-6 md:p-8">
                    <p class="text-gray-700 mb-4">
                        本工具提供SEO关键词分析功能，可以帮助您筛选、分析和分类关键词数据，为您的SEO策略提供数据支持。
                    </p>
                    <p class="text-gray-700">
                        工具会根据您提供的筛选规则处理Excel文件中的关键词，并将结果分类整理后导出为新的Excel文件。
                    </p>
                </div>
            </section>
        </main>

        <footer class="bg-neutral text-white py-8">
            <div class="container mx-auto px-4 text-center">
                <p>© 2025 SEO关键词分析工具 | 版权所有</p>
            </div>
        </footer>

        <script>
        // 轮询进度
        var __progressTimer = null;
        function setProgress(pct){
            var bar = document.getElementById('progress-bar');
            var thumb = document.getElementById('progress-thumb');
            var text = document.getElementById('progress-text');
            var wrap = document.getElementById('progress-wrap');
            if (!bar || !thumb || !text || !wrap) return;
            var p = typeof pct === 'number' ? pct : 0;
            if (p < 0) p = 0; if (p > 100) p = 100;
            bar.style.width = p + '%';
            thumb.style.left = p + '%';
            text.textContent = p + '%';
        }
        function stopProgressPolling(setTo100){
            var wrap = document.getElementById('progress-wrap');
            if (__progressTimer){ clearInterval(__progressTimer); __progressTimer = null; }
            if (setTo100) setProgress(100);
            if (wrap){ setTimeout(function(){ wrap.classList.add('hidden'); }, 800); }
        }
        function startProgressPolling(progressKey){
            var bar = document.getElementById('progress-bar');
            var wrap = document.getElementById('progress-wrap');
            if (!bar || !wrap) return;
            wrap.classList.remove('hidden');
            setProgress(0);
            if (__progressTimer){ clearInterval(__progressTimer); __progressTimer = null; }
            __progressTimer = setInterval(function(){
                fetch('/progress?key=' + encodeURIComponent(progressKey)).then(function(r){return r.json()}).then(function(data){
                    var p = (data && typeof data.percent === 'number') ? data.percent : 0;
                    setProgress(p);
                }).catch(function(){});
            }, 1000);
        }

        // 轻量Toast提示
        function showToast(message, type){
            var wrap = document.createElement('div');
            wrap.className = 'fixed top-4 right-4 z-50';
            var color = 'bg-gray-800';
            if (type === 'success') color = 'bg-emerald-600';
            if (type === 'error') color = 'bg-red-600';
            if (type === 'info') color = 'bg-blue-600';
            wrap.innerHTML = '<div class="text-white text-sm px-4 py-2 rounded shadow-lg ' + color + '" role="status">' +
                             (message || '操作完成') + '</div>';
            document.body.appendChild(wrap);
            setTimeout(function(){
                try { document.body.removeChild(wrap); } catch(e) {}
            }, 3000);
        }
        // 最简单的JavaScript实现
        var selectedFiles = [];
        
        function formatSize(bytes){
            if (!bytes && bytes !== 0) return '';
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes/1024).toFixed(1) + ' KB';
            return (bytes/1024/1024).toFixed(1) + ' MB';
        }
        
        function updateFileList(statusLabel){
            var container = document.getElementById('file-list');
            if (!container) return;
            if (!selectedFiles || selectedFiles.length === 0){
                container.classList.add('hidden');
                container.innerHTML = '';
                return;
            }
            var title = (statusLabel ? statusLabel : '已选择') + ' ' + selectedFiles.length + ' 个文件';
            var rows = selectedFiles.map(function(f, idx){
                return '<li class="flex items-center justify-between py-1">'
                    + '<span class="truncate mr-2" title="' + f.name + '">' + f.name + '</span>'
                    + '<span class="text-gray-500 text-xs mr-2">' + formatSize(f.size) + '</span>'
                    + '<button class="text-red-600 hover:text-red-700 text-xs" onclick="removeFileAt(' + idx + ')">移除</button>'
                    + '</li>';
            }).join('');
            container.innerHTML = '<div class="font-medium mb-1">' + title + '</div>'
                + '<ul class="divide-y divide-gray-200">' + rows + '</ul>'
                + '<div class="mt-2"><button class="text-gray-600 hover:text-gray-800 text-xs" onclick="clearAllFiles()">清空全部</button></div>';
            container.classList.remove('hidden');
        }
        
        function removeFile() {
            clearAllFiles();
        }
        function removeFileAt(index){
            if (index >= 0 && index < selectedFiles.length){
                selectedFiles.splice(index, 1);
                updateFileList();
            }
        }
        function clearAllFiles(){
            selectedFiles = [];
            var input = document.getElementById('file');
            if (input) input.value = '';
            updateFileList();
        }
        
        function setupFile() {
            var fileInput = document.getElementById('file');
            fileInput.onchange = function() {
                var files = Array.from(this.files || []);
                // 累加到全局已选择列表，避免重复（按name+size+lastModified去重）
                files.forEach(function(f){
                    var exists = selectedFiles.some(function(sf){
                        return sf.name === f.name && sf.size === f.size && sf.lastModified === f.lastModified;
                    });
                    if (!exists){ selectedFiles.push(f); }
                });
                // 清空input以便多次选择同一文件也能触发onchange
                this.value = '';
                updateFileList();
            };
        }
        
        function setupForm() {
            var form = document.getElementById('analysis-form');
            // 修复换行后光标不可见：监听Enter触发
            // 保持焦点与插入符可见
            var keywordsInput = document.getElementById('keywords');
            if (keywordsInput){
                keywordsInput.addEventListener('keydown', function(e){
                    if (e.key === 'Enter'){
                        // 让浏览器按默认处理换行，但确保焦点与插入符可见
                        setTimeout(function(){
                            try { keywordsInput.focus({preventScroll:false}); } catch(_){ keywordsInput.focus(); }
                        }, 0);
                    }
                });
            }
            // 将原本的onsubmit流程改为点击按钮触发，避免浏览器默认提交
            document.getElementById('submit-btn').onclick = function(event) {
                
                var fileInput = document.getElementById('file');
                var keywordsInput = document.getElementById('keywords');
                var aiApiKeyInput = document.getElementById('ai_api_key');
                var aiApiUrlInput = document.getElementById('ai_api_url');
                // AI模型类型现在使用单选框，无需单独获取元素
                var submitBtn = document.getElementById('submit-btn');
                var loadingIcon = document.getElementById('loading-icon');
                var btnText = document.getElementById('btn-text');
                
                // 验证文件是否已选择
                if (!selectedFiles || selectedFiles.length === 0) {
                    alert('请选择至少一个Excel文件上传');
                    fileInput.focus();
                    return;
                }
                
                // 验证关键词筛选规则
                if (!keywordsInput.value.trim()) {
                    alert('请输入要筛选的关键词');
                    keywordsInput.focus();
                    return;
                }
                
                // 验证AI API配置
                if (!aiApiKeyInput.value.trim()) {
                    alert('请输入AI API密钥');
                    aiApiKeyInput.focus();
                    return;
                }
                
                if (!aiApiUrlInput.value.trim()) {
                    alert('请输入AI API端点URL');
                    aiApiUrlInput.focus();
                    return;
                }
                
                // AI模型类型使用单选框，默认已选中deepseek，无需验证
                
                loadingIcon.style.display = 'inline-block';
                btnText.textContent = '分析中...';
                submitBtn.disabled = true;
                // 本次分析的进度键（时间戳随机）
                var progressKey = 'k_' + Date.now() + '_' + Math.floor(Math.random()*1000);
                startProgressPolling(progressKey);
                
                // 提交前先将关键词保存到后端，再继续分析
                var saveKeywords = function(){
                    // 用XHR发送，避免可能的Fetch与FormData兼容问题影响后续文件发送
                    return new Promise(function(resolve){
                        try {
                            var fd = new FormData();
                            fd.append('keywords', keywordsInput.value);
                            var xhr = new XMLHttpRequest();
                            xhr.open('POST', '/save-keywords');
                            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                            xhr.onload = function(){ resolve(true); };
                            xhr.onerror = function(){ resolve(false); };
                            xhr.send(fd);
                        } catch(e) { resolve(false); }
                    });
                };

                saveKeywords().then(function(){
                    // 将选中的文件写回原<input>，再用FormData(form)采集，最大化兼容性
                    var fileInputNow = document.getElementById('file');
                    var filesToSend = (selectedFiles && selectedFiles.length > 0) ? selectedFiles.slice() : (fileInputNow && fileInputNow.files ? Array.from(fileInputNow.files) : []);
                    if (!filesToSend || filesToSend.length === 0){
                        alert('请选择至少一个Excel文件上传');
                        loadingIcon.style.display = 'none';
                        btnText.textContent = '开始分析';
                        submitBtn.disabled = false;
                        stopProgressPolling(false);
                        return;
                    }
                    try {
                        if (fileInputNow && window.DataTransfer){
                            var dt = new DataTransfer();
                            filesToSend.forEach(function(f){ dt.items.add(f); });
                            fileInputNow.files = dt.files;
                        }
                    } catch(e) {}
                    try { console.log('准备发送文件数:', filesToSend.length, filesToSend.map(function(x){return x.name;})); } catch(e) {}
                    // 直接用表单生成FormData，确保文件字段名与后端一致
                    var formData = new FormData(form);
                    // 增加进度键
                    formData.append('progress_key', progressKey);
                    // 使用Fetch API替代XMLHttpRequest，避免InvalidStateError
                fetch('/analyze', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    // 获取响应头信息
                    const totalKeywords = response.headers.get('X-Total-Keywords');
                    const matchedKeywords = response.headers.get('X-Matched-Keywords');
                    const contentDisposition = response.headers.get('Content-Disposition') || '';
                    const contentType = response.headers.get('Content-Type') || '';
                    
                    // 调试日志
                    console.log('Fetch status:', response.status);
                    console.log('X-Total-Keywords:', totalKeywords);
                    console.log('X-Matched-Keywords:', matchedKeywords);
                    console.log('Content-Disposition:', contentDisposition);
                    console.log('Content-Type:', contentType);
                    
                    // 隐藏加载图标
                    loadingIcon.style.display = 'none';
                    btnText.textContent = '开始分析';
                    submitBtn.disabled = false;
                    
                    // 判断响应类型（更健壮）：
                    // 1) 标准Excel MIME
                    const isExcelByMime = contentType.includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
                    // 2) 通过Content-Disposition附件+文件名后缀猜测
                    const isAttachment = contentDisposition.toLowerCase().includes('attachment');
                    let cdFilename = '';
                    try {
                        const m = contentDisposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
                        if (m) {
                            cdFilename = decodeURIComponent(m[1] || m[2] || '');
                        }
                    } catch (e) {
                        cdFilename = '';
                    }
                    const isExcelByName = /\.xlsx(\?.*)?$/i.test(cdFilename);
                    const shouldTreatAsExcel = isExcelByMime || (isAttachment && isExcelByName);
                    
                    if (contentType.includes('application/json')) {
                        // 处理JSON响应
                        return response.json().then(data => ({
                            type: 'json',
                            data,
                            headers: { totalKeywords, matchedKeywords, contentDisposition }
                        }));
                    } else if (shouldTreatAsExcel) {
                        // 处理Excel文件响应
                        return response.blob().then(blob => ({
                            type: 'excel',
                            data: blob,
                            headers: { totalKeywords, matchedKeywords, contentDisposition }
                        }));
                    } else {
                        // 默认当作文本处理
                        return response.text().then(text => ({
                            type: 'text',
                            data: text,
                            headers: { totalKeywords, matchedKeywords, contentDisposition }
                        }));
                    }
                })
                .then(result => {
                    if (result.type === 'json') {
                        const response = result.data;
                        // 检查并显示警告信息
                        if (response.warnings && response.warnings.length > 0) {
                            const warningMessage = '警告信息:' + response.warnings.join(', ');
                            alert(warningMessage);
                        }
                        // 然后显示错误信息（如果有）
                        if (response.error) {
                            if (!response.warnings || response.warnings.length === 0) {
                                // 只有在没有显示警告的情况下才显示错误
                                alert('分析失败: ' + response.error);
                            }
                        } else if (!response.warnings || response.warnings.length === 0) {
                            // 如果既没有警告也没有错误，显示完成信息
                            stopProgressPolling(true);
                            alert('分析完成');
                            // 更新文件展示为“已上传”
                            updateFileList('已上传');
                            // 删除progress目录
                            try {
                                fetch('/delete-temp-file', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({delete: 'clear_progress'})
                                });
                            } catch(e) {}
                        }
                    } else if (result.type === 'excel') {
                        const blob = result.data;
                        const headers = result.headers;
                        const matchedKeywords = headers.matchedKeywords;
                        const totalKeywords = headers.totalKeywords;
                        const contentDisposition = headers.contentDisposition;
                                
                                // 重点检查：如果没有设置Content-Disposition头，可能表示没有生成下载文件
                                if (!contentDisposition) {
                                    stopProgressPolling(false);
                                    // 如果没有Content-Disposition但有匹配关键词，这是异常情况
                                    if (matchedKeywords && parseInt(matchedKeywords) > 0) {
                                        alert('警告：找到了匹配的关键词，但无法生成下载文件');
                                    } else {
                                        // 这是正常情况：没有找到匹配的关键词
                                        alert('没有筛选出任何关键词，请重新输入筛选的关键词后重试');
                                    }
                                    return;
                                }
                                
                                // 从Content-Disposition头中提取文件名
                                let filename = 'keyword_analysis_result.xlsx'; // 默认文件名
                                if (contentDisposition) {
                                    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                                    if (filenameMatch && filenameMatch[1]) {
                                        filename = filenameMatch[1];
                                    }
                                }
                                
                                // 创建下载链接并触发下载
                                if (blob && blob.size > 0) {
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement('a');
                                    a.href = url;
                                    a.download = filename;
                                    document.body.appendChild(a);
                                    
                                    // 确保在主线程触发下载
                                    try {
                                        // 使用鼠标事件模拟真实点击，某些浏览器需要
                                        const event = new MouseEvent('click', {
                                            bubbles: true,
                                            cancelable: true,
                                            view: window
                                        });
                                        a.dispatchEvent(event);
                                    } catch (e) {
                                        // 备用方案：直接点击
                                        a.click();
                                    }
                                    
                                    // 延迟清理，确保下载操作完成
                                    setTimeout(() => {
                                        // 移除DOM元素
                                        document.body.removeChild(a);
                                        // 释放URL对象
                                        URL.revokeObjectURL(url);
                                    }, 1000);
                                    
                                    // 结束进度轮询（完成）
                                    stopProgressPolling(true);
                                    // 通知服务器删除临时结果目录
                                    fetch('/delete-temp-file', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/json'
                                        },
                                        body: JSON.stringify({delete: 'results_folder'})
                                    }).then(() => {
                                        // 清理上传中间产物（data_* 目录与 upload_* 文件）
                                        return fetch('/delete-temp-file', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({delete: 'cleanup_upload_artifacts'})
                                        });
                                    }).then(() => {
                                        // 删除progress目录
                                        return fetch('/delete-temp-file', {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({delete: 'clear_progress'})
                                        });
                                    }).then(() => {
                                        // 可选：若需彻底清空uploads，取消注释下一段
                                        // return fetch('/delete-temp-file', {
                                        //     method: 'POST',
                                        //     headers: { 'Content-Type': 'application/json' },
                                        //     body: JSON.stringify({delete: 'clear_uploads'})
                                        // });
                                    });
                                    // 更新文件展示为“已上传”
                                    updateFileList('已上传');
                                } else {
                                    console.error('响应数据不是有效的Blob对象');
                                    stopProgressPolling(false);
                                    alert('生成下载文件失败');
                                }
                            } else {
                                // 处理文本或其他类型的响应
                                stopProgressPolling(true);
                                alert('分析完成');
                                // 更新文件展示为“已上传”
                                updateFileList('已上传');
                                // 删除progress目录
                                try {
                                    fetch('/delete-temp-file', {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({delete: 'clear_progress'})
                                    });
                                } catch(e) {}
                            }
                        })
                        .catch(error => {
                            // 处理请求错误
                            console.error('请求失败:', error);
                            stopProgressPolling(false);
                            loadingIcon.style.display = 'none';
                            btnText.textContent = '开始分析';
                            submitBtn.disabled = false;
                            alert('分析失败：网络错误或服务器异常');
                        });
                });
            };
            
            // 移除“保存关键词”按钮逻辑，改为提交时自动保存
        }

        // 保存AI模型类型到配置文件
        function setupModelConfig() {
            var modelRadios = document.querySelectorAll('input[name="ai_model"]');
            var modelStatus = document.getElementById('model-status');
            
            // 默认选中deepseek模型
            document.getElementById('model_deepseek').checked = true;
            
            // 尝试从配置中获取当前模型类型（可选，不影响功能）
            // 由于Flask模板变量在这里无法直接使用，我们默认选择deepseek作为初始值
            // 用户可以随时通过单选框切换模型类型
            
            // 为每个单选按钮添加事件监听器
            modelRadios.forEach(radio => {
                radio.addEventListener('change', function() {
                    if (this.checked) {
                        var modelType = this.value;
                        
                        // 显示保存状态
                        modelStatus.textContent = '正在保存模型设置...';
                        modelStatus.classList.remove('hidden', 'text-green-600', 'text-red-600');
                        modelStatus.classList.add('text-blue-600');
                        
                        // 发送请求保存模型配置
                        const formData = new FormData();
                        formData.append('ai_model', modelType);
                        
                        const xhr = new XMLHttpRequest();
                        xhr.open('POST', '/save-model-config');
                        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
                        
                        xhr.onload = function() {
                            if (xhr.status === 200) {
                                try {
                                    const response = JSON.parse(xhr.responseText);
                                    modelStatus.textContent = response.message;
                                    modelStatus.classList.remove('text-blue-600', 'text-red-600');
                                    modelStatus.classList.add('text-green-600');
                                } catch (e) {
                                    modelStatus.textContent = '保存成功';
                                    modelStatus.classList.remove('text-blue-600', 'text-red-600');
                                    modelStatus.classList.add('text-green-600');
                                }
                            } else {
                                try {
                                    const response = JSON.parse(xhr.responseText);
                                    modelStatus.textContent = '保存失败: ' + response.error;
                                } catch (e) {
                                    modelStatus.textContent = '保存失败，请重试';
                                }
                                modelStatus.classList.remove('text-blue-600', 'text-green-600');
                                modelStatus.classList.add('text-red-600');
                            }
                            
                            // 3秒后隐藏状态消息
                            setTimeout(() => {
                                modelStatus.classList.add('hidden');
                            }, 3000);
                        };
                        
                        xhr.onerror = function() {
                            modelStatus.textContent = '网络错误，请重试';
                            modelStatus.classList.remove('text-blue-600', 'text-green-600');
                            modelStatus.classList.add('text-red-600');
                        };
                        
                        xhr.send(formData);
                    }
                });
            });
        }

        window.onload = function() {
            setupFile();
            setupForm();
            setupModelConfig();
        };
        </script>
    </body>
    </html>
    ''')

# 分析API
@app.route('/analyze', methods=['POST'])
def analyze():
    """分析Excel文件中的关键词并返回结果"""
    logger.info("收到关键词分析请求")
    
    try:
        # 检查请求方法和内容类型
        logger.debug(f"请求方法: POST, 内容类型: {request.content_type}")
        
        # 直接使用已初始化的file_uploader
        logger.info("开始使用全局file_uploader处理上传")
        logger.debug("检查请求中的文件部分")
        # 检查是否有文件上传（接受任意文件字段名）
        if not request.files or len(request.files) == 0:
            logger.warning("请求中没有文件部分")
            return jsonify({'error': '请上传Excel文件'}), 400
        
        # 汇总所有文件字段
        files = []
        try:
            for field_name, file_list in request.files.lists():
                logger.debug(f"接收文件字段: {field_name}, 数量: {len(file_list)}")
                for f in file_list:
                    files.append(f)
        except Exception as e:
            logger.error(f"遍历上传文件失败: {str(e)}")
        files = [f for f in files if f and getattr(f, 'filename', '')]
        if not files:
            logger.warning("未选择任何文件或文件名为空")
            return jsonify({'error': '请选择要上传的文件'}), 400
        
        logger.info(f"收到文件上传: {len(files)} 个文件")
        
        # 获取关键词规则
        keywords_text = request.form.get('keywords', '')
        logger.debug(f"关键词规则文本长度: {len(keywords_text)}")
        if not keywords_text.strip():
            logger.warning("关键词筛选规则为空")
            return jsonify({'error': '请输入关键词筛选规则'}), 400
        
        # 获取AI API配置
        ai_api_key = request.form.get('ai_api_key', '')
        ai_api_url = request.form.get('ai_api_url', '')
        ai_model = request.form.get('ai_model', '')
        # 获取进度键
        progress_key = request.form.get('progress_key', '')
        
        # 记录API配置日志（注意：不要记录完整的API密钥）
        logger.info(f"接收到AI配置 - 模型: {ai_model}, URL: {ai_api_url[:30] if ai_api_url else '未提供'}")
            
        # 保存上传的Excel文件（使用FileUploader处理）
        saved_filepaths = []
        try:
            logger.info("准备保存上传的文件")
            for f in files:
                path = file_uploader.save_uploaded_file(f, prefix="upload")
                saved_filepaths.append((f.filename, path))
                logger.info(f"已保存: 原始文件名={f.filename}, 保存路径={path}")
        except FileTypeError:
            logger.error("文件类型不支持，仅支持Excel文件")
            return jsonify({'error': '只支持Excel文件(xlsx, xls)'}), 400
        except FileSizeError:
            logger.error("文件大小超过16MB限制")
            return jsonify({'error': '文件大小超过限制(16MB)'}), 400
        except FileSaveError as e:
            error_msg = str(e)
            logger.error(f"文件保存失败: {error_msg}")
            return jsonify({'error': f'文件保存失败: {error_msg}'}), 500
        except Exception as e:
            error_msg = str(e)
            logger.error(f"文件处理过程中出现意外错误: {error_msg}")
            logger.error(traceback.format_exc())
            return jsonify({'error': f'文件处理错误: {error_msg}'}), 500
        
        # 保存关键词规则到临时文件
        keywords_filepath = file_uploader.create_temp_file(keywords_text, "keywords.md")
        logger.info(f"已保存关键词规则文件: {keywords_filepath}")
        
        # 创建临时的数据目录
        temp_data_dir = file_uploader.create_temp_directory("data")
        
        # 复制文件到临时数据目录（使用已保存的唯一文件名，避免重名覆盖）
        temp_keywords_path = os.path.join(temp_data_dir, 'keywords.md')
        shutil.copy2(keywords_filepath, temp_keywords_path)
        for original_name, saved_path in saved_filepaths:
            unique_name = os.path.basename(saved_path)
            target_path = os.path.join(temp_data_dir, unique_name)
            shutil.copy2(saved_path, target_path)
            logger.info(f"已复制到临时数据目录: {unique_name}")
        
        # 创建临时的结果目录
        temp_results_dir = file_uploader.create_temp_directory("results")
            
        # 从配置管理器获取所有必要的配置
        keyword_config = config_manager.get_keyword_config()
        export_config = config_manager.get_export_config()
        ai_config = config_manager.get_ai_api_config()
        
        # 为进度持久化创建progress文件
        progress_file = None
        try:
            if progress_key:
                progress_dir = os.path.join(file_uploader.upload_folder, 'progress')
                os.makedirs(progress_dir, exist_ok=True)
                progress_file = os.path.join(progress_dir, f"{progress_key}.json")
        except Exception:
            progress_file = None

        # 定义进度回调：写入内存与磁盘文件，供前端轮询读取
        def progress_callback(done, total):
            try:
                percent = 0
                try:
                    total = int(total) if total else 0
                    done = int(done)
                    percent = int(done * 100 / total) if total > 0 else 0
                except Exception:
                    percent = 0
                if progress_key:
                    progress_store[progress_key] = {
                        'done': done,
                        'total': total,
                        'percent': percent
                    }
                if progress_file:
                    try:
                        with open(progress_file, 'w', encoding='utf-8') as f:
                            json.dump({'done': done, 'total': total, 'percent': percent}, f, ensure_ascii=False)
                    except Exception:
                        pass
            except Exception:
                pass

        # 创建KeywordAnalyzer实例，使用正确的参数格式
        analyzer = KeywordAnalyzer(
            data_folder=temp_data_dir,
            keyword_patterns=None,  # 先不设置，让markdown读取和表单设置按顺序进行
            keyword_columns=keyword_config['keyword_columns'],
            volume_columns=keyword_config['volume_columns'],
            output_filename_prefix=export_config['output_filename_prefix'],
            ai_api_endpoint=ai_config['endpoint'],
            ai_api_key=ai_api_key,
            progress_callback=progress_callback
        )
        
        # 设置必要的属性
        analyzer.results_folder = temp_results_dir
        # 为了后续访问配置，将config_manager保存为实例属性
        analyzer.config_manager = config_manager
            
        # 先让analyzer从markdown文件读取关键词规则（如果存在）
        analyzer.read_keyword_patterns_from_markdown()
        
        # 然后从表单设置关键词规则（表单设置优先于markdown文件）
        if keywords_text.strip():
            # 将表单中的关键词文本转换为正则表达式模式
            # 支持换行符、逗号或空格分隔的关键词
            keywords = [k.strip() for k in re.split('[\\n,\\s]+', keywords_text) if k.strip()]
            if keywords:
                # 转义每个关键词并创建或模式
                analyzer.keyword_patterns = '|'.join([re.escape(k) for k in keywords])
                logger.info(f"表单关键词规则已应用，覆盖了markdown文件设置: {analyzer.keyword_patterns}")
            else:
                logger.warning("表单中的关键词规则为空或无效，继续使用markdown文件中的规则")
            
            # 如果用户提供了API配置，则更新
            if ai_api_key:
                analyzer.ai_api_key = ai_api_key
                logger.info("已设置AI API密钥")
            if ai_api_url:
                analyzer.ai_api_endpoint = ai_api_url
                logger.info(f"已设置AI API端点: {ai_api_url[:30]}...")
            if ai_model:
                config_manager.ai_model_type = ai_model.lower()
                logger.info(f"已设置AI模型类型: {ai_model.lower()}")
            
            # 运行分析
            result = analyzer.run_full_analysis()
            
            # 检查是否有警告信息
            warnings = result.get('warnings', [])
            
            # 如果没有输出文件但有警告，返回警告信息
            if not result.get('output_file'):
                if warnings:
                    return jsonify({'warnings': warnings, 'error': '未生成分析结果'}), 200
                else:
                    return jsonify({'error': '分析失败，请检查文件格式和关键词规则'}), 500
            
            output_file = result['output_file']
            
            # 获取统计信息
            total_keywords = result.get('total_keywords', 0)
            matched_keywords = result.get('matched_keywords', 0)
            
            # 使用文件结果处理器来提供文件下载
            try:
                # 准备分析结果字典
                analysis_result = {
                    'output_file': output_file,
                    'total_keywords': total_keywords,
                    'matched_keywords': matched_keywords,
                    'warnings': warnings
                }
                
                # 使用文件结果处理器提供文件下载
                response, error = file_result_handler.serve_file(output_file, analysis_result)
                
                if error:
                    logger.error(f"文件结果处理器出错: {error}")
                    return jsonify({'error': f'文件准备失败: {error}'}), 500
                
                # 添加分析统计信息到响应头，供前端使用
                response.headers['X-Total-Keywords'] = str(total_keywords)
                response.headers['X-Matched-Keywords'] = str(matched_keywords)
                # 在完成后，设置进度为100%
                try:
                    if progress_key:
                        progress_store[progress_key] = {
                            'done': total_keywords,
                            'total': total_keywords,
                            'percent': 100
                        }
                    if progress_file:
                        try:
                            with open(progress_file, 'w', encoding='utf-8') as f:
                                json.dump({'done': total_keywords, 'total': total_keywords, 'percent': 100}, f, ensure_ascii=False)
                        except Exception:
                            pass
                except Exception:
                    pass
                
                return response
            except Exception as e:
                logger.error(f"处理文件下载时出错: {str(e)}")
                logger.error(traceback.format_exc())
                return jsonify({'error': f'文件下载处理失败: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"处理分析请求时出错: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

# 删除临时文件路由
@app.route('/delete-temp-file', methods=['POST'])
def delete_temp_file():
    """删除分析生成的临时文件"""
    try:
        # 从请求中获取文件名
        data = request.get_json()
        action = data.get('delete') if data else None
        filename = data.get('filename') if data else None
        
        # 优先支持删除结果目录
        if action == 'results_folder':
            success = file_result_handler.delete_last_results_folder()
            if success:
                logger.info("结果目录已成功删除")
                return jsonify({'success': True, 'message': 'sucess'}), 200
            else:
                logger.error("结果目录删除失败")
                return jsonify({'error': 'fail，请稍后重试'}), 500
        
        # 清空uploads根目录
        if action == 'clear_uploads':
            success = file_result_handler.clear_uploads_folder()
            if success:
                logger.info("uploads目录已清空")
                return jsonify({'success': True, 'message': 'uploads目录已清空'}), 200
            else:
                logger.error("uploads目录清空失败")
                return jsonify({'error': '清空uploads失败，请稍后重试'}), 500

        # 清理上传中间产物（data_* 与 upload_*）
        if action == 'cleanup_upload_artifacts':
            success = file_result_handler.cleanup_upload_artifacts()
            if success:
                logger.info("上传中间文件已清理")
                return jsonify({'success': True, 'message': 'success'}), 200
            else:
                logger.error("上传中间文件清理失败")
                return jsonify({'error': 'fail'}), 500

        # 删除progress目录
        if action == 'clear_progress':
            success = file_result_handler.clear_progress_folder()
            if success:
                logger.info("progress目录已清空")
                return jsonify({'success': True, 'message': 'progress目录已清空'}), 200
            else:
                logger.error("progress目录清空失败")
                return jsonify({'error': 'progress目录清空失败'}), 500
        
        # 兼容旧逻辑：按文件名删除
        if filename:
            success = file_result_handler.delete_file_by_name(filename)
            if success:
                logger.info(f"临时文件 {filename} 已成功删除")
                return jsonify({'success': True, 'message': '临时文件已删除'}), 200
            else:
                logger.error(f"文件结果处理器无法删除文件: {filename}")
                return jsonify({'error': '文件删除失败，请稍后重试'}), 500
        
        logger.warning("请求中未提供有效删除参数")
        return jsonify({'error': '未提供删除参数'}), 400
    
    except Exception as e:
        logger.error(f"处理删除文件请求时出错: {str(e)}")
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500

# 保存AI模型类型配置
@app.route('/save-model-config', methods=['POST'])
def save_model_config():
    """保存AI模型类型到.env文件"""
    logger.info("收到保存AI模型类型请求")
    
    try:
        # 获取AI模型类型
        ai_model = request.form.get('ai_model', 'deepseek').lower()
        logger.info(f"接收到AI模型类型: {ai_model}")
        
        # 验证模型类型
        if ai_model not in ['deepseek', 'tongyi']:
            logger.warning(f"无效的AI模型类型: {ai_model}")
            return jsonify({'error': '无效的AI模型类型，仅支持deepseek或tongyi'}), 400
        
        # 更新配置管理器中的模型类型
        config_manager.ai_model_type = ai_model
        
        # 创建配置字典，只包含AI模型类型
        config_dict = {'AI_MODEL_TYPE': ai_model}
        
        # 保存配置到.env文件
        success = config_manager.save_config_to_env(config_dict)
        
        if success:
            logger.info(f"AI模型类型 {ai_model} 已成功保存到.env文件")
            return jsonify({
                'success': True,
                'message': f'AI模型类型已成功设置为{"通义千问" if ai_model == "tongyi" else "DeepSeek"}',
                'model_type': ai_model
            }), 200
        else:
            logger.error("保存AI模型类型到.env文件失败")
            return jsonify({'error': '保存配置失败，请检查文件权限'}), 500
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"保存AI模型类型时出错: {error_msg}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'保存失败: {error_msg}'}), 500

# 保存关键词规则
@app.route('/save-keywords', methods=['POST'])
def save_keywords():
    """保存关键词规则到keywords.md文件"""
    logger.info("收到保存关键词规则请求")
    
    try:
        # 获取关键词文本
        keywords_text = request.form.get('keywords', '')
        logger.debug(f"关键词规则文本长度: {len(keywords_text)}")
        
        if not keywords_text.strip():
            logger.warning("关键词筛选规则为空")
            return jsonify({'error': '关键词规则不能为空'}), 400
        
        # 使用KeywordManager保存关键词规则
        keyword_manager.save_keywords(keywords_text)
        logger.info("关键词规则已成功保存到keywords.md")
        
        # 获取保存后的关键词列表用于确认
        saved_keywords = keyword_manager.load_keywords()
        
        return jsonify({
            'success': True,
            'message': '关键词规则已成功保存',
            'saved_keywords_count': len(saved_keywords)
        }), 200
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"保存关键词规则失败: {error_msg}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'保存失败: {error_msg}'}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'message': 'SEO关键词分析工具运行正常'})

# 进度查询API
@app.route('/progress', methods=['GET'])
def progress():
    try:
        key = request.args.get('key', '')
        data = progress_store.get(key) if key else None
        if not data:
            # 回退到磁盘进度文件
            try:
                progress_dir = os.path.join(file_uploader.upload_folder, 'progress')
                progress_file = os.path.join(progress_dir, f"{key}.json")
                if key and os.path.exists(progress_file):
                    with open(progress_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
            except Exception:
                data = None
        if not data:
            return jsonify({'percent': 0, 'done': 0, 'total': 0})
        return jsonify({
            'percent': int(data.get('percent', 0)),
            'done': int(data.get('done', 0)),
            'total': int(data.get('total', 0))
        })
    except Exception:
        return jsonify({'percent': 0, 'done': 0, 'total': 0})

# 处理@vite/client路径，防止404错误
@app.route('/@vite/client', methods=['GET'])
def vite_client():
    return Response(status=204)

if __name__ == '__main__':
    # 在生产环境中，这个部分不会被使用，因为会使用Gunicorn或uWSGI
    # 在开发环境中启用debug模式以便更好地排查问题
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=debug_mode)

# 用于WSGI服务器的应用入口
wsgi_app = app