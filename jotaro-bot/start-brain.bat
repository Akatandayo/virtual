@echo off
rem Start the brain program for the Jotaro bot.
cd /d "%~dp0brain"
where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is not installed. Install it from https://nodejs.org/ and run this again.
  pause
  exit /b 1
)
if not exist node_modules call npm install --no-audit --no-fund
if not exist .env (
  copy .env.example .env >nul
  echo brain\.env was created. By default it uses your Claude Code login ^(Pro/Max plan^).
  echo To use an API key instead, set BACKEND=api and ANTHROPIC_API_KEY, then save and close Notepad.
  notepad .env
)
node src/index.js
pause
