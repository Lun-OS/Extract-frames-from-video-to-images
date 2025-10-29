"""
视频帧提取工具 - GUI界面
提供完整的图形用户界面，包括视频选择、参数设置、预览功能等
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import time
from typing import Optional
import cv2
from PIL import Image, ImageTk

from video_processor import VideoProcessor, create_output_directory, format_duration
from utils import (
    is_video_file, get_file_size_mb, create_thumbnail, opencv_to_pil,
    resize_image_for_display, save_project_config, load_project_config,
    add_recent_file, clean_output_directory, get_directory_info,
    validate_output_path, get_available_space_gb, estimate_output_size,
    center_window, get_supported_video_formats
)


class VideoFrameExtractorGUI:
    """视频帧提取工具GUI类"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("视频帧提取工具 v1.0")
        self.root.geometry("1000x940")
        
        # 应用程序状态
        self.video_processor: Optional[VideoProcessor] = None
        self.current_video_path = ""
        self.output_directory = ""
        self.is_extracting = False
        self.extraction_thread = None
        self.large_file_warned = False

        # 预览后台线程状态
        self.preview_target_seconds = 0.0
        self.preview_worker = None
        self.preview_worker_stop = threading.Event()
        
        # 加载配置
        self.config = load_project_config()
        
        # 创建界面
        self.create_widgets()
        self.setup_layout()
        self.bind_events()
        
        # 恢复窗口位置
        if 'window_geometry' in self.config:
            try:
                self.root.geometry(self.config['window_geometry'])
            except:
                center_window(self.root, 1000, 940)
        else:
            center_window(self.root, 1000, 940)
    
    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        self.main_frame = ttk.Frame(self.root, padding="10")
        
        # 视频选择区域
        self.video_frame = ttk.LabelFrame(self.main_frame, text="视频文件", padding="10")
        
        self.video_path_var = tk.StringVar(value=self.config.get('last_video_path', ''))
        self.video_path_entry = ttk.Entry(self.video_frame, textvariable=self.video_path_var, width=60)
        self.browse_button = ttk.Button(self.video_frame, text="浏览", command=self.browse_video)
        
        # 视频信息显示
        self.video_info_frame = ttk.Frame(self.video_frame)
        self.video_info_text = tk.Text(self.video_info_frame, height=4, width=50, state='disabled')
        self.video_info_scroll = ttk.Scrollbar(self.video_info_frame, orient="vertical", command=self.video_info_text.yview)
        self.video_info_text.configure(yscrollcommand=self.video_info_scroll.set)
        
        # 参数设置区域
        self.params_frame = ttk.LabelFrame(self.main_frame, text="提取参数", padding="10")
        
        # 时间范围设置（增加拖动条）
        self.time_frame = ttk.Frame(self.params_frame)
        self.duration_seconds = 0
        
        # 开始时间 - 拖动条 + 文本显示
        ttk.Label(self.time_frame, text="开始时间:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.start_time_var = tk.StringVar(value=self.config.get('default_start_time', '00:00:00'))
        self.start_scale = ttk.Scale(self.time_frame, from_=0, to=1, orient='horizontal', command=self.on_start_scale_changed)
        self.start_scale.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self.start_time_label = ttk.Label(self.time_frame, textvariable=self.start_time_var, width=10)
        self.start_time_label.grid(row=0, column=2, padx=(0, 10))
        
        # 结束时间 - 拖动条 + 文本显示
        ttk.Label(self.time_frame, text="结束时间:").grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.end_time_var = tk.StringVar(value="")
        self.end_scale = ttk.Scale(self.time_frame, from_=0, to=1, orient='horizontal', command=self.on_end_scale_changed)
        self.end_scale.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        self.end_time_label = ttk.Label(self.time_frame, textvariable=self.end_time_var, width=10)
        self.end_time_label.grid(row=1, column=2, padx=(0, 10))
        ttk.Label(self.time_frame, text="(为空表示到结尾)", font=("", 8)).grid(row=1, column=3, sticky="w")
        
        # 允许直接输入（可选）：仍保留原始输入框，便于精确控制
        self.start_time_entry = ttk.Entry(self.time_frame, textvariable=self.start_time_var, width=12)
        self.end_time_entry = ttk.Entry(self.time_frame, textvariable=self.end_time_var, width=12)
        # 不默认显示输入框，后续可在需要时显示
        
        # 帧间隔设置（拖动条 + 选择）
        self.interval_frame = ttk.Frame(self.params_frame)
        ttk.Label(self.interval_frame, text="帧间隔:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.frame_interval_var = tk.IntVar(value=int(self.config.get('default_frame_interval', 1)))
        # 拖动条（1-300）
        self.interval_scale = ttk.Scale(self.interval_frame, from_=1, to=300, orient='horizontal', command=self.on_interval_scale_changed)
        self.interval_scale.set(self.frame_interval_var.get())
        self.interval_scale.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        # 选择框（Spinbox）
        self.frame_interval_spin = tk.Spinbox(self.interval_frame, from_=1, to=1000, width=7, command=self.on_interval_spin_changed)
        self.frame_interval_spin.delete(0, tk.END)
        self.frame_interval_spin.insert(0, str(self.frame_interval_var.get()))
        self.frame_interval_spin.grid(row=0, column=2, padx=(0, 10))
        ttk.Label(self.interval_frame, text="(每隔N帧提取一帧)", font=("", 8)).grid(row=0, column=3, sticky="w")
        
        # 输出目录设置
        self.output_frame = ttk.Frame(self.params_frame)
        ttk.Label(self.output_frame, text="输出目录:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.output_dir_var = tk.StringVar(value=self.config.get('last_output_dir', ''))
        self.output_dir_entry = ttk.Entry(self.output_frame, textvariable=self.output_dir_var, width=40)
        self.output_dir_entry.grid(row=0, column=1, padx=(0, 10))
        self.output_browse_button = ttk.Button(self.output_frame, text="浏览", command=self.browse_output_dir)
        self.output_browse_button.grid(row=0, column=2)

        # 输出格式选择
        ttk.Label(self.output_frame, text="输出格式:").grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(8, 0))
        self.output_format_var = tk.StringVar(value=self.config.get('default_output_format', 'webp'))
        self.output_format_display_map = {
            'png': 'PNG（快速/占用大）',
            'webp': 'WebP（较慢/占用小）',
            'jpeg': 'JPEG（极快/有损）'
        }
        self.output_format_reverse_map = {v: k for k, v in self.output_format_display_map.items()}
        initial_display = self.output_format_display_map.get(self.output_format_var.get(), 'WebP（较慢/占用小）')
        self.output_format_display_var = tk.StringVar(value=initial_display)
        self.output_format_combo = ttk.Combobox(
            self.output_frame,
            state='readonly',
            values=list(self.output_format_display_map.values()),
            textvariable=self.output_format_display_var,
            width=20
        )
        self.output_format_combo.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=(8, 0))
        ttk.Label(self.output_frame, text="说明: PNG体积大但快速；WebP体积小但较慢；JPEG非常快但有损。", font=("", 8)).grid(row=1, column=2, sticky="w", pady=(8, 0))
        
        # 预览区域
        self.preview_frame = ttk.LabelFrame(self.main_frame, text="预览", padding="10")
        
        # 预览控制（拖动条）
        self.preview_control_frame = ttk.Frame(self.preview_frame)
        self.preview_time_var = tk.StringVar(value="00:00:00")
        ttk.Label(self.preview_control_frame, text="预览时间:").pack(side='left', padx=(0, 5))
        self.preview_scale = ttk.Scale(self.preview_control_frame, from_=0, to=1, orient='horizontal', command=self.on_preview_scale_changed)
        self.preview_scale.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.preview_time_label = ttk.Label(self.preview_control_frame, textvariable=self.preview_time_var, width=10)
        self.preview_time_label.pack(side='left')
        self.preview_update_job = None  # 保留但不再用于密集取帧
        
        # 预览图像显示
        self.preview_canvas = tk.Canvas(self.preview_frame, width=400, height=300, bg='gray90')
        self.preview_image_id = None
        
        # 控制按钮区域
        self.control_frame = ttk.Frame(self.main_frame)
        self.extract_button = ttk.Button(self.control_frame, text="开始提取", command=self.start_extraction)
        self.pause_button = ttk.Button(self.control_frame, text="暂停", command=self.pause_extraction, state='disabled')
        self.stop_button = ttk.Button(self.control_frame, text="停止", command=self.stop_extraction, state='disabled')
        self.clear_button = ttk.Button(self.control_frame, text="清理输出", command=self.clear_output)
        
        # 进度显示区域
        self.progress_frame = ttk.LabelFrame(self.main_frame, text="进度信息", padding="10")
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.progress_frame, variable=self.progress_var, maximum=100)
        
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(self.progress_frame, textvariable=self.status_var)
        
        self.progress_text = tk.Text(self.progress_frame, height=6, width=80, state='disabled')
        self.progress_scroll = ttk.Scrollbar(self.progress_frame, orient="vertical", command=self.progress_text.yview)
        self.progress_text.configure(yscrollcommand=self.progress_scroll.set)
        
        # 最近文件菜单
        self.create_menu()
    
    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开视频", command=self.browse_video)
        file_menu.add_separator()
        
        # 最近文件子菜单
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="最近文件", menu=self.recent_menu)
        self.update_recent_menu()
        
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.on_closing)
        
        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self.show_about)
    
    def setup_layout(self):
        """设置布局"""
        self.main_frame.pack(fill='both', expand=True)
        
        # 视频选择区域布局
        self.video_frame.pack(fill='x', pady=(0, 10))
        
        video_input_frame = ttk.Frame(self.video_frame)
        video_input_frame.pack(fill='x', pady=(0, 10))
        self.video_path_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.browse_button.pack(side='right')
        
        self.video_info_frame.pack(fill='x')
        self.video_info_text.pack(side='left', fill='both', expand=True)
        self.video_info_scroll.pack(side='right', fill='y')
        
        # 参数设置区域布局
        self.params_frame.pack(fill='x', pady=(0, 10))
        self.time_frame.pack(fill='x', pady=(0, 10))
        self.interval_frame.pack(fill='x', pady=(0, 10))
        self.output_frame.pack(fill='x')
        
        # 预览区域布局
        self.preview_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self.preview_control_frame.pack(fill='x', pady=(0, 10))
        # 取消旧的预览按钮和输入框布局
        
        self.preview_canvas.pack(fill='both', expand=True)
        
        # 控制按钮布局
        self.control_frame.pack(fill='x', pady=(0, 10))
        self.extract_button.pack(side='left', padx=(0, 10))
        self.pause_button.pack(side='left', padx=(0, 10))
        self.stop_button.pack(side='left', padx=(0, 10))
        self.clear_button.pack(side='right')
        
        # 进度显示布局
        self.progress_frame.pack(fill='x')
        self.status_label.pack(fill='x', pady=(0, 5))
        self.progress_bar.pack(fill='x', pady=(0, 10))
        
        progress_text_frame = ttk.Frame(self.progress_frame)
        progress_text_frame.pack(fill='x')
        self.progress_text.pack(side='left', fill='both', expand=True)
        self.progress_scroll.pack(side='right', fill='y')
    
    def bind_events(self):
        """绑定事件"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.video_path_var.trace('w', self.on_video_path_changed)
        self.output_dir_var.trace('w', self.on_output_dir_changed)
        # 手动输入与拖动条联动
        self.start_time_var.trace('w', lambda *args: self.sync_scale_with_entry('start'))
        self.end_time_var.trace('w', lambda *args: self.sync_scale_with_entry('end'))
    
    def browse_video(self):
        """浏览选择视频文件"""
        filetypes = [
            ("视频文件", " ".join(f"*{ext}" for ext in get_supported_video_formats())),
            ("所有文件", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=filetypes,
            initialdir=os.path.dirname(self.video_path_var.get()) if self.video_path_var.get() else ""
        )
        
        if filename:
            self.video_path_var.set(filename)
            add_recent_file(filename)
            self.update_recent_menu()
    
    def browse_output_dir(self):
        """浏览选择输出目录"""
        directory = filedialog.askdirectory(
            title="选择输出目录",
            initialdir=self.output_dir_var.get() if self.output_dir_var.get() else ""
        )
        
        if directory:
            self.output_dir_var.set(directory)
    
    def on_video_path_changed(self, *args):
        """视频路径改变事件"""
        video_path = self.video_path_var.get()
        
        if video_path and os.path.isfile(video_path) and is_video_file(video_path):
            self.load_video(video_path)
            
            # 自动设置输出目录
            if not self.output_dir_var.get():
                output_dir = create_output_directory(video_path)
                self.output_dir_var.set(output_dir)
        else:
            self.clear_video_info()
    
    def on_output_dir_changed(self, *args):
        """输出目录改变事件"""
        self.update_output_info()
    
    def load_video(self, video_path: str):
        """加载视频文件"""
        try:
            if self.video_processor:
                self.video_processor.close()
            # 停止旧的预览线程
            self.stop_preview_worker()
            
            self.video_processor = VideoProcessor(video_path)
            self.current_video_path = video_path
            
            # 显示视频信息
            self.display_video_info()
            
            # 设置时长和各拖动条范围
            duration = self.video_processor.video_info['duration']
            self.duration_seconds = duration
            self.configure_time_scales(duration)
            # 结束时间默认到结尾
            self.end_time_var.set(self.seconds_to_hms(duration))
            # 预览条默认 00:00:00
            self.preview_time_var.set("00:00:00")
            self.preview_scale.set(0)
            self.preview_target_seconds = 0.0
            # 启动预览后台线程
            self.start_preview_worker()
            
            self.log_message(f"视频加载成功: {os.path.basename(video_path)}")
            
        except Exception as e:
            self.log_message(f"视频加载失败: {str(e)}", "error")
            messagebox.showerror("错误", f"无法加载视频文件:\n{str(e)}")

    def configure_time_scales(self, duration: float):
        """配置开始/结束/预览拖动条范围"""
        # 统一设置到秒级范围
        for scale in (self.start_scale, self.end_scale, self.preview_scale):
            scale.configure(from_=0, to=max(duration, 1), value=0)
        # 初始值
        self.start_scale.set(0)
        self.end_scale.set(duration)

    @staticmethod
    def seconds_to_hms(seconds: float) -> str:
        seconds = max(0, float(seconds))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @staticmethod
    def seconds_to_hms_precise(seconds: float) -> str:
        """将秒转换为 HH:MM:SS.mmm，保留毫秒以避免终点截断。"""
        seconds = max(0, float(seconds))
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs_int = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        # 处理进位
        if ms == 1000:
            ms = 0
            secs_int += 1
            if secs_int == 60:
                secs_int = 0
                minutes += 1
                if minutes == 60:
                    minutes = 0
                    hours += 1
        return f"{hours:02d}:{minutes:02d}:{secs_int:02d}.{ms:03d}"

    def on_start_scale_changed(self, value):
        try:
            seconds = float(value)
            # 不超过结束时间
            end_seconds = self.end_scale.get()
            if seconds > end_seconds:
                seconds = end_seconds
                self.start_scale.set(seconds)
            self.start_time_var.set(self.seconds_to_hms(seconds))
        except Exception:
            pass

    def on_end_scale_changed(self, value):
        try:
            seconds = float(value)
            # 不小于开始时间
            start_seconds = self.start_scale.get()
            if seconds < start_seconds:
                seconds = start_seconds
                self.end_scale.set(seconds)
            self.end_time_var.set(self.seconds_to_hms(seconds))
        except Exception:
            pass

    def on_interval_scale_changed(self, value):
        try:
            iv = max(1, int(float(value)))
            self.frame_interval_var.set(iv)
            # 同步到 Spinbox
            self.frame_interval_spin.delete(0, tk.END)
            self.frame_interval_spin.insert(0, str(iv))
        except Exception:
            pass

    def on_interval_spin_changed(self):
        try:
            iv = max(1, int(self.frame_interval_spin.get()))
            self.frame_interval_var.set(iv)
            self.interval_scale.set(iv)
        except Exception:
            pass

    def on_preview_scale_changed(self, value):
        try:
            seconds = float(value)
            self.preview_time_var.set(self.seconds_to_hms(seconds))
            # 仅更新目标秒数，由后台线程拉取帧；避免阻塞UI线程
            self.preview_target_seconds = seconds
        except Exception:
            pass

    def sync_scale_with_entry(self, which: str):
        """当手动输入时间时，同步拖动条位置"""
        try:
            time_str = self.start_time_var.get() if which == 'start' else self.end_time_var.get()
            # 转为秒
            secs = self.hms_to_seconds(time_str)
            if secs is None:
                return
            if which == 'start':
                self.start_scale.set(secs)
            else:
                self.end_scale.set(secs)
        except Exception:
            pass

    @staticmethod
    def hms_to_seconds(hms: str) -> Optional[float]:
        try:
            parts = hms.replace('-', ':').split(':')
            if len(parts) != 3:
                return None
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            return float(h * 3600 + m * 60 + s)
        except Exception:
            return None
    
    def display_video_info(self):
        """显示视频信息"""
        if not self.video_processor:
            return
        
        info = self.video_processor.get_video_info()
        file_size = get_file_size_mb(self.current_video_path)
        
        info_text = f"""文件: {os.path.basename(self.current_video_path)}
