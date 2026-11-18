@echo off
REM Abre o gerenciador de modpacks no Windows (precisa do Python 3 instalado: python.org, marque "Add to PATH").
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw -3 modpack_gui.py) || (start "" pythonw modpack_gui.py)
