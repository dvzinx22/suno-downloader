@echo off
title Suno AI Downloader
echo Iniciando Suno AI Downloader...
python "%~dp0suno_downloader.py" --gui
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocurrio un error al iniciar. Presiona cualquier tecla para salir...
    pause
)
