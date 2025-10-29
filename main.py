#!/usr/bin/env python3
"""
视频帧提取工具 - 主程序入口
支持命令行和GUI两种使用方式
"""

import sys
import os
import argparse
from typing import Optional

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from video_processor import VideoProcessor, create_output_directory, validate_time_format
from main_gui import VideoFrameExtractorGUI
from utils import is_video_file, get_file_size_mb, format_file_size


def print_banner():
    """打印程序横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                    视频帧提取工具 v1.0                         ║
║                Video Frame Extraction Tool                   ║
╠══════════════════════════════════════════════════════════════╣
║  功能: 将视频转换为时间命名的图片序列                              ║
║  支持: 多种视频格式，自定义时间范围和帧间隔                         ║
║  输出: HH-MM-SS-ms.png 格式的图片文件                           ║
╠══════════════════════════════════════════════════════════════╣
║  作者：Lun.   githun:Lun-OS   QQ:15965342218                  ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_help():
    """打印帮助信息"""
    help_text = """
使用方法:
  python main.py                           # 启动GUI界面
  python main.py [视频文件]                 # 使用默认参数提取
  python main.py [视频文件] [选项]          # 使用自定义参数提取

选项:
  -h, --help                              显示此帮助信息
  -o, --output DIR                        输出目录 (默认: ./{视频名称}/)
  -s, --start TIME                        开始时间 (格式: HH:MM:SS, 默认: 00:00:00)
  -e, --end TIME                          结束时间 (格式: HH:MM:SS, 默认: 视频结尾)
  -i, --interval N                        帧间隔 (每隔N帧提取一帧, 默认: 1)
  --gui                                   强制启动GUI界面
  --no-gui                                强制使用命令行模式

示例:
  python main.py video.mp4                                    # 提取整个视频的所有帧
  python main.py video.mp4 -s 00:01:00 -e 00:02:00          # 提取1-2分钟的帧
  python main.py video.mp4 -i 30                             # 每隔30帧提取一帧
  python main.py video.mp4 -o ./output -s 00:00:30 -i 10    # 自定义输出目录和参数

支持的视频格式:
  .mp4, .avi, .mov, .mkv, .wmv, .flv, .webm, .m4v, .3gp, .mpg, .mpeg, .ts
"""
    print(help_text)


def validate_arguments(args) -> tuple[bool, str]:
    """
    验证命令行参数
    
    Returns:
        (是否有效, 错误信息)
    """
    # 检查视频文件
    if not os.path.isfile(args.video):
        return False, f"视频文件不存在: {args.video}"
    
    if not is_video_file(args.video):
        return False, f"不支持的视频格式: {args.video}"
    
    # 检查时间格式
    if args.start and not validate_time_format(args.start):
        return False, f"开始时间格式错误: {args.start} (应为 HH:MM:SS)"
    
    if args.end and not validate_time_format(args.end):
        return False, f"结束时间格式错误: {args.end} (应为 HH:MM:SS)"
    
    # 检查帧间隔
    if args.interval < 1:
        return False, f"帧间隔必须大于0: {args.interval}"
    
    return True, ""


def extract_frames_cli(args) -> bool:
    """
    命令行模式提取帧
    
    Returns:
        是否成功
    """
    try:
        print(f"正在加载视频: {args.video}")
        
        # 显示视频信息
        file_size = get_file_size_mb(args.video)
        print(f"文件大小: {file_size:.1f} MB")
        
        # 创建视频处理器
        processor = VideoProcessor(args.video)
        video_info = processor.get_video_info()
        
        print(f"分辨率: {video_info['width']} x {video_info['height']}")
        print(f"帧率: {video_info['fps']:.2f} fps")
        print(f"总帧数: {video_info['total_frames']}")
        print(f"时长: {video_info['duration']:.2f} 秒")
        print()
        
        # 设置输出目录
        if args.output:
            output_dir = args.output
        else:
            output_dir = create_output_directory(args.video)
        
        print(f"输出目录: {output_dir}")
        
        # 计算预计提取帧数
        start_frame = processor.timestamp_to_frame(args.start) if args.start else 0
        if args.end:
            end_frame = processor.timestamp_to_frame(args.end)
        else:
            end_frame = video_info['total_frames'] - 1
        
        estimated_frames = len(range(start_frame, end_frame + 1, args.interval))
        print(f"预计提取帧数: {estimated_frames}")
        print()
        
        # 进度回调函数
        def progress_callback(current, total, frame_path):
            progress = (current / total) * 100
            filename = os.path.basename(frame_path)
            print(f"\r进度: {current}/{total} ({progress:.1f}%) - {filename}", end="", flush=True)
        
        print("开始提取帧...")
        
        # 执行提取
        result = processor.extract_frames(
            output_dir=output_dir,
            start_time=args.start,
            end_time=args.end,
            frame_interval=args.interval,
            progress_callback=progress_callback
        )
        
        print()  # 换行
        print()
        
        # 显示结果
        print("提取完成！")
        print(f"总计划提取: {result['total_frames_to_extract']} 帧")
        print(f"成功提取: {result['extracted_count']} 帧")
        print(f"失败: {result['failed_count']} 帧")
        print(f"输出目录: {result['output_directory']}")
        print(f"耗时: {result['extract_duration']:.2f} 秒")
        
        if result['failed_count'] > 0:
            print(f"警告: 有 {result['failed_count']} 帧提取失败")
        
        processor.close()
        return True
        
    except KeyboardInterrupt:
        print("\n\n用户中断操作")
        return False
    except Exception as e:
        print(f"\n\n错误: {str(e)}")
        return False


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="视频帧提取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False
    )
    
    parser.add_argument('video', nargs='?', help='视频文件路径')
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助信息')
    parser.add_argument('-o', '--output', help='输出目录')
    parser.add_argument('-s', '--start', default='00:00:00', help='开始时间 (HH:MM:SS)')
    parser.add_argument('-e', '--end', help='结束时间 (HH:MM:SS)')
    parser.add_argument('-i', '--interval', type=int, default=1, help='帧间隔')
    parser.add_argument('--gui', action='store_true', help='强制启动GUI')
    parser.add_argument('--no-gui', action='store_true', help='强制使用命令行模式')
    
    args = parser.parse_args()
    
    # 显示横幅
    print_banner()
    
    # 显示帮助
    if args.help:
        print_help()
        return 0
    
    # 决定使用GUI还是命令行模式
    use_gui = False
    
    if args.gui:
        use_gui = True
    elif args.no_gui:
        use_gui = False
    elif not args.video:
        # 没有提供视频文件，启动GUI
        use_gui = True
    else:
        # 提供了视频文件，使用命令行模式
        use_gui = False
    
    if use_gui:
        print("启动图形界面...")
        try:
            app = VideoFrameExtractorGUI()
            app.run()
            return 0
        except Exception as e:
            print(f"GUI启动失败: {str(e)}")
            print("请检查是否正确安装了所需的依赖库")
            return 1
    else:
        # 命令行模式
        if not args.video:
            print("错误: 命令行模式需要指定视频文件")
            print("使用 'python main.py --help' 查看帮助信息")
            return 1
        
        # 验证参数
        valid, error_msg = validate_arguments(args)
        if not valid:
            print(f"参数错误: {error_msg}")
            return 1
        
        # 执行提取
        success = extract_frames_cli(args)
        return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n程序异常退出: {str(e)}")
        sys.exit(1)