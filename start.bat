@echo off
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Установка зависимостей...
    pip install -r requirements.txt
)
echo Запуск сервера...
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"
python main.py