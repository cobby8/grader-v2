@echo off
REM ============================================================
REM  Uniform Grading Tool - launcher (double-click to start)
REM  This is a thin wrapper. All Korean guidance is printed by
REM  Python (webapp/run.py) so the console text never breaks.
REM ============================================================
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM Always run from this file's folder (the project root).
cd /d "%~dp0"

echo.
echo ============================================================
echo   Uniform Grading Tool - starting...
echo ============================================================
echo.

REM ---- Find a Python that actually has fastapi installed -------
REM A PC may have several Pythons (e.g. py=3.13, python=3.11) and
REM only one may have the parts installed. Test each candidate.
set "PYEXE="

call :try_py ".venv\Scripts\python.exe"
if not "!PYEXE!"=="" goto run

call :try_py "venv\Scripts\python.exe"
if not "!PYEXE!"=="" goto run

call :try_py "python"
if not "!PYEXE!"=="" goto run

call :try_py "py"
if not "!PYEXE!"=="" goto run

REM ---- No Python with fastapi. Decide which message to show. ----
REM If some Python exists, let Python print the (Korean) install
REM guide; otherwise no Python at all -> ask to install Python.
set "ANYPY="
where python >nul 2>nul && set "ANYPY=python"
if "!ANYPY!"=="" ( where py >nul 2>nul && set "ANYPY=py" )

if "!ANYPY!"=="" (
  echo [ERROR] Python is not installed.
  echo.
  echo   Install Python 3.11 from https://www.python.org/downloads/
  echo   and check "Add Python to PATH" during setup.
  echo   Then double-click run.bat again.
  echo.
  pause
  exit /b 1
)

REM Python exists but parts missing: run.py prints Korean guidance.
"!ANYPY!" -m webapp.run
echo.
pause
exit /b 1

:run
echo [OK] Using Python: !PYEXE!
"!PYEXE!" -m webapp.run
echo.
echo ============================================================
echo   Server stopped.
echo ============================================================
echo.
pause
exit /b 0

REM ---- helper: set PYEXE if the given Python has fastapi --------
:try_py
set "_CAND=%~1"
echo "%_CAND%" | findstr /i "\.exe" >nul
if not errorlevel 1 (
  if not exist "%_CAND%" goto :eof
)
"%_CAND%" -c "import fastapi, uvicorn" >nul 2>nul
if not errorlevel 1 set "PYEXE=%_CAND%"
goto :eof
