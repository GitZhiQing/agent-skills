@echo off
rem ddgs-web-fetch launcher for Windows cmd/PowerShell (no Git Bash needed).
rem Location-independent: the project root is derived from this script's path.
setlocal
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
uv run --project "%PROJECT_DIR%" ddgs-web-fetch %*
exit /b %ERRORLEVEL%
