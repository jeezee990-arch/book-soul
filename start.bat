@echo off
rem ============================================================
rem  Book Soul launcher (double-click to start)
rem ============================================================
rem  Starts the full stack:
rem    1. Python backend (auto-spawned by start_backend.ps1
rem       via beforeDevCommand in tauri.conf.json)
rem    2. Vite dev server (port 5173)
rem    3. Tauri desktop window
rem
rem  A console window will flash briefly; once the Tauri window
rem  appears you can ignore it.  To debug, keep this window open
rem  by removing the 'exit' line below.
rem ============================================================

rem Switch to repo root (script lives in repo root)
cd /d "%~dp0"

rem Launch via pnpm tauri dev (handles Python + Vite + Tauri)
start "" "pnpm.cmd" tauri dev

exit
