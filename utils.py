"""
工具函数模块
提供文件操作、图像处理、格式转换等辅助功能
"""

import os
import sys
import json
import shutil
from typing import List, Dict, Any, Optional
from datetime import datetime
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk


def get_supported_video_formats() -> List[str]:
    """获取支持的视频格式列表"""
    return [
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', 
        '.webm', '.m4v', '.3gp', '.mpg', '.mpeg', '.ts'
    ]


def is_video_file(file_path: str) -> bool:
    """
    检查文件是否为支持的视频格式
    
    Args:
        file_path: 文件路径
        
    Returns:
        是否为视频文件
    """
    if not os.path.isfile(file_path):
        return False
    
    ext = os.path.splitext(file_path)[1].lower()
    return ext in get_supported_video_formats()


def get_file_size_mb(file_path: str) -> float:
    """
    获取文件大小（MB）
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件大小（MB）
    """
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except OSError:
        return 0.0


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小显示
    
    Args:
        size_bytes: 字节数
        
    Returns:
        格式化的大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def create_thumbnail(image_path: str, size: tuple = (150, 150)) -> Optional[ImageTk.PhotoImage]:
    """
    创建图片缩略图
    
    Args:
        image_path: 图片路径
        size: 缩略图尺寸
        
    Returns:
        PIL ImageTk对象，失败返回None
    """
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
    except Exception:
        return None


def opencv_to_pil(cv_image: np.ndarray) -> Image.Image:
    """
    将OpenCV图像转换为PIL图像
    
    Args:
        cv_image: OpenCV图像数组
        
    Returns:
        PIL图像对象
    """
    # OpenCV使用BGR，PIL使用RGB
    rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_image)


def pil_to_opencv(pil_image: Image.Image) -> np.ndarray:
    """
    将PIL图像转换为OpenCV图像
    
    Args:
        pil_image: PIL图像对象
        
    Returns:
        OpenCV图像数组
    """
    # PIL使用RGB，OpenCV使用BGR
    rgb_array = np.array(pil_image)
    return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)


def resize_image_for_display(image: np.ndarray, max_width: int = 800, max_height: int = 600) -> np.ndarray:
    """
    调整图像大小以适应显示
    
    Args:
        image: 原始图像
        max_width: 最大宽度
        max_height: 最大高度
        
    Returns:
        调整后的图像
    """
    height, width = image.shape[:2]
    
    # 计算缩放比例
    scale_w = max_width / width
    scale_h = max_height / height
    scale = min(scale_w, scale_h, 1.0)  # 不放大图像
    
    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    
    return image


def save_project_config(config: Dict[str, Any], config_path: str = "config.json"):
    """
    保存项目配置
    
    Args:
        config: 配置字典
        config_path: 配置文件路径
    """
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"保存配置失败: {str(e)}")