大小: {file_size:.1f} MB
分辨率: {info['width']} x {info['height']}
帧率: {info['fps']:.2f} fps
总帧数: {info['total_frames']}
时长: {format_duration(info['duration'])}"""
        
        self.video_info_text.config(state='normal')
        self.video_info_text.delete(1.0, tk.END)
        self.video_info_text.insert(1.0, info_text)
        self.video_info_text.config(state='disabled')
    
    def clear_video_info(self):
        """清空视频信息"""
        self.video_info_text.config(state='normal')
        self.video_info_text.delete(1.0, tk.END)
        self.video_info_text.config(state='disabled')
        
        if self.video_processor:
            self.video_processor.close()
            self.video_processor = None
        
        self.current_video_path = ""
    
    def update_output_info(self):
        """更新输出信息"""
        output_dir = self.output_dir_var.get()
        if not output_dir:
            return
        
        dir_info = get_directory_info(output_dir)
        if dir_info['exists'] and dir_info['file_count'] > 0:
            self.log_message(f"输出目录已存在 {dir_info['file_count']} 个文件")
    
    def preview_frame_at_time(self):
        """预览指定时间的帧"""
        if not self.video_processor:
            messagebox.showwarning("警告", "请先选择视频文件")
            return
        
        time_str = self.preview_time_var.get()
        try:
            frame = self.video_processor.get_frame_at_time(time_str)
            if frame is not None:
                self.display_preview_frame(frame)
            else:
                messagebox.showwarning("警告", "无法获取指定时间的帧")
        except Exception as e:
            messagebox.showerror("错误", f"预览失败: {str(e)}")

    def preview_frame_at_time_seconds(self, seconds: float):
        """按秒预览（供拖动条节流调用）"""
        # 改为由后台线程处理，此方法不再主动读取帧
        try:
            self.preview_target_seconds = float(seconds)
        except Exception:
            pass
    
    def display_preview_frame(self, frame):
        """显示预览帧"""
        try:
            # 调整图像大小适应画布
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                resized_frame = resize_image_for_display(frame, canvas_width, canvas_height)
                
                # 转换为PIL图像
                pil_image = opencv_to_pil(resized_frame)
                photo = ImageTk.PhotoImage(pil_image)
                
                # 在画布中央显示
                self.preview_canvas.delete("all")
                x = canvas_width // 2
                y = canvas_height // 2
                self.preview_image_id = self.preview_canvas.create_image(x, y, image=photo)
                
                # 保持引用防止被垃圾回收
                self.preview_canvas.image = photo
                
        except Exception as e:
            self.log_message(f"预览显示失败: {str(e)}", "error")
    
    def start_extraction(self):
        """开始提取帧"""
        if self.is_extracting:
            return
        
        # 验证输入
        if not self.validate_inputs():
            return
        
        # 准备提取参数
        try:
            # 优先使用拖动条的值
            start_secs = self.start_scale.get()
            end_secs = self.end_scale.get()
            start_time = self.seconds_to_hms_precise(start_secs)
            end_time = self.seconds_to_hms_precise(end_secs)
            frame_interval = int(self.frame_interval_var.get())
            output_dir = self.output_dir_var.get()
            output_format = self.get_selected_output_format()
            
            # 检查输出目录
            valid, error_msg = validate_output_path(output_dir)
            if not valid:
                messagebox.showerror("错误", f"输出路径无效: {error_msg}")
                return
            
            # 检查磁盘空间
            if self.video_processor:
                info = self.video_processor.get_video_info()
                estimated_size = estimate_output_size(
                    max(1, info['total_frames'] // max(1, frame_interval)),
                    info['width'],
                    info['height']
                )
                format_scale = {
                    'png': 1.0,
                    'webp': 0.4,
                    'jpeg': 0.25,
                    'jpg': 0.25
                }.get(output_format, 1.0)
                estimated_size *= format_scale
                available_space = get_available_space_gb(output_dir) * 1024  # 转换为MB
                
                if estimated_size > available_space * 0.9:  # 保留10%空间
                    if not messagebox.askyesno("警告", 
                        f"估算输出大小: {estimated_size:.1f} MB\n"
                        f"可用空间: {available_space:.1f} MB\n"
                        f"按当前输出格式（{output_format.upper()}）估算，空间可能不足，是否继续？"):
                        return
            
            # 开始提取
            self.is_extracting = True
            self.update_ui_state()
            # 提取期间暂停预览，降低CPU竞争
            self.stop_preview_worker()
            
            self.extraction_thread = threading.Thread(
                target=self.extraction_worker,
                args=(start_time, end_time, frame_interval, output_dir, output_format),
                daemon=True
            )
            self.extraction_thread.start()
            
        except ValueError as e:
            messagebox.showerror("错误", f"参数错误: {str(e)}")
        except Exception as e:
            messagebox.showerror("错误", f"启动提取失败: {str(e)}")
    
    def extraction_worker(self, start_time: str, end_time: Optional[str], frame_interval: int, output_dir: str, output_format: str):
        """提取工作线程"""
        try:
            def progress_callback(current, total, frame_path):
                if not self.is_extracting:
                    return
                
                progress = (current / total) * 100
                self.root.after(0, lambda: self.update_progress(progress, current, total, frame_path))
            
            self.log_message("开始提取帧...")
            start_time_extract = time.time()
            
            result = self.video_processor.extract_frames(
                output_dir=output_dir,
                start_time=start_time,
                end_time=end_time,
                frame_interval=frame_interval,
                progress_callback=progress_callback,
                use_threading=True,
                output_format=output_format
            )
            
            if self.is_extracting:  # 检查是否被停止
                extract_duration = time.time() - start_time_extract
                self.root.after(0, lambda: self.extraction_completed(result, extract_duration))
            
        except Exception as e:
            self.root.after(0, lambda: self.extraction_failed(str(e)))
    
    def update_progress(self, progress: float, current: int, total: int, frame_path: str):
        """更新进度显示"""
        self.progress_var.set(progress)
        self.status_var.set(f"正在提取: {current}/{total} ({progress:.1f}%)")
        
        filename = os.path.basename(frame_path)
        self.log_message(f"已提取: {filename}")
        if not self.large_file_warned:
            try:
                size_mb = get_file_size_mb(frame_path)
                ext = os.path.splitext(filename)[1].lower().lstrip('.')
                threshold_map = {
                    'png': 10.0,
                    'webp': 6.0,
                    'jpg': 6.0,
                    'jpeg': 6.0
                }
                threshold = threshold_map.get(ext, 10.0)
                if size_mb >= threshold:
                    self.large_file_warned = True
                    messagebox.showwarning(
                        "文件过大警告",
                        f"检测到单张文件较大: {filename}\n大小约 {size_mb:.1f} MB\n格式: {ext.upper()}\n建议：降低压缩强度或改用 WebP/JPEG，以减少占用。"
                    )
            except Exception:
                pass
    
    def extraction_completed(self, result: dict, extract_duration: float):
        """提取完成"""
        self.is_extracting = False
        self.update_ui_state()
        
        self.progress_var.set(100)
        self.status_var.set("提取完成")
        
        success_msg = f"""提取完成！
