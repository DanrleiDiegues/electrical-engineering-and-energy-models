@echo off
chcp 65001 >nul
title Planejamento Energetico - iniciar
set "RAIZ=%~dp0"

echo [1/2] Abrindo a API (Python) na porta 8000...
if exist "%RAIZ%.venv\Scripts\python.exe" (set "PY=%RAIZ%.venv\Scripts\python.exe") else (set "PY=python")
start "API - Planejamento Energetico" cmd /k "cd /d "%RAIZ%" && "%PY%" -m uvicorn api.main:app --reload"

echo [2/2] Abrindo a interface React na porta 5173...
if not exist "%RAIZ%web\node_modules" (
  start "Web - Planejamento Energetico" cmd /k "cd /d "%RAIZ%web" && npm install && npm run dev"
) else (
  start "Web - Planejamento Energetico" cmd /k "cd /d "%RAIZ%web" && npm run dev"
)

echo Aguardando os servidores subirem...
timeout /t 8 >nul
start "" http://localhost:5173
echo.
echo Duas janelas foram abertas (API e Web). Se alguma mostrar erro, copie a mensagem.
echo Para encerrar, feche as duas janelas.
pause
