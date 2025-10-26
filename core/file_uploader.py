import os
import shutil
import tempfile
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

class FileUploadError(Exception):
    """文件上传相关的异常基类"""
    pass

class FileTypeError(FileUploadError):
    """文件类型不支持的异常"""
    pass

class FileSizeError(FileUploadError):
    """文件大小超出限制的异常"""
    pass

class FileSaveError(FileUploadError):
    """文件保存失败的异常"""
    pass

class DirectoryAccessError(FileUploadError):
    """目录访问权限错误的异常"""
    pass

class FileUploader:
    """
    文件上传管理类，负责处理文件的验证、保存和清理
    
    功能特点：
    - 支持文件类型验证
    - 支持文件大小限制
    - 自动生成唯一文件名
    - 临时文件管理和清理
    - 完善的错误处理和日志记录
    - 支持目录创建和权限检查
    """
    
    def __init__(self,
                 allowed_extensions: set = None,
                 max_file_size: int = 16 * 1024 * 1024,  # 默认16MB
                 upload_folder: str = None,
                 logger: logging.Logger = None):
        """
        初始化文件上传器
        
        Args:
            allowed_extensions: 允许的文件扩展名集合，默认允许xlsx和xls
            max_file_size: 最大文件大小（字节），默认16MB
            upload_folder: 上传目录路径，如果为None则使用应用目录下的uploads文件夹
            logger: 日志记录器，如果为None则创建默认日志记录器
        """
        self.allowed_extensions = allowed_extensions or {'xlsx', 'xls'}
        self.max_file_size = max_file_size
        self.logger = logger or logging.getLogger(__name__)
        
        # 设置上传目录
        self.upload_folder = self._setup_upload_folder(upload_folder)
        self.temp_files: List[str] = []  # 跟踪临时文件以便后续清理
    
    def _setup_upload_folder(self, upload_folder: Optional[str]) -> str:
        """
        设置并验证上传目录
        
        Args:
            upload_folder: 指定的上传目录路径
            
        Returns:
            str: 可用的上传目录路径
            
        Raises:
            DirectoryAccessError: 如果无法创建或访问上传目录
        """
        # 如果没有指定上传目录，使用应用目录下的uploads文件夹
        if not upload_folder:
            # 获取当前文件的目录（core目录），然后上一级就是应用根目录
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            upload_folder = os.path.join(app_root, 'uploads')
            self.logger.info(f"未指定上传目录，默认使用应用目录下的uploads文件夹: {upload_folder}")
        else:
            self.logger.info(f"使用指定的上传目录: {upload_folder}")
        
        # 尝试创建上传目录
        try:
            self.logger.debug(f"开始创建上传目录: {upload_folder}")
            os.makedirs(upload_folder, exist_ok=True)
            self.logger.info(f"上传目录已设置: {upload_folder}")
            
            # 检查目录是否存在
            if not os.path.exists(upload_folder):
                self.logger.error(f"目录创建后检查失败: {upload_folder} 不存在")
                # 回退到系统临时目录
                upload_folder = tempfile.gettempdir()
                self.logger.warning(f"目录检查失败，回退到系统临时目录: {upload_folder}")
            else:
                # 验证目录是否可写
                test_file = os.path.join(upload_folder, f"test_{datetime.now().timestamp()}.tmp")
                self.logger.debug(f"开始验证目录写入权限，测试文件: {test_file}")
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    # 验证写入是否成功
                    if os.path.exists(test_file) and os.path.getsize(test_file) > 0:
                        self.logger.info(f"上传目录写入权限验证通过")
                        os.remove(test_file)
                    else:
                        self.logger.error(f"测试文件写入后检查失败: {test_file} 不存在或为空")
                        # 如果无法写入，回退到系统临时目录
                        upload_folder = tempfile.gettempdir()
                        self.logger.warning(f"测试文件检查失败，回退到系统临时目录: {upload_folder}")
                except Exception as e:
                    self.logger.error(f"上传目录写入权限验证失败: {str(e)}")
                    # 如果无法写入，回退到系统临时目录
                    upload_folder = tempfile.gettempdir()
                    self.logger.warning(f"写入测试失败，回退到系统临时目录: {upload_folder}")
        
        except Exception as e:
            self.logger.error(f"创建上传目录失败: {str(e)}")
            # 回退到系统临时目录
            upload_folder = tempfile.gettempdir()
            self.logger.warning(f"创建目录失败，回退到系统临时目录: {upload_folder}")
            
            # 再次验证系统临时目录
            try:
                self.logger.debug(f"开始验证系统临时目录: {upload_folder}")
                os.makedirs(upload_folder, exist_ok=True)
                # 再次检查写入权限
                test_file = os.path.join(upload_folder, f"temp_test_{datetime.now().timestamp()}.tmp")
                with open(test_file, 'w') as f:
                    f.write('temp_test')
                os.remove(test_file)
                self.logger.info(f"系统临时目录验证通过")
            except Exception as e:
                self.logger.critical(f"无法创建或访问临时目录: {str(e)}")
                raise DirectoryAccessError(f"无法创建或访问任何上传目录: {str(e)}")
        
        return upload_folder
    
    def allowed_file(self, filename: str) -> bool:
        """
        检查文件扩展名是否允许
        
        Args:
            filename: 文件名
            
        Returns:
            bool: 如果文件类型允许则返回True
        """
        return ('.' in filename and 
                filename.rsplit('.', 1)[1].lower() in self.allowed_extensions)
    
    def save_uploaded_file(self, file_obj, prefix: str = "upload") -> str:
        """
        保存上传的文件到上传目录
        
        Args:
            file_obj: Flask上传的文件对象
            prefix: 文件名前缀
            
        Returns:
            str: 保存后的文件路径
            
        Raises:
            FileTypeError: 如果文件类型不支持
            FileSizeError: 如果文件大小超出限制
            FileSaveError: 如果文件保存失败
        """
        # 记录开始保存的详细信息
        self.logger.info(f"开始处理文件上传，prefix={prefix}")
        
        # 验证文件对象
        if not file_obj:
            self.logger.error("文件对象为None")
            raise FileSaveError("未提供有效的文件对象")
        
        # 验证文件名
        if not hasattr(file_obj, 'filename'):
            self.logger.error("文件对象没有filename属性")
            raise FileSaveError("文件对象无效：缺少filename属性")
        
        filename = file_obj.filename
        self.logger.debug(f"接收到的文件名: {filename}")
        
        if not filename:
            self.logger.error("文件名不能为空")
            raise FileSaveError("未提供有效的文件名")
        
        # 验证文件类型
        if not self.allowed_file(filename):
            allowed_types = ', '.join(self.allowed_extensions)
            error_msg = f"不支持的文件类型，仅支持: {allowed_types}"
            self.logger.error(f"文件类型验证失败: {filename}, 错误: {error_msg}")
            raise FileTypeError(error_msg)
        
        # 检查文件对象是否有save方法
        if not hasattr(file_obj, 'save'):
            self.logger.error("文件对象没有save方法")
            raise FileSaveError("文件对象无效：缺少save方法")
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 精确到毫秒
        file_ext = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{prefix}_{timestamp}.{file_ext}"
        filepath = os.path.join(self.upload_folder, unique_filename)
        self.logger.info(f"生成唯一文件名: {unique_filename}")
        self.logger.debug(f"文件将保存到: {filepath}")
        
        # 检查目标目录是否存在
        if not os.path.exists(self.upload_folder):
            error_msg = f"上传目录不存在: {self.upload_folder}"
            self.logger.error(error_msg)
            raise FileSaveError(error_msg)
        
        # 保存文件
        try:
            self.logger.info(f"准备保存文件: {filename} -> {unique_filename}")
            
            # 尝试获取文件大小（如果可能）
            if hasattr(file_obj, 'content_length') and file_obj.content_length:
                self.logger.debug(f"文件预估大小: {file_obj.content_length} 字节")
                if file_obj.content_length > self.max_file_size:
                    error_msg = f"文件大小超出限制: {file_obj.content_length} 字节 > {self.max_file_size} 字节"
                    self.logger.error(error_msg)
                    raise FileSizeError(error_msg)
            
            # 保存文件（支持Flask文件对象）
            start_time = time.time()
            file_obj.save(filepath)
            save_time = time.time() - start_time
            self.logger.info(f"文件保存操作完成，耗时: {save_time:.4f} 秒")
            
            # 验证文件是否成功保存
            if not os.path.exists(filepath):
                error_msg = f"文件保存后不存在: {filepath}"
                self.logger.error(error_msg)
                raise FileSaveError(error_msg)
            
            # 检查文件大小
            file_size = os.path.getsize(filepath)
            self.logger.debug(f"保存后文件大小: {file_size} 字节")
            
            if file_size == 0:
                os.remove(filepath)
                error_msg = "保存的文件为空"
                self.logger.error(error_msg)
                raise FileSaveError(error_msg)
            
            if file_size > self.max_file_size:
                os.remove(filepath)  # 删除过大的文件
                error_msg = f"文件大小超出限制: {file_size} 字节 > {self.max_file_size} 字节"
                self.logger.error(error_msg)
                raise FileSizeError(error_msg)
            
            # 将文件添加到临时文件列表
            self.temp_files.append(filepath)
            self.logger.debug(f"已将文件添加到临时文件列表，当前列表长度: {len(self.temp_files)}")
            
            self.logger.info(f"文件保存成功: {unique_filename}, 大小: {file_size} 字节")
            return filepath
            
        except FileUploadError:
            # 重新抛出FileUploadError类型的异常
            self.logger.debug("捕获到FileUploadError类型异常，重新抛出")
            raise
        except Exception as e:
            error_msg = f"文件保存失败: {str(e)}"
            self.logger.error(f"文件保存异常: {filename}, 错误: {error_msg}")
            self.logger.debug(f"文件保存异常详情:", exc_info=True)
            # 尝试删除可能创建的部分文件
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    self.logger.info(f"已删除部分保存的文件: {filepath}")
                except:
                    pass
            raise FileSaveError(error_msg)
    
    def create_temp_file(self, content: str, filename: str) -> str:
        """
        创建临时文件
        
        Args:
            content: 文件内容
            filename: 文件名
            
        Returns:
            str: 创建的文件路径
        """
        filepath = os.path.join(self.upload_folder, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 将文件添加到临时文件列表
            self.temp_files.append(filepath)
            self.logger.info(f"临时文件已创建: {filename}")
            return filepath
            
        except Exception as e:
            error_msg = f"创建临时文件失败: {str(e)}"
            self.logger.error(error_msg)
            raise FileSaveError(error_msg)
    
    def create_temp_directory(self, prefix: str = "temp") -> str:
        """
        创建临时目录
        
        Args:
            prefix: 目录名前缀
            
        Returns:
            str: 创建的目录路径
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        dirname = f"{prefix}_{timestamp}"
        dirpath = os.path.join(self.upload_folder, dirname)
        
        try:
            os.makedirs(dirpath, exist_ok=True)
            # 将目录添加到临时文件列表以便后续清理
            self.temp_files.append(dirpath)
            self.logger.info(f"临时目录已创建: {dirname}")
            return dirpath
            
        except Exception as e:
            error_msg = f"创建临时目录失败: {str(e)}"
            self.logger.error(error_msg)
            raise DirectoryAccessError(error_msg)
    
    def copy_file(self, src_path: str, dest_path: str) -> str:
        """
        复制文件
        
        Args:
            src_path: 源文件路径
            dest_path: 目标文件路径
            
        Returns:
            str: 目标文件路径
        """
        try:
            # 确保目标目录存在
            dest_dir = os.path.dirname(dest_path)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            shutil.copy2(src_path, dest_path)
            self.temp_files.append(dest_path)
            self.logger.info(f"文件已复制: {src_path} -> {dest_path}")
            return dest_path
            
        except Exception as e:
            error_msg = f"文件复制失败: {str(e)}"
            self.logger.error(error_msg)
            raise FileSaveError(error_msg)
    
    def cleanup(self):
        """
        清理所有临时文件和目录
        """
        self.logger.info(f"开始清理临时文件，共 {len(self.temp_files)} 个项目")
        
        for item_path in self.temp_files:
            try:
                if os.path.exists(item_path):
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        self.logger.info(f"已删除临时目录: {item_path}")
                    else:
                        os.remove(item_path)
                        self.logger.info(f"已删除临时文件: {item_path}")
                else:
                    self.logger.warning(f"临时项目不存在: {item_path}")
                    
            except Exception as e:
                self.logger.error(f"删除临时项目失败: {item_path}, 错误: {str(e)}")
        
        # 清空临时文件列表
        self.temp_files.clear()
        self.logger.info("临时文件清理完成")
    
    def __enter__(self):
        """支持上下文管理器协议"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文退出时自动清理临时文件"""
        self.cleanup()

# 导出异常类，方便使用
export = {
    'FileUploadError': FileUploadError,
    'FileTypeError': FileTypeError,
    'FileSizeError': FileSizeError,
    'FileSaveError': FileSaveError,
    'DirectoryAccessError': DirectoryAccessError,
    'FileUploader': FileUploader
}