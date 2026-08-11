@echo off
setlocal

REM Build em pasta: reduz falsos positivos em comparacao ao executavel autoextraivel --onefile.
REM Instale antes as dependencias do scanner. O PyInstaller e atualizado abaixo.

echo Atualizando o empacotador...
python -m pip install --upgrade pyinstaller --quiet
if errorlevel 1 (
  echo Falha ao instalar ou atualizar o PyInstaller.
  exit /b 1
)

echo Gerando scanner em modo pasta, sem compactacao UPX...
python -m PyInstaller --noconfirm --clean --onedir --noconsole --noupx ^
  --name scanner --distpath dist --specpath build_spec --workpath build ^
  --version-file version_info.txt ^
  --hidden-import openpyxl --hidden-import pandas --hidden-import cv2 ^
  --hidden-import numpy --hidden-import pytesseract ^
  --hidden-import ler_documento_completo --hidden-import extrair_cabecalho ^
  --hidden-import planilha_relacional --hidden-import preprocessamento_scan ^
  --hidden-import pipeline_foto_torta ^
  --exclude-module torch --exclude-module tensorflow --exclude-module keras ^
  --exclude-module easyocr --exclude-module sklearn --exclude-module scipy ^
  --exclude-module matplotlib --exclude-module PyQt5 --exclude-module PyQt6 ^
  --exclude-module PySide2 --exclude-module PySide6 --exclude-module tkinter ^
  --exclude-module pytest --exclude-module IPython --exclude-module notebook ^
  scanner_cli.py

if errorlevel 1 (
  echo.
  echo Falha ao gerar o scanner.
  exit /b 1
)

echo.
echo Pronto: dist\scanner\scanner.exe
echo Distribua a pasta dist\scanner inteira. Nao copie somente o EXE.
echo Para ambientes corporativos, assine digitalmente o EXE com um certificado confiavel.
pause
endlocal
