@echo off
rem CHECK_ALL.bat -- re-runs every set that has passed and compares it against its
rem accepted output under tests\. Must stay green.
setlocal
python -m forge.run_set --check-all
exit /b %ERRORLEVEL%
