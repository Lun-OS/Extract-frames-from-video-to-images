# 视频帧提取工具（Video Frame Extraction）

将视频按时间戳导出为图像序列，支持 GUI 与命令行两种使用方式，适合数据集制作、素材采样、镜头分析等场景。

## 目录
- 功能特性
- 环境要求
- 安装
- 快速开始
  - 启动 GUI
  - 使用命令行（CLI）
- 命令行参数说明
- 输出与命名规则
- 性能与体积建议
- 常见问题
- 项目结构
- 开发与贡献

## 功能特性
- 支持多种视频格式（.mp4, .avi, .mov, .mkv, .wmv, .flv, .webm, .m4v, .3gp, .mpg, .mpeg, .ts）
- 图形界面（Tkinter）：视频选择、时间范围拖动条、预览、进度与日志展示、最近文件列表
- 命令行模式：一条命令即可提取指定时间段的帧
- 可设置帧间隔（每隔 N 帧提取一帧）
- 输出格式（GUI）：PNG / WebP / JPEG 可选；命令行默认导出为 WebP
- 自动选择后端：优先使用 FFmpeg（若已安装，支持硬件解码），否则回退到 OpenCV
- 多线程并行写盘，加速保存过程
- 自动为输出目录估算体积并提示磁盘空间风险
- 友好的错误提示与进度展示

## 环境要求
- 操作系统：Windows / macOS / Linux
- Python：推荐 3.9+（Windows 安装脚本提示为 3.7+，但代码类型注解更适配 3.9 及以上）
- 依赖库：
  - opencv-python
  - Pillow
  - numpy
  - tqdm
- 可选：FFmpeg（强烈推荐，通常更快且可用硬件解码）

## 安装

### Windows 一键安装
仓库根目录提供了安装脚本 `install.bat`：

1) 双击运行 `install.bat`（或在终端执行）
2) 脚本将自动升级 pip/setuptools/wheel 并安装依赖
3) 若网络问题导致安装失败，脚本会自动切换清华镜像源重试，并给出手动安装建议

安装完成后，终端会提示运行：

```bash
python main.py
```

### 通用方式（跨平台）
建议在虚拟环境中安装：

```bash
python -m venv .venv
. .venv/bin/activate   # Windows 请执行: .\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

可选：安装 FFmpeg 以获得更佳性能与硬件加速（Windows 可参考 ffmpeg.org 或各大包管理器）。

## 快速开始

### 启动 GUI
图形界面便于交互预览与参数设置：

```bash
python main.py
```

在 GUI 中：
- 选择视频文件（支持的格式见下）
- 通过开始/结束时间拖动条设定提取范围（也可直接输入如 00:01:23）
- 设置帧间隔（每隔 N 帧提取一帧）
- 选择输出目录与输出格式（PNG / WebP / JPEG）
- 点击“开始提取”，查看进度与日志

### 使用命令行（CLI）
命令行适合脚本化批处理：

```bash
python main.py [视频文件] [选项]
```

常用示例：

```bash
# 提取整个视频的所有帧（默认 WebP，输出到 ./{视频名称}/）
python main.py video.mp4

# 提取 1-2 分钟的帧
python main.py video.mp4 -s 00:01:00 -e 00:02:00

# 每隔 30 帧提取一帧
python main.py video.mp4 -i 30

# 自定义输出目录与参数
python main.py video.mp4 -o ./output -s 00:00:30 -i 10

# 强制启动 GUI / 强制使用 CLI
python main.py --gui
python main.py video.mp4 --no-gui
```

## 命令行参数说明
- `-o, --output DIR`：输出目录（默认：当前目录下以视频名创建的文件夹，如 `./video_name/`）
- `-s, --start TIME`：开始时间，格式为 `HH:MM:SS`（也接受 `HH-MM-SS`）；默认 `00:00:00`
- `-e, --end TIME`：结束时间，格式为 `HH:MM:SS`（也接受 `HH-MM-SS`）；默认到视频结尾
- `-i, --interval N`：帧间隔（每隔 N 帧提取一帧）；默认 `1`
- `--gui`：强制启动 GUI
- `--no-gui`：强制使用命令行模式

支持的视频格式：
`.mp4, .avi, .mov, .mkv, .wmv, .flv, .webm, .m4v, .3gp, .mpg, .mpeg, .ts`

## 输出与命名规则
- 默认输出目录：`./{视频文件名不含扩展}/`
- 文件命名：`HH-MM-SS-ms.ext`（例如 `00-01-23-456.webp`），其中 ms 为毫秒
- 输出格式：
  - GUI 可选：`PNG / WebP / JPEG`
  - CLI 默认：`WebP`（无损模式；若使用 FFmpeg 后端，仍以 WebP 方式编码）

## 性能与体积建议
- 更快：安装并使用 FFmpeg（自动检测），通常优于 OpenCV 解码；在 Windows 上默认尝试硬件加速（dxva2）
- 更小：优先选择 WebP（体积更小，但编码稍慢）或 JPEG（极快但有损）
- 更稳：较大的帧间跳转由内核自动处理；GUI 预览对小幅拖动做了优化以提升跟手性
- 更安全：程序会估算输出总大小并在空间可能不足时提示继续与否

## 常见问题
1) 依赖安装失败？
   - Windows 下可直接运行 `install.bat`，脚本会自动重试并切换清华镜像源
   - 手动安装：`python -m pip install -r requirements.txt`
2) 无法打开视频？
   - 确认文件路径正确、格式在支持列表内；如仍有问题，建议安装 FFmpeg 后重试
3) 输出体积过大？
   - 尝试在 GUI 中选择 WebP 或 JPEG；或增大帧间隔（`-i`）以降低输出帧数

## 项目结构
```
├── main.py             # 程序入口（CLI/GUI 切换）
├── main_gui.py         # 图形界面（Tkinter）
├── video_processor.py  # 核心提取逻辑（OpenCV/FFmpeg 后端）
├── utils.py            # 工具函数（格式判断、体积估算、配置保存等）
├── requirements.txt    # 依赖列表
├── install.bat         # Windows 一键安装脚本
└── README.md           # 项目说明
```

## 开发与贡献
- 欢迎提交 Issue 与 Pull Request 改进功能与体验
- 建议安装并启用 FFmpeg 以便在开发过程中更好地对齐性能表现

—— 作者：Lun（GitHub: Lun-OS）
