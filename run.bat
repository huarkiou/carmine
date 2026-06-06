@echo off
chcp 936 >nul
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 uv，请先安装：https://github.com/astral-sh/uv
    pause
    exit /b 1
)

if not exist "uv.lock" (
    echo [提示] 正在安装依赖...
    uv sync
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

:menu
cls
echo.
echo  ==============================
echo    carmine - 汽车行业数据采集
echo  ==============================
echo.
echo   采集 - 写入数据库 (默认 output/carmine.db)
echo     1. 销量排行 (近6个月)
echo     2. 配置参数 (热销车系)
echo     3. 配置参数 (全品牌)
echo     4. 配置参数 (全品牌 + 停售年款)
echo     5. 全量采集 (销量 + 配置)
echo.
echo   导出 - 数据库转xlsx (默认 output/{timestamp}/)
echo     6. 销量排行 xlsx
echo     7. 配置参数 xlsx
echo     8. 全量导出
echo.
echo   q. 退出
echo  ==============================
echo   提示: 高级选项请直接用命令行
echo     --db PATH      指定数据库文件
echo     --output PATH  指定输出目录
echo     --all-years    含停售年款
echo     --months N     月数 (1-6)
echo  ==============================
echo.

set choice=
set /p choice=  选择: 

if "%choice%"=="1"  uv run python -m src.fetch_to_db sales --months 6
if "%choice%"=="2"  uv run python -m src.fetch_to_db specs --mode sales
if "%choice%"=="3"  uv run python -m src.fetch_to_db specs --mode all
if "%choice%"=="4"  uv run python -m src.fetch_to_db specs --mode all --all-years
if "%choice%"=="5"  uv run python -m src.fetch_to_db all --months 6
if "%choice%"=="6"  uv run python -m src.export sales --months 6 --top 50
if "%choice%"=="7"  uv run python -m src.export specs
if "%choice%"=="8"  uv run python -m src.export all
if /i "%choice%"=="q" exit /b 0

echo.
echo  -- 按任意键返回菜单 --
pause >nul
goto menu
