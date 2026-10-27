@echo off
rem windows-disk-cleanup launcher for Windows cmd/PowerShell.
rem Location-independent: the project root is derived from this script's path.
setlocal
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
set "PYTHONPATH=%PROJECT_DIR%\src;%PYTHONPATH%"

where uv >nul 2>nul
if %ERRORLEVEL%==0 (
  uv run --no-project python -m disk_cleanup %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python -m disk_cleanup %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m disk_cleanup %*
  exit /b %ERRORLEVEL%
)

echo ERROR: 找不到 uv/python/py。请安装 uv 或 Python 3.9+。 1>&2
exit /b 2
