@echo off
REM 包装脚本：绕过 PowerShell 执行策略限制
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0commit-history.ps1" %*
exit /b %ERRORLEVEL%
