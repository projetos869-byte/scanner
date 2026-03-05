@echo off
REM Gera scanner.exe para uso com o Excel.
REM Requer: pip install pyinstaller openpyxl pandas
REM Opcional (para atualizar Excel aberto): pip install pywin32

echo Instalando dependencias para build...
pip install pyinstaller openpyxl pandas --quiet
pip install pywin32 --quiet 2>nul

echo.
echo Gerando scanner.exe...
pyinstaller --onefile --noconsole --name scanner --distpath dist --specpath . --workpath build ^
  --hidden-import openpyxl --hidden-import pandas --hidden-import cv2 --hidden-import numpy ^
  --hidden-import easyocr --hidden-import pytesseract --hidden-import win32com.client ^
  --hidden-import ler_documento_completo --hidden-import extrair_cabecalho --hidden-import planilha_relacional ^
  --hidden-import preprocessamento_scan --hidden-import pipeline_foto_torta ^
  scanner_cli.py

echo.
echo Pronto. Exe em: dist\scanner.exe
echo Copie dist\scanner.exe e a pasta scanner (ou apenas o exe + controle_treinamentos.xlsx + pasta imagens) para onde for usar.
pause
