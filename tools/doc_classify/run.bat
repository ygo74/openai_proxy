@echo off
REM Simple batch file to run the document classifier with default settings

REM Default values
SET MODEL=gpt-4o
SET PROXY_URL=http://localhost:8000
SET API_KEY=sk-16AwYoZqNoVKjfMz-Mr8TeuaXk3O6JeLwPdQSAQiF0s
SET CATEGORIES=categories.json

REM Check if Python is available
where python >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH
    exit /b 1
)

REM Check if the doc_classify.py script exists
IF NOT EXIST doc_classify.py (
    echo Error: doc_classify.py not found in current directory
    exit /b 1
)

REM Check if categories.json exists
IF NOT EXIST %CATEGORIES% (
    echo Error: %CATEGORIES% not found in current directory
    exit /b 1
)

REM Display usage if no arguments provided
IF "%~1"=="" (
    echo Usage: %0 [--file document.pdf ^| --folder documents/]
    echo Optional arguments:
    echo   --output results.json    Save results to JSON file
    echo   --model model_name       Specify a different model (default: %MODEL%)
    echo   --verbose                Enable verbose logging
    exit /b 1
)

REM Run the script with provided arguments
python doc_classify.py --proxy-url "%PROXY_URL%" --api-key "%API_KEY%" --model "%MODEL%" --categories "%CATEGORIES%" %*