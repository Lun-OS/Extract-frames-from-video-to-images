"""
视频帧提取核心模块
实现视频解析、帧提取、时间戳计算等核心功能
"""

import cv2
import os
import time
import subprocess
import shutil
from datetime import datetime, timedelta
from typing import Tuple, Optional, Callable
import concurrent.futures
import numpy as np
from PIL import Image
import threading
from utils import opencv_to_pil


class VideoProcessor:
    """视频处理器类"""
    
    def __init__(self, video_path: str):
        """
        初始化视频处理器
        
        Args:
            video_path: 视频文件路径
        """
        self.video_path = video_path
        self.cap = None
        self.video_info = {}
        # 预览相关锁，确保跨线程安全读取
        self._cap_lock = threading.Lock()
        self._load_video()
    
    def _load_video(self):
        """加载视频文件并获取基本信息"""
        try:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                raise ValueError(f"无法打开视频文件: {self.video_path}")
            
            # 获取视频基本信息
            self.video_info = {
                'total_frames': int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'fps': self.cap.get(cv2.CAP_PROP_FPS),
                'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'duration': 0  # 将在下面计算
            }
            
            # 计算视频时长（秒）
            if self.video_info['fps'] > 0:
                self.video_info['duration'] = self.video_info['total_frames'] / self.video_info['fps']
            
        except Exception as e:
            raise ValueError(f"视频加载失败: {str(e)}")
    
    def get_video_info(self) -> dict:
        """获取视频信息"""
        return self.video_info.copy()
    
    def frame_to_timestamp(self, frame_number: int) -> str:
        """
        将帧号转换为时间戳字符串
        
        Args:
            frame_number: 帧号
            
        Returns:
            格式为 HH-MM-SS-ms 的时间戳字符串
        """
        if self.video_info['fps'] <= 0:
            return "00-00-00-000"
        
        # 计算时间（秒）
        time_seconds = frame_number / self.video_info['fps']
        
        # 转换为时分秒毫秒
        hours = int(time_seconds // 3600)
        minutes = int((time_seconds % 3600) // 60)
        seconds = int(time_seconds % 60)
        milliseconds = int((time_seconds % 1) * 1000)
        
        return f"{hours:02d}-{minutes:02d}-{seconds:02d}-{milliseconds:03d}"
    
    def timestamp_to_frame(self, timestamp_str: str) -> int:
        """
        将时间戳字符串转换为帧号
        
        Args:
            timestamp_str: 格式为 HH:MM:SS 或 HH-MM-SS 的时间戳
            
        Returns:
            对应的帧号
        """
        # 处理不同的分隔符
        timestamp_str = timestamp_str.replace('-', ':')
        
        try:
            time_parts = timestamp_str.split(':')
            if len(time_parts) >= 3:
                hours = int(time_parts[0])
                minutes = int(time_parts[1])
                seconds = float(time_parts[2])  # 支持小数秒
                
                total_seconds = hours * 3600 + minutes * 60 + seconds
                frame_number = int(total_seconds * self.video_info['fps'])
                
                return min(frame_number, self.video_info['total_frames'] - 1)
        except (ValueError, IndexError):
            pass
        
        return 0
    
    def extract_frames(self, 
                      output_dir: str,
                      start_time: str = "00:00:00",
                      end_time: str = None,
                      frame_interval: int = 1,
                      progress_callback: Optional[Callable] = None,
                      use_threading: bool = True,
                      max_workers: Optional[int] = None,
                      output_format: str = 'webp',
                      quality: Optional[int] = None,
                      lossless: bool = True,
                      png_compress_level: int = 9,
                      backend: str = 'auto',
                      hwaccel: str = 'auto') -> dict:
        """
        提取视频帧
        
        Args:
            output_dir: 输出目录
            start_time: 开始时间 (HH:MM:SS)
            end_time: 结束时间 (HH:MM:SS)，None表示到视频结尾
            frame_interval: 帧间隔（每隔N帧提取一帧）
            progress_callback: 进度回调函数 callback(current, total, frame_path)
            
        Returns:
            提取结果统计信息
        """
        if not self.cap or not self.cap.isOpened():
            raise ValueError("视频未正确加载")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 计算开始和结束帧
        start_frame = self.timestamp_to_frame(start_time)
        if end_time:
            end_frame = self.timestamp_to_frame(end_time)
        else:
            end_frame = self.video_info['total_frames'] - 1
        
        # 确保帧范围有效
        start_frame = max(0, start_frame)
        end_frame = min(end_frame, self.video_info['total_frames'] - 1)
        
        if start_frame >= end_frame:
            raise ValueError("开始时间不能大于或等于结束时间")
        
        # 计算需要提取的帧数（先估算，准确进度由保存回调更新）
        total_frames_to_extract = len(range(start_frame, end_frame + 1, frame_interval))
        extracted_count = 0
        failed_count = 0

        # 后端选择：优先使用 FFmpeg + 硬件解码（若可用），否则使用 OpenCV
        chosen_backend = backend
        if backend == 'auto':
            chosen_backend = 'ffmpeg' if self._ffmpeg_available() else 'opencv'
        
        if chosen_backend == 'ffmpeg':
            return self._extract_frames_ffmpeg(
                output_dir=output_dir,
                start_time=start_time,
                end_time=end_time,
                frame_interval=frame_interval,
                progress_callback=progress_callback,
                output_format=output_format,
                quality=quality,
                lossless=lossless,
                png_compress_level=png_compress_level,
                start_frame=start_frame,
                end_frame=end_frame,
                total_frames_to_extract=total_frames_to_extract,
                hwaccel=hwaccel
            )
        
        # 设置视频位置到开始帧，之后顺序读取，避免频繁跳帧造成解码不稳定
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        start_extract_time = time.time()
        
        # 多线程池用于并行写盘，加速保存速度
        executor = None
        futures = []
        progress_counter = 0
        
        try:
            if use_threading:
                if max_workers is None:
                    # 保守并发：最多4线程，并尽量留出1个核心给系统，避免整机卡顿
                    cpu_count = (os.cpu_count() or 4)
                    max_workers = max(1, min(4, cpu_count - 1))
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
            
            current_frame_num = start_frame
            while current_frame_num <= end_frame:
                ret, frame = self.cap.read()
                if not ret:
                    # 读取失败，尝试继续下一帧
                    failed_count += 1
                    current_frame_num += 1
                    continue
                
                if (current_frame_num - start_frame) % max(1, frame_interval) == 0:
                    # 生成文件名（按所选格式扩展名）
                    timestamp = self.frame_to_timestamp(current_frame_num)
                    ext = (output_format or 'png').lower()
                    filename = f"{timestamp}.{ext}"
                    filepath = os.path.join(output_dir, filename)
                    
                    def save_and_report(path, img_bgr):
                        ok = False
                        try:
                            # 转为 PIL 图像
                            pil_img = opencv_to_pil(img_bgr)
                            if ext == 'png':
                                lvl = max(0, min(9, int(png_compress_level)))
                                pil_img.save(path, format='PNG', optimize=True, compress_level=lvl)
                            elif ext in ('jpg', 'jpeg'):
                                q = max(1, min(100, int(quality or 95)))
                                pil_img.save(path, format='JPEG', quality=q, subsampling=0, optimize=True)
                            elif ext == 'webp':
                                # WebP 可选无损；降低 method 以减少CPU占用，减轻系统卡顿
                                q = max(1, min(100, int(quality or (100 if lossless else 95))))
                                pil_img.save(path, format='WEBP', quality=q, lossless=bool(lossless), method=4)
                            else:
                                # 未知格式，回退为PNG
                                pil_img.save(path, format='PNG', optimize=True, compress_level=9)
                            ok = True
                        except Exception as e:
                            print(f"保存帧失败 {os.path.basename(path)}: {str(e)}")
                        return ok, path
                    
                    if executor:
                        future = executor.submit(save_and_report, filepath, frame.copy())
                        futures.append(future)
                    else:
                        ok, p = save_and_report(filepath, frame)
                        if ok:
                            extracted_count += 1
                            progress_counter += 1
                            if progress_callback:
                                progress_callback(progress_counter, total_frames_to_extract, p)
                        else:
                            failed_count += 1
                
                current_frame_num += 1
            
            # 处理并行保存完成的结果
            for future in futures:
                try:
                    ok, p = future.result()
                    if ok:
                        extracted_count += 1
                    else:
                        failed_count += 1
                    progress_counter += 1
                    if progress_callback:
                        progress_callback(progress_counter, total_frames_to_extract, p)
                except Exception as e:
                    failed_count += 1
            
        except Exception as e:
            raise RuntimeError(f"帧提取过程中发生错误: {str(e)}")
        finally:
            if executor:
                executor.shutdown(wait=True)
        
        # 计算提取时间
        extract_duration = time.time() - start_extract_time
        
        return {
            'total_frames_to_extract': total_frames_to_extract,
            'extracted_count': extracted_count,
            'failed_count': failed_count,
            'output_directory': output_dir,
            'extract_duration': extract_duration,
            'start_frame': start_frame,
            'end_frame': end_frame,
            'frame_interval': frame_interval
        }

    @staticmethod
    def _ffmpeg_available() -> bool:
        return shutil.which('ffmpeg') is not None

    def _extract_frames_ffmpeg(self,
                               output_dir: str,
                               start_time: str,
                               end_time: Optional[str],
                               frame_interval: int,
                               progress_callback: Optional[Callable],
                               output_format: str,
                               quality: Optional[int],
                               lossless: bool,
                               png_compress_level: int,
                               start_frame: int,
                               end_frame: int,
                               total_frames_to_extract: int,
                               hwaccel: str) -> dict:
        if not self._ffmpeg_available():
            raise RuntimeError("未检测到 ffmpeg，请安装后重试或使用 OpenCV 后端。")
        
        ext = (output_format or 'webp').lower()
        tmp_dir = os.path.join(output_dir, "_ffmpeg_tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        pattern = os.path.join(tmp_dir, "%010d." + ext)
        
        # 构建 ffmpeg 命令
        cmd = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error',
        ]
        # 硬件解码选择
        if hwaccel and hwaccel != 'auto':
            cmd += ['-hwaccel', hwaccel]
        else:
            # Windows 上优先尝试 dxva2（更通用），否则让 ffmpeg 自动选择
            cmd += ['-hwaccel', 'auto']
        
        # 起止时间
        if start_time:
            cmd += ['-ss', start_time]
        if end_time:
            cmd += ['-to', end_time]
        
        cmd += ['-i', self.video_path]
        
        # 帧选择：每隔 N 帧提取一帧
        select_filter = f"select=not(mod(n\\,{max(1, frame_interval)}))"
        vf = [select_filter]
        
        cmd += ['-vf', ','.join(vf), '-vsync', 'vfr']
        
        # 输出编码设置
        if ext == 'png':
            cmd += ['-c:v', 'png', '-compression_level', str(max(0, min(9, int(png_compress_level))))]
        elif ext in ('jpg', 'jpeg'):
            q = max(2, min(31, int(quality or 2)))  # mjpeg 的 q 值越小越高质，2≈高质量
            cmd += ['-c:v', 'mjpeg', '-q:v', str(q)]
        elif ext == 'webp':
            cmd += ['-c:v', 'libwebp']
            if lossless:
                cmd += ['-lossless', '1']
                # 适度压缩强度，降低CPU
                cmd += ['-compression_level', '4']
                cmd += ['-q:v', str(int(quality or 100))]
            else:
                cmd += ['-lossless', '0']
                cmd += ['-compression_level', '4']
                cmd += ['-q:v', str(max(1, min(100, int(quality or 95))))]
        else:
            # 回退为PNG
            cmd += ['-c:v', 'png', '-compression_level', '9']
        
        # 起始编号，从起始帧号开始编号，便于后续按帧号重命名为时间戳
        cmd += ['-start_number', str(start_frame)]
        
        # 输出模式与路径
        cmd += ['-y', '-f', 'image2', pattern]
        
        start_time_extract = time.time()
        
        # 运行 ffmpeg
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            err = proc.stderr.decode(errors='ignore')
            raise RuntimeError(f"FFmpeg 提取失败: {err}")
        
        # 统计与重命名
        files = sorted([f for f in os.listdir(tmp_dir) if f.lower().endswith('.' + ext)])
        extracted_count = 0
        failed_count = 0
        progress_counter = 0
        for fname in files:
            try:
                index = int(os.path.splitext(fname)[0])
                timestamp = self.frame_to_timestamp(index)
                new_name = f"{timestamp}.{ext}"
                src = os.path.join(tmp_dir, fname)
                dst = os.path.join(output_dir, new_name)
                os.replace(src, dst)
                extracted_count += 1
                progress_counter += 1
                if progress_callback:
                    progress_callback(progress_counter, total_frames_to_extract, dst)
            except Exception:
                failed_count += 1
        
        # 清理临时目录
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
        
        extract_duration = time.time() - start_time_extract
        return {
            'total_frames_to_extract': total_frames_to_extract,
            'extracted_count': extracted_count,
            'failed_count': failed_count,
            'output_directory': output_dir,
            'extract_duration': extract_duration,
            'start_frame': start_frame,
            'end_frame': end_frame,
            'frame_interval': frame_interval
        }
    
    def get_frame_at_time(self, timestamp: str) -> Optional[np.ndarray]:
        """
        获取指定时间的帧
        
        Args:
            timestamp: 时间戳 (HH:MM:SS)
            
        Returns:
            帧图像数组，失败返回None
        """
        if not self.cap or not self.cap.isOpened():
            return None

        frame_num = self.timestamp_to_frame(timestamp)
        with self._cap_lock:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = self.cap.read()
        return frame if ret else None
    
    def get_frame_at_position(self, frame_number: int) -> Optional[np.ndarray]:
        """
        获取指定帧号的帧
        
        Args:
            frame_number: 帧号
            
        Returns:
            帧图像数组，失败返回None
        """
        if not self.cap or not self.cap.isOpened():
            return None
        
        if frame_number < 0 or frame_number >= self.video_info['total_frames']:
            return None
        
        with self._cap_lock:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = self.cap.read()
        return frame if ret else None

    def get_frame_at_seconds_fast(self, seconds: float) -> Optional[np.ndarray]:
        """按秒快速获取预览帧，针对小幅度前进拖动优化。

        原理：
        - 小范围前进（<= ~2 秒）优先用 grab 前进到目标帧后再 read，一次只解码最终帧；
        - 大范围跳转或后退则直接 seek 到目标帧再 read；
        - 所有读取都加锁，避免与其他线程冲突。

        该方法用于预览线程，提升连续拖动的跟手性。
        """
        if not self.cap or not self.cap.isOpened():
            return None

        fps = self.video_info.get('fps', 0) or 25.0
        target_frame = int(max(0.0, seconds) * fps)

        with self._cap_lock:
            try:
                current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            except Exception:
                current_frame = target_frame

            diff = target_frame - current_frame
            # 阈值：2 秒内的前进，尝试使用 grab 优化
            threshold = int(max(1.0, fps * 2.0))

            if diff > 0 and diff <= threshold:
                # 前进到目标位置：先抓取到倒数第二帧，再 read 最后一帧
                steps = max(0, diff - 1)
                for _ in range(steps):
                    self.cap.grab()
                ret, frame = self.cap.read()
                return frame if ret else None
            else:
                # 大幅跳转或后退：直接定位
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                ret, frame = self.cap.read()
                return frame if ret else None
    
    def close(self):
        """关闭视频文件"""
        if self.cap:
            self.cap.release()
            self.cap = None
    
    def __del__(self):
        """析构函数"""
        self.close()


def create_output_directory(video_path: str, base_dir: str = None) -> str:
    """
    创建输出目录
    
    Args:
        video_path: 视频文件路径
        base_dir: 基础目录，默认为当前目录
        
    Returns:
        创建的输出目录路径
    """
    if base_dir is None:
        base_dir = os.getcwd()
    
    # 获取视频文件名（不含扩展名）
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # 创建输出目录
    output_dir = os.path.join(base_dir, video_name)
    os.makedirs(output_dir, exist_ok=True)
    
    return output_dir


def format_duration(seconds: float) -> str:
    """
    格式化时长显示
    
    Args:
        seconds: 秒数
        
    Returns:
        格式化的时长字符串
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def validate_time_format(time_str: str) -> bool:
    """
    验证时间格式是否正确
    
    Args:
        time_str: 时间字符串
        
    Returns:
        是否为有效格式
    """
    try:
        # 支持 HH:MM:SS 和 HH-MM-SS 格式
        time_str = time_str.replace('-', ':')
        parts = time_str.split(':')
        
        if len(parts) != 3:
            return False
        
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        
        return (0 <= hours <= 23 and 
                0 <= minutes <= 59 and 
                0 <= seconds < 60)
    except (ValueError, IndexError):
        return False
