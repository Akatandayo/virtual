@echo off
rem Install the Jotaro bot into a Bedrock Dedicated Server folder.
rem Usage: install.bat "C:\path\to\bedrock-server" ["C:\path\to\stand_addon.mcaddon"]
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: install.bat "server folder" ["stand addon .mcaddon"]
  pause
  exit /b 1
)
if "%~2"=="" (
  node tools\install.mjs "%~1"
) else (
  node tools\install.mjs "%~1" --addon "%~2"
)
pause
