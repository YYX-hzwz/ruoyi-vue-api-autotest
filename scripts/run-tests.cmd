@echo off
REM 包装脚本：绕过 PowerShell 执行策略限制（Windows 默认禁止运行 .ps1）
REM 用法与 run-tests.ps1 完全一致，参数原样透传
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-tests.ps1" %*
exit /b %ERRORLEVEL%
