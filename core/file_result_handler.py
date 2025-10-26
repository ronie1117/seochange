import os
import shutil
import logging
from datetime import datetime
from flask import send_file, Response, session

# 配置日志记录器
logger = logging.getLogger(__name__)

class FileResultHandler:
    """
    文件结果处理器，专门负责管理生成的文件并提供给前端下载。
    该类提供了安全、统一的文件管理和下载功能。
    """
    
    def __init__(self, uploader=None):
        """
        初始化文件结果处理器
        
        Args:
            uploader: 文件上传器实例，用于创建临时目录和文件
        """
        self.uploader = uploader
        logger.info("FileResultHandler 已初始化")
    
    def prepare_file_for_download(self, file_path, analysis_result=None):
        """
        准备文件以供下载，添加必要的安全检查
        
        Args:
            file_path: 要提供下载的文件路径
            analysis_result: 分析结果字典，包含统计信息等
            
        Returns:
            tuple: (file_path, metadata_dict) 或 (None, error_message)
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"文件不存在: {file_path}"
            logger.error(error_msg)
            return None, error_msg
        
        # 验证文件路径的安全性
        if not self._is_safe_file_path(file_path):
            error_msg = f"不安全的文件路径: {file_path}"
            logger.error(error_msg)
            return None, error_msg
        
        # 准备元数据
        metadata = {
            'file_size': os.path.getsize(file_path),
            'file_name': os.path.basename(file_path),
            'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S')
        }
        
        # 如果提供了分析结果，添加分析相关的元数据
        if analysis_result:
            metadata['total_keywords'] = analysis_result.get('total_keywords', 0)
            metadata['matched_keywords'] = analysis_result.get('matched_keywords', 0)
            metadata['warnings'] = analysis_result.get('warnings', [])
        
        logger.info(f"已准备文件供下载: {file_path}，大小: {metadata['file_size']} 字节")
        return file_path, metadata
    
    def create_download_response(self, file_path, metadata):
        """
        创建文件下载响应
        
        Args:
            file_path: 文件路径
            metadata: 文件元数据
            
        Returns:
            Response: Flask响应对象，包含文件和适当的头信息
        """
        # 生成英文文件名以避免Unicode编码问题
        timestamp = metadata['timestamp']
        english_filename = f"keyword_analysis_{timestamp}.xlsx"
        
        # 创建响应
        try:
            response = send_file(file_path, as_attachment=True)
            
            # 设置响应头
            response.headers['Content-Disposition'] = f'attachment; filename="{english_filename}"' 
            response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            response.headers['Content-Length'] = str(metadata['file_size'])
            
            # 添加额外的响应头以确保浏览器正确处理下载
            response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition, X-Total-Keywords, X-Matched-Keywords'
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            
            # 添加分析结果相关的头信息
            if 'total_keywords' in metadata:
                response.headers['X-Total-Keywords'] = str(metadata['total_keywords'])
            if 'matched_keywords' in metadata:
                response.headers['X-Matched-Keywords'] = str(metadata['matched_keywords'])
            
            # 如果有警告信息，添加到响应头中
            if 'warnings' in metadata and metadata['warnings']:
                warnings_str = ';'.join(metadata['warnings'])
                response.headers['X-Warnings'] = warnings_str
            
            # 保存文件路径到会话，以便后续删除
            session['last_output_file'] = file_path
            # 同时保存结果目录，便于批量清理
            try:
                session['last_results_dir'] = os.path.dirname(file_path)
            except Exception:
                pass
            
            logger.info(f"已创建下载响应，文件名: {english_filename}")
            return response
            
        except Exception as e:
            error_msg = f"创建下载响应失败: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def serve_file(self, file_path, analysis_result=None):
        """
        提供文件下载的主要方法
        
        Args:
            file_path: 文件路径
            analysis_result: 分析结果字典
            
        Returns:
            Response: Flask响应对象或错误响应
        """
        # 准备文件
        prepared_file, metadata = self.prepare_file_for_download(file_path, analysis_result)
        
        if prepared_file is None:
            # 如果准备文件失败，返回错误信息
            return None, metadata
        
        # 创建并返回下载响应
        try:
            response = self.create_download_response(prepared_file, metadata)
            return response, None
        except Exception as e:
            return None, str(e)
    
    def delete_file(self, file_path):
        """
        安全地删除文件
        
        Args:
            file_path: 要删除的文件路径
            
        Returns:
            bool: 是否成功删除
        """
        # 验证文件路径的安全性
        if not self._is_safe_file_path(file_path):
            logger.error(f"尝试删除不安全的文件路径: {file_path}")
            return False
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.warning(f"尝试删除不存在的文件: {file_path}")
            return False
        
        try:
            # 尝试删除文件
            os.remove(file_path)
            logger.info(f"已删除文件: {file_path}")
            
            # 尝试删除空的父目录
            self._try_remove_empty_directory(os.path.dirname(file_path))
            
            return True
        except Exception as e:
            logger.error(f"删除文件失败: {file_path}, 错误: {str(e)}")
            return False
            
    def delete_file_by_name(self, filename):
        """
        根据文件名安全删除文件
        搜索结果目录查找匹配的文件
        
        Args:
            filename: 要删除的文件名
            
        Returns:
            bool: 删除是否成功
        """
        try:
            # 在结果目录中搜索匹配的文件
            if not filename or (not self.uploader or not hasattr(self.uploader, 'upload_folder')):
                logger.error(f"无效的文件名或上传目录: {filename}")
                return False
            
            upload_dir = self.uploader.upload_folder
            # 递归搜索上传目录中的文件
            for root, _, files in os.walk(upload_dir):
                if filename in files:
                    file_path = os.path.join(root, filename)
                    # 使用delete_file方法进行安全删除
                    return self.delete_file(file_path)
            
            logger.warning(f"在上传目录中未找到文件: {filename}")
            return False
        except Exception as e:
            logger.error(f"按名称删除文件时出错: {str(e)}")
            return False

    def delete_last_results_folder(self):
        """
        删除本次下载对应的结果目录（会话中保存的最后输出所在目录）
        """
        try:
            results_dir = session.get('last_results_dir')
            if not results_dir:
                logger.warning("会话中未找到结果目录信息")
                return False
            if not os.path.exists(results_dir):
                logger.warning(f"结果目录不存在: {results_dir}")
                return False
            # 路径安全校验
            if not self._is_safe_file_path(results_dir):
                logger.error(f"不安全的目录路径: {results_dir}")
                return False
            # 只删除以results_前缀创建的临时目录
            base_name = os.path.basename(results_dir)
            if not base_name.startswith('results_'):
                logger.error(f"拒绝删除非临时结果目录: {results_dir}")
                return False
            # 执行删除
            shutil.rmtree(results_dir)
            logger.info(f"已删除结果目录: {results_dir}")
            # 清理会话信息
            try:
                session.pop('last_results_dir', None)
                session.pop('last_output_file', None)
            except Exception:
                pass
            # 尝试删除空父目录
            self._try_remove_empty_directory(os.path.dirname(results_dir))
            return True
        except Exception as e:
            logger.error(f"删除结果目录失败: {str(e)}")
            return False

    def clear_uploads_folder(self):
        """
        清空上传根目录（仅删除其内部内容，不删除根目录本身）
        """
        try:
            if not (self.uploader and hasattr(self.uploader, 'upload_folder')):
                logger.error("未配置上传目录，无法清空uploads")
                return False
            upload_dir = os.path.abspath(self.uploader.upload_folder)
            if not os.path.exists(upload_dir):
                logger.warning(f"上传目录不存在: {upload_dir}")
                return True
            # 安全校验上传目录本身
            if not self._is_safe_file_path(upload_dir):
                logger.error(f"不安全的上传目录路径: {upload_dir}")
                return False
            # 遍历并删除内容
            for name in os.listdir(upload_dir):
                target = os.path.join(upload_dir, name)
                # 再次确保在上传目录内
                if not self._is_safe_file_path(target):
                    logger.warning(f"跳过不安全路径: {target}")
                    continue
                try:
                    if os.path.isdir(target):
                        shutil.rmtree(target)
                        logger.info(f"已删除目录: {target}")
                    else:
                        os.remove(target)
                        logger.info(f"已删除文件: {target}")
                except Exception as e:
                    logger.error(f"删除失败: {target}, 错误: {str(e)}")
                    # 不中断，继续删除其他项
                    continue
            logger.info("uploads目录内容已清空")
            return True
        except Exception as e:
            logger.error(f"清空uploads目录失败: {str(e)}")
            return False

    def cleanup_upload_artifacts(self):
        """
        仅清理上传目录中分析过程产生的中间文件：
        - 删除所有以 data_ 开头的临时数据目录
        - 删除所有以 upload_ 开头的上传临时文件
        保留其他文件（如 progress、results 等由其他流程管理）
        """
        try:
            if not (self.uploader and hasattr(self.uploader, 'upload_folder')):
                logger.error("未配置上传目录，无法执行清理")
                return False
            upload_dir = os.path.abspath(self.uploader.upload_folder)
            if not os.path.exists(upload_dir):
                logger.warning(f"上传目录不存在: {upload_dir}")
                return True
            if not self._is_safe_file_path(upload_dir):
                logger.error(f"不安全的上传目录路径: {upload_dir}")
                return False
            removed_any = False
            for name in os.listdir(upload_dir):
                target = os.path.join(upload_dir, name)
                if not self._is_safe_file_path(target):
                    continue
                try:
                    if os.path.isdir(target) and name.startswith('data_'):
                        shutil.rmtree(target)
                        logger.info(f"已删除临时数据目录: {target}")
                        removed_any = True
                    elif os.path.isfile(target) and name.startswith('upload_'):
                        os.remove(target)
                        logger.info(f"已删除上传临时文件: {target}")
                        removed_any = True
                except Exception as e:
                    logger.error(f"清理失败: {target}, 错误: {str(e)}")
                    # 不中断
                    continue
            if not removed_any:
                logger.info("无需清理：未发现 data_ 目录或 upload_ 文件")
            return True
        except Exception as e:
            logger.error(f"清理上传中间文件失败: {str(e)}")
            return False

    def clear_progress_folder(self):
        """
        删除uploads目录下的progress文件夹（含其所有内容）。
        下次有进度写入时会自动重建。
        """
        try:
            if not (self.uploader and hasattr(self.uploader, 'upload_folder')):
                logger.error("未配置上传目录，无法删除progress目录")
                return False
            upload_dir = os.path.abspath(self.uploader.upload_folder)
            progress_dir = os.path.join(upload_dir, 'progress')
            if not os.path.exists(progress_dir):
                logger.info("progress目录不存在，无需删除")
                return True
            # 安全校验
            if not self._is_safe_file_path(progress_dir):
                logger.error(f"不安全的目录路径: {progress_dir}")
                return False
            shutil.rmtree(progress_dir)
            logger.info(f"已删除progress目录: {progress_dir}")
            return True
        except Exception as e:
            logger.error(f"删除progress目录失败: {str(e)}")
            return False
    
    def _is_safe_file_path(self, file_path):
        """
        检查文件路径是否安全
        
        Args:
            file_path: 要检查的文件路径
            
        Returns:
            bool: 如果路径安全则返回True
        """
        try:
            # 获取绝对路径
            abs_path = os.path.abspath(file_path)
            
            # 检查是否在临时目录或上传目录内
            # 这里假设有一个基础目录，所有操作都应该在这个目录内
            if self.uploader and hasattr(self.uploader, 'upload_folder'):
                base_dir = os.path.abspath(self.uploader.upload_folder)
                if not abs_path.startswith(base_dir):
                    return False
            
            # 避免目录遍历攻击
            if '..' in os.path.normpath(file_path).split(os.sep):
                return False
            
            return True
        except Exception:
            return False
    
    def _try_remove_empty_directory(self, directory_path):
        """
        尝试删除空目录
        
        Args:
            directory_path: 目录路径
        """
        try:
            if os.path.exists(directory_path) and not os.listdir(directory_path):
                os.rmdir(directory_path)
                logger.info(f"已删除空目录: {directory_path}")
                
                # 递归删除父目录（如果也为空）
                parent_dir = os.path.dirname(directory_path)
                if parent_dir and parent_dir != directory_path:  # 避免无限递归
                    self._try_remove_empty_directory(parent_dir)
        except Exception as e:
            logger.warning(f"删除目录失败: {directory_path}, 错误: {str(e)}")

# 创建一个全局的FileResultHandler实例供导入使用
file_result_handler = None

def init_file_result_handler(uploader=None):
    """
    初始化全局文件结果处理器
    
    Args:
        uploader: 文件上传器实例
    """
    global file_result_handler
    file_result_handler = FileResultHandler(uploader)
    logger.info("全局FileResultHandler已初始化")
    return file_result_handler