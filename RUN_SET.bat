@echo off
rem RUN_SET.bat <set>  -- or drag a set folder from sets\ onto this file.
rem Builds one weapon set and stops at the first thing that is wrong.
setlocal
if "%~1"=="" (
  echo Usage: RUN_SET.bat ^<set^>       for example: RUN_SET.bat vanilla_check
  exit /b 2
)
set "SETARG=%~n1"
python -m forge.run_set "%SETARG%" %2 %3 %4 %5 %6
exit /b %ERRORLEVEL%
