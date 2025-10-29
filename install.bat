@echo off
chcp 65001 >nul
echo ========================================
echo 视频帧提取工具 - 依赖库安装脚本
echo ========================================
echo.

echo 正在检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python环境，请先安装Python 3.7+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python环境检查通过！
echo.

echo 正在升级 pip / setuptools / wheel...
python -m pip install --upgrade pip setuptools wheel

echo.
echo 正在安装项目依赖库...
echo 这可能需要几分钟时间，请耐心等待...
echo.

python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [提示] 初次安装失败，自动切换清华镜像源重试...
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
    if errorlevel 1 (
        echo.
        echo [尝试修复] Pillow 二进制轮子安装（避免源码构建）...
        python -m pip install "Pillow>=11.0.0" --only-binary=:all: -i https://pypi.tuna.tsinghua.edu.cn/simple/
        echo [再次重试] 重新安装全部依赖...
        python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
        if errorlevel 1 (
            echo.
            echo [错误] 依赖库安装仍然失败！
            echo 可能原因：
            echo  1) 网络环境限制或镜像不可用
            echo  2) Python版本过新，部分库未发布对应轮子
            echo  3) 本地編譯環境缺失（如VC編譯器等）
            echo.
            echo 可手动尝试：
            echo  python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
            echo 或逐个安装：
            echo  python -m pip install opencv-python Pillow numpy tqdm -i https://pypi.tuna.tsinghua.edu.cn/simple/
            pause
            exit /b 1
        )
    )
)

echo.
echo ========================================
echo 安装完成！
echo ========================================
echo 现在可以运行程序了：
echo python main.py
echo.
pause