总计划提取: {result['total_frames_to_extract']} 帧
成功提取: {result['extracted_count']} 帧
失败: {result['failed_count']} 帧
输出目录: {result['output_directory']}
耗时: {extract_duration:.1f} 秒"""
        
        self.log_message(success_msg)
        messagebox.showinfo("完成", success_msg)
        
        # 保存配置
        self.save_current_config()
        # 重新启动预览线程
        self.start_preview_worker()
    
    def extraction_failed(self, error_msg: str):
        """提取失败"""
        self.is_extracting = False
        self.update_ui_state()
        
        self.status_var.set("提取失败")
        self.log_message(f"提取失败: {error_msg}", "error")
        messagebox.showerror("错误", f"提取失败:\n{error_msg}")
        # 恢复预览线程
        self.start_preview_worker()
    
    def pause_extraction(self):
        """暂停提取（暂未实现）"""
        messagebox.showinfo("提示", "暂停功能将在后续版本中实现")
    
    def stop_extraction(self):
        """停止提取"""
        if self.is_extracting:
            self.is_extracting = False
            self.status_var.set("正在停止...")
            self.log_message("用户停止了提取操作")
    
    def clear_output(self):
        """清理输出目录"""
        output_dir = self.output_dir_var.get()
        if not output_dir or not os.path.exists(output_dir):
            messagebox.showwarning("警告", "输出目录不存在")
            return
        
        def confirm_callback(message):
            return messagebox.askyesno("确认", message)
        
        if clean_output_directory(output_dir, confirm_callback):
            self.log_message("输出目录已清理")
            messagebox.showinfo("完成", "输出目录已清理")
        else:
            self.log_message("清理操作已取消")
    
    def validate_inputs(self) -> bool:
        """验证输入参数"""
        if not self.video_processor:
            messagebox.showerror("错误", "请先选择视频文件")
            return False
        
        try:
            frame_interval = int(self.frame_interval_var.get())
            if frame_interval < 1:
                raise ValueError("帧间隔必须大于0")
        except ValueError:
            messagebox.showerror("错误", "帧间隔必须是正整数")
            return False

        # 保证开始时间不大于结束时间
        if self.duration_seconds:
            if self.start_scale.get() > self.end_scale.get():
                messagebox.showerror("错误", "开始时间不能大于结束时间")
                return False
        
        if not self.output_dir_var.get():
            messagebox.showerror("错误", "请设置输出目录")
            return False
        
        return True
    
    def update_ui_state(self):
        """更新UI状态"""
        if self.is_extracting:
            self.extract_button.config(state='disabled')
            self.pause_button.config(state='normal')
            self.stop_button.config(state='normal')
        else:
            self.extract_button.config(state='normal')
            self.pause_button.config(state='disabled')
            self.stop_button.config(state='disabled')
    
    def log_message(self, message: str, level: str = "info"):
        """记录日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.progress_text.config(state='normal')
        self.progress_text.insert(tk.END, log_entry)
        self.progress_text.see(tk.END)
        self.progress_text.config(state='disabled')
    
    def update_recent_menu(self):
        """更新最近文件菜单"""
        self.recent_menu.delete(0, tk.END)
        
        recent_files = self.config.get('recent_files', [])
        if not recent_files:
            self.recent_menu.add_command(label="(无最近文件)", state='disabled')
            return
        
        for file_path in recent_files[:10]:  # 最多显示10个
            if os.path.exists(file_path):
                filename = os.path.basename(file_path)
                self.recent_menu.add_command(
                    label=filename,
                    command=lambda path=file_path: self.open_recent_file(path)
                )
    
    def open_recent_file(self, file_path: str):
        """打开最近文件"""
        if os.path.exists(file_path):
            self.video_path_var.set(file_path)
        else:
            messagebox.showerror("错误", f"文件不存在: {file_path}")
    
    def save_current_config(self):
        """保存当前配置"""
        # 兼容 IntVar 与字符串输入，避免在 int 上调用 isdigit
        try:
            interval_val = int(self.frame_interval_var.get())
        except Exception:
            raw = str(self.frame_interval_var.get())
            interval_val = int(raw) if raw.isdigit() else 1
        try:
            selected_format = self.get_selected_output_format()
        except Exception:
            selected_format = 'webp'
        self.config.update({
            'last_video_path': self.video_path_var.get(),
            'last_output_dir': self.output_dir_var.get(),
            'default_frame_interval': max(1, interval_val),
            'default_start_time': self.start_time_var.get(),
            'window_geometry': self.root.geometry(),
            'default_output_format': selected_format
        })
        save_project_config(self.config)

    def get_selected_output_format(self) -> str:
        """获取选中的输出格式（扩展名）"""
        display = getattr(self, 'output_format_display_var', None)
        if display is None:
            return self.config.get('default_output_format', 'webp')
        display_val = self.output_format_display_var.get()
        ext = self.output_format_reverse_map.get(display_val, 'webp')
        # 统一返回 'jpeg' 而非 'jpg'
        return 'jpeg' if ext == 'jpeg' else ext
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """视频帧提取工具 v1.0

功能特点:
• 支持多种视频格式
• 自定义时间范围提取
• 可调节帧间隔
• 实时预览功能
• 进度显示和日志记录

开发: Python + OpenCV + Tkinter
"""
        messagebox.showinfo("关于", about_text)
    
    def on_closing(self):
        """窗口关闭事件"""
        if self.is_extracting:
            if messagebox.askyesno("确认", "正在提取帧，确定要退出吗？"):
                self.is_extracting = False
            else:
                return
        
        # 保存配置
        self.save_current_config()
        
        # 清理资源
        if self.video_processor:
            self.video_processor.close()
        # 停止预览线程
        self.stop_preview_worker()
        
        self.root.destroy()

    def start_preview_worker(self):
        """启动后台预览线程（若未启动）"""
        if self.preview_worker and self.preview_worker.is_alive():
            return
        if not self.video_processor:
            return
        self.preview_worker_stop.clear()
        self.preview_worker = threading.Thread(target=self._preview_worker_loop, daemon=True)
        self.preview_worker.start()

    def stop_preview_worker(self):
        """停止后台预览线程"""
        try:
            if self.preview_worker:
                self.preview_worker_stop.set()
                self.preview_worker.join(timeout=0.5)
        except Exception:
            pass
        finally:
            self.preview_worker = None

    def _preview_worker_loop(self):
        """后台循环：按最新目标秒数拉取帧并在主线程显示"""
        last_seconds = None
        while not self.preview_worker_stop.is_set():
            try:
                if not self.video_processor:
                    time.sleep(0.1)
                    continue
                seconds = float(self.preview_target_seconds)
                # 避免重复解码同一时间点
                if last_seconds is not None and abs(seconds - last_seconds) < 1e-3:
                    time.sleep(0.05)
                    continue
                frame = self.video_processor.get_frame_at_seconds_fast(seconds)
                if frame is not None:
                    last_seconds = seconds
                    # 在主线程更新画面
                    self.root.after(0, lambda f=frame: self.display_preview_frame(f))
                # 控制频率（~20fps 上限，实际取决于解码速度）
                time.sleep(0.05)
            except Exception:
                time.sleep(0.1)
    
    def run(self):
        """运行应用程序"""
        self.root.mainloop()


if __name__ == "__main__":
    app = VideoFrameExtractorGUI()
    app.run()
