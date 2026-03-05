"""
Extrai cabeçalho do documento: nome do treinamento e data.
Regra: geralmente em LETRA MAIOR, linha maior do cabeçalho, ou contém
TREINAMENTO, CAPACITAÇÃO, NR, SEGURANÇA.
"""

import re
import os
from typing import Optional, Tuple, List, Union
import cv2
import numpy as np

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _SCRIPT_DIR:
    os.chdir(_SCRIPT_DIR)

# Palavras-chave que indicam nome de treinamento
PALAVRAS_TREINAMENTO = ("TREINAMENTO", "CAPACITAÇÃO", "CAPACITACAO", "NR", "SEGURANÇA", "SEGURANCA", "CURSO", "NR-")

# Padrões de data (DD.MM.YY ou DD/MM/YYYY)
REGEX_DATA = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b")


_EASYOCR_READER = None

def _get_reader():
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
            _EASYOCR_READER = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
        except Exception:
            pass
    return _EASYOCR_READER


def _ocr_topo_imagem(imagem: np.ndarray, fracao_topo: float = 0.22) -> List[Tuple[float, float, float, float, str, float]]:
    """
    OCR apenas na faixa superior da imagem.
    Retorna lista de (x1, y1, x2, y2, texto, confiança).
    """
    h, w = imagem.shape[:2]
    y_corte = int(h * fracao_topo)
    topo = imagem[0:y_corte, 0:w]
    if topo.size == 0:
        return []
    resultados = []
    reader = _get_reader()
    if reader is not None:
        try:
            if len(topo.shape) == 2:
                topo_rgb = cv2.cvtColor(topo, cv2.COLOR_GRAY2RGB)
            else:
                topo_rgb = cv2.cvtColor(topo, cv2.COLOR_BGR2RGB)
            det = reader.readtext(topo_rgb)
            for bbox, texto, conf in det:
                if not texto or not bbox:
                    continue
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                resultados.append((min(xs), min(ys), max(xs), max(ys), texto.strip(), float(conf)))
        except Exception:
            pass
    try:
        import pytesseract
        if len(topo.shape) == 3:
            gray = cv2.cvtColor(topo, cv2.COLOR_BGR2GRAY)
        else:
            gray = topo
        d = pytesseract.image_to_data(gray, lang="por", output_type=pytesseract.Output.DICT)
        n = len(d.get("text", []))
        for i in range(n):
            txt = (d.get("text") or [""])[i]
            if not txt or not txt.strip():
                continue
            left = int((d.get("left") or [0])[i])
            top_ = int((d.get("top") or [0])[i])
            ww = int((d.get("width") or [0])[i])
            hh = int((d.get("height") or [0])[i])
            conf = int((d.get("conf") or [0])[i])
            if conf <= 0:
                continue
            resultados.append((left, top_, left + ww, top_ + hh, txt.strip(), conf / 100.0))
    except Exception:
        pass
    return resultados


def _melhor_linha_treinamento(
    linhas: List[Tuple[float, float, float, float, str, float]]
) -> Optional[str]:
    """
    Escolhe a linha mais provável de ser o nome do treinamento:
    - contém palavra-chave (TREINAMENTO, NR, etc.), ou
    - linha com mais caracteres, ou
    - linha com maior altura de bbox (letra maior).
    """
    if not linhas:
        return None
    texto_upper = None
    melhor = None
    melhor_pontos = -1
    for (x1, y1, x2, y2, texto, conf) in linhas:
        t = (texto or "").strip()
        if len(t) < 3:
            continue
        tu = t.upper()
        pontos = 0
        if any(palavra in tu for palavra in PALAVRAS_TREINAMENTO):
            pontos += 100
        altura = y2 - y1
        if altura > 0:
            pontos += min(50, altura / 2)
        pontos += min(30, len(t) / 2)
        if conf > 0.5:
            pontos += 10
        if pontos > melhor_pontos:
            melhor_pontos = pontos
            melhor = t
    return melhor


def _extrair_data(texto_ou_linhas: Union[str, List[str]]) -> Optional[str]:
    """Encontra primeira data no formato DD.MM.YY ou DD/MM/YYYY."""
    if isinstance(texto_ou_linhas, list):
        texto = " ".join(str(x) for x in texto_ou_linhas)
    else:
        texto = texto_ou_linhas or ""
    m = REGEX_DATA.search(texto)
    if not m:
        return None
    d, mes, ano = m.group(1), m.group(2), m.group(3)
    if len(ano) == 2:
        ano = "20" + ano
    return f"{d.zfill(2)}.{mes.zfill(2)}.{ano}"


def extrair_cabecalho_documento(
    caminho_ou_imagem: Union[str, np.ndarray],
    fracao_topo: float = 0.22,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrai do cabeçalho do documento o nome do treinamento e a data.
    - nome_treinamento: linha com palavra-chave ou maior/mais longa.
    - data_treinamento: primeira data encontrada (DD.MM.YYYY).

    Returns:
        (nome_treinamento, data_treinamento)
    """
    if isinstance(caminho_ou_imagem, str):
        if not os.path.exists(caminho_ou_imagem):
            return None, None
        img = cv2.imread(caminho_ou_imagem)
    else:
        img = caminho_ou_imagem
    if img is None or img.size == 0:
        return None, None
    linhas = _ocr_topo_imagem(img, fracao_topo=fracao_topo)
    nome = _melhor_linha_treinamento(linhas)
    todos_textos = [linha[4] for linha in linhas]
    data = _extrair_data(todos_textos)
    return nome, data
