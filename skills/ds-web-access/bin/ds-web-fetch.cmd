@echo off
rem ds-web-fetch launcher for Windows cmd/PowerShell.
setlocal
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
uv run --project "%PROJECT_DIR%" ds-web-fetch %*
exit /b %ERRORLEVEL%
