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
echo   采集 - 写入数据库
echo     1. 销量排行（最近6个月）
echo     2. 配置参数表（热销车系）
echo     3. 配置参数表（全品牌）
echo     4. 全量采集（销量+配置）
echo.
echo   导出 - 数据库转xlsx
echo     5. 销量排行xlsx
echo     6. 配置参数表xlsx
echo     7. 全量导出
echo.
echo   q. 退出
echo  ==============================
echo.

set choice=
set /p choice=  选择: 

if "%choice%"=="1"  uv run python -m src.fetch_to_db sales --months 6
if "%choice%"=="2"  uv run python -m src.fetch_to_db specs --mode sales
if "%choice%"=="3"  uv run python -m src.fetch_to_db specs --mode all
if "%choice%"=="4"  uv run python -m src.fetch_to_db all --months 6
if "%choice%"=="5"  uv run python -m src.export sales --months 6 --top 50
if "%choice%"=="6"  uv run python -m src.export specs
if "%choice%"=="7"  uv run python -m src.export all
if /i "%choice%"=="q" exit /b 0

echo.
echo  -- 按任意键返回菜单 --
pause >nul
goto menu
