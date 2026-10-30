@echo off
REM 包装脚本：绕过 PowerShell 执行策略限制
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo-defect-lifecycle.ps1" %*
exit /b %ERRORLEVEL%
