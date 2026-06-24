@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   Concurrent Gemma - Local RTX Edition
echo   NVIDIA / Windows optimized fork
echo ============================================
echo.

echo Checking if Ollama is already running (separate CMD or prior serve)...

REM --- Readiness check using only curl + findstr (no PowerShell at all here) ---
set "TMPVER=%TEMP%\ollama-ver-%RANDOM%.txt"
curl -s --max-time 2 http://localhost:11434/api/version > "%TMPVER%" 2>nul
findstr /c:"version" "%TMPVER%" >nul 2>&1
set "READY=%errorlevel%"
del "%TMPVER%" >nul 2>&1

if %READY% equ 0 goto :ollama_is_up

echo No live Ollama API responding. Freeing port 11434 if anything is holding it...

REM Pure batch: kill anything listening on 11434 via netstat

goto :after_ollama_check

:ollama_is_up
echo ✅ Ollama is UP and responding on http://localhost:11434.
echo    Detected your external CMD serve — will NOT kill or restart it.
echo    Concurrency (OLLAMA_NUM_PARALLEL) uses the value that was active when YOU started your ollama serve.
echo    If you want a different agent count, use the "Apply OLLAMA_NUM_PARALLEL" button inside the app,
echo    or restart your serve manually with $env:OLLAMA_NUM_PARALLEL=N before "ollama serve".
echo.
goto :start_python

:after_ollama_check

for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":11434" ^| findstr "LISTENING"') do (
    echo   Killing listener PID %%p
    taskkill /F /PID %%p /T >nul 2>&1
)
timeout /t 1 >nul

REM Also kill by known process names
for %%p in (ollama.exe "Ollama Desktop.exe") do (
    taskkill /F /IM %%p /T >nul 2>&1
)
timeout /t 1 >nul

echo.
echo Starting Ollama server in a new minimized window with OLLAMA_NUM_PARALLEL=4 ...
start "Ollama Server (parallel)" /min cmd /c "set OLLAMA_NUM_PARALLEL=4 && ollama serve"

echo Waiting for Ollama to become ready (max ~30s)...
set attempts=0

:waitloop
timeout /t 1 >nul

set "TMPVER=%TEMP%\ollama-ver-%RANDOM%.txt"
curl -s --max-time 2 http://localhost:11434/api/version > "%TMPVER%" 2>nul
findstr /c:"version" "%TMPVER%" >nul 2>&1
set "READY=%errorlevel%"
del "%TMPVER%" >nul 2>&1

if %READY% equ 0 goto :ollama_responded

set /a attempts+=1
if %attempts% GEQ 30 goto :wait_timeout
goto :waitloop

:ollama_responded
echo Ollama responded after ~%attempts% seconds.
goto :ollama_ready

:wait_timeout
echo WARNING: Ollama did not respond within 30 seconds.
echo          Will proceed anyway — the Gradio app will show a red banner if still unreachable.
goto :ollama_ready

:ollama_ready
echo.
echo *** Ollama ready with parallelism. ***
echo.
echo To run YOUR OWN serve manually (recommended for full control):
echo   In a separate PowerShell / CMD window:
echo     $env:OLLAMA_NUM_PARALLEL=4
echo     ollama serve
echo.
echo (If you get 'bind: Only one usage of each socket address', run these first:)
echo   netstat -ano ^| findstr :11434
echo   taskkill /F /PID ^<the-PID^> /T
echo   taskkill /F /IM ollama.exe /T
echo   taskkill /F /IM "Ollama Desktop.exe" /T
echo.
echo Then run run.bat again — it will now detect your manual serve and skip starting its own.
echo.

:start_python

REM Create venv if it doesn't exist
if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create venv. Make sure Python 3.10+ is installed.
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Installing / updating dependencies...
pip install -r requirements.txt --quiet

echo.
echo Starting Gradio dashboard...
echo Open the URL shown below in your browser.
echo.

python app.py

echo.
echo App closed.
pause