def load_project_config(config_path: str = "config.json") -> Dict[str, Any]:
    """
    加载项目配置
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    default_config = {
        'last_video_path': '',
        'last_output_dir': '',
        'default_frame_interval': 1,
        'default_start_time': '00:00:00',
        'window_geometry': '1000x940+100+100',
        'recent_files': []
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 合并默认配置
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
    except Exception as e:
        print(f"加载配置失败: {str(e)}")
    
    return default_config


def add_recent_file(file_path: str, config_path: str = "config.json", max_recent: int = 10):
    """
    添加最近使用的文件
    
    Args:
        file_path: 文件路径
        config_path: 配置文件路径
        max_recent: 最大最近文件数量
    """
    config = load_project_config(config_path)
    recent_files = config.get('recent_files', [])
    
    # 移除已存在的相同路径
    if file_path in recent_files:
        recent_files.remove(file_path)
    
    # 添加到开头
    recent_files.insert(0, file_path)
    
    # 限制数量
    recent_files = recent_files[:max_recent]
    
    config['recent_files'] = recent_files
    save_project_config(config, config_path)


def clean_output_directory(output_dir: str, confirm_callback=None) -> bool:
    """
    清理输出目录
    
    Args:
        output_dir: 输出目录路径
        confirm_callback: 确认回调函数
        
    Returns:
        是否成功清理
    """
    if not os.path.exists(output_dir):
        return True
    
    try:
        # 获取目录中的文件数量（支持多种图片格式）
        files = [
            f for f in os.listdir(output_dir)
            if f.lower().endswith(('.png', '.webp', '.jpg', '.jpeg'))
        ]
        if not files:
            return True
        
        # 如果有确认回调，询问用户
        if confirm_callback:
            if not confirm_callback(f"目录中有 {len(files)} 个文件，是否清理？"):
                return False
        
        # 删除所有图片文件
        for file in files:
            file_path = os.path.join(output_dir, file)
            try:
                os.remove(file_path)
            except OSError:
                pass
        
        return True
    except Exception as e:
        print(f"清理目录失败: {str(e)}")
        return False


def get_directory_info(directory: str) -> Dict[str, Any]:
    """
    获取目录信息
    
    Args:
        directory: 目录路径
        
    Returns:
        目录信息字典
    """
    info = {
        'exists': False,
        'file_count': 0,
        'total_size': 0,
        'image_files': [],
        'last_modified': None
    }
    
    if not os.path.exists(directory):
        return info
    
    info['exists'] = True
    
    try:
        image_files = []
        total_size = 0
        
        for file in os.listdir(directory):
            if file.lower().endswith(('.png', '.webp', '.jpg', '.jpeg')):
                file_path = os.path.join(directory, file)
                file_size = os.path.getsize(file_path)
                file_mtime = os.path.getmtime(file_path)
                
                image_files.append({
                    'name': file,
                    'path': file_path,
                    'size': file_size,
                    'modified': datetime.fromtimestamp(file_mtime)
                })
                total_size += file_size
        
        # 按文件名排序
        image_files.sort(key=lambda x: x['name'])
        
        info.update({
            'file_count': len(image_files),
            'total_size': total_size,
            'image_files': image_files,
            'last_modified': max([f['modified'] for f in image_files]) if image_files else None
        })
        
    except Exception as e:
        print(f"获取目录信息失败: {str(e)}")
    
    return info


def validate_output_path(path: str) -> tuple[bool, str]:
    """
    验证输出路径是否有效
    
    Args:
        path: 路径字符串
        
    Returns:
        (是否有效, 错误信息)
    """
    if not path:
        return False, "路径不能为空"
    
    try:
        # 检查父目录是否存在
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            return False, f"父目录不存在: {parent_dir}"
        
        # 检查是否可写
        if os.path.exists(path):
            if not os.access(path, os.W_OK):
                return False, "目录不可写"
        else:
            # 尝试创建目录
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                return False, f"无法创建目录: {str(e)}"
        
        return True, ""
        
    except Exception as e:
        return False, f"路径验证失败: {str(e)}"


def get_available_space_gb(path: str) -> float:
    """
    获取路径所在磁盘的可用空间（GB）
    
    Args:
        path: 路径
        
    Returns:
        可用空间（GB）
    """
    try:
        if os.name == 'nt':  # Windows
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p(path),
                ctypes.pointer(free_bytes),
                None,
                None
            )
            return free_bytes.value / (1024**3)
        else:  # Unix/Linux
            statvfs = os.statvfs(path)
            return (statvfs.f_frsize * statvfs.f_bavail) / (1024**3)
    except Exception:
        return 0.0


def estimate_output_size(total_frames: int, frame_width: int, frame_height: int) -> float:
    """
    估算输出文件总大小（MB）
    
    Args:
        total_frames: 总帧数
        frame_width: 帧宽度
        frame_height: 帧高度
        
    Returns:
        估算大小（MB）
    """
    # PNG文件大小估算：每像素约2-4字节（考虑压缩）
    pixels_per_frame = frame_width * frame_height
    bytes_per_frame = pixels_per_frame * 3  # 保守估计
    total_bytes = total_frames * bytes_per_frame
    return total_bytes / (1024 * 1024)


def center_window(window, width: int, height: int):
    """
    将窗口居中显示
    
    Args:
        window: tkinter窗口对象
        width: 窗口宽度
        height: 窗口高度
    """
    # 获取屏幕尺寸
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # 计算居中位置
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    window.geometry(f"{width}x{height}+{x}+{y}")


def resource_path(relative_path: str) -> str:
    """
    获取资源文件路径（支持打包后的exe）
    
    Args:
        relative_path: 相对路径
        
    Returns:
        绝对路径
    """
    try:
        # PyInstaller创建的临时文件夹
        base_path = sys._MEIPASS
    except AttributeError:
        # 开发环境
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)
