@echo off
title Suno AI - Servidor Movil para Celular
echo Iniciando Servidor Web Movil...
echo.
python "%~dp0suno_mobile_server.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocurrio un error al iniciar. Presiona cualquier tecla para salir...
    pause
)
