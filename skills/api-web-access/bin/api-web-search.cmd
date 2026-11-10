@echo off
rem api-web-search launcher for Windows cmd/PowerShell (no Git Bash needed).
rem Location-independent: the skill root is derived from this script's path.
setlocal
for %%I in ("%~dp0..") do set "PROJECT_DIR=%%~fI"
uv run --project "%PROJECT_DIR%" api-web-search %*
exit /b %ERRORLEVEL%
