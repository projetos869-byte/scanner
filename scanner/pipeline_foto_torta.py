"""
Pipeline à prova de foto torta — Etapa B: grade da tabela por morfologia (sem x fixo).

Depois do warp (Etapa A), extrai linhas verticais e horizontais por morfologia,
monta a grade e extrai matrícula + presença de assinatura por faixas (pick_band).
Plugável: pode usar preprocessamento_scan para warp ou este módulo standalone.

Uso:
  from pipeline_foto_torta import extrair_matricula_e_presenca
  resultados = extrair_matricula_e_presenca(img_bgr, ...)
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import os

# Opcional: usar nosso pré-processamento para warp
try:
    from preprocessamento_scan import normalizar_para_scan, LARGURA_PADRAO_WARP
    _TEM_PREPROC = True
except ImportError:
    _TEM_PREPROC = False

try:
    import pytesseract
except ImportError:
    pytesseract = None


# ---------- Etapa A (warp) — pode vir do preprocessamento_scan ou inline ----------

def _order_points(pts: np.ndarray) -> np.ndarray:
    """Ordena 4 pontos: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _four_point_transform(image: np.ndarray, pts: np.ndarray) -> np.ndarray:
    rect = _order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxW = int(max(widthA, widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxH = int(max(heightA, heightB))
    dst = np.array([[0, 0], [maxW - 1, 0], [maxW - 1, maxH - 1], [0, maxH - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxW, maxH))


def preprocess_and_warp(img_bgr: np.ndarray, target_w: int = 2200) -> np.ndarray:
    """
    Grayscale → blur → Canny → maior contorno retangular → warp → redimensionar por largura.
    Se preprocessamento_scan estiver disponível, usa normalizar_para_scan com target_width.
    """
    if _TEM_PREPROC:
        warped = normalizar_para_scan(
            img_bgr,
            tamanho_a4=None,
            target_width=target_w,
            aplicar_deskew=True,
            aplicar_binarizacao=False,
            retornar_bgr=True,
        )
        return warped

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 60, 180)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
    page = None
    for c in cnts[:10]:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            page = approx.reshape(4, 2)
            break
    if page is None:
        warped = img_bgr
    else:
        warped = _four_point_transform(img_bgr, page)
    h, w = warped.shape[:2]
    scale = target_w / w
    warped = cv2.resize(warped, (target_w, int(h * scale)), interpolation=cv2.INTER_CUBIC)
    return warped


# ---------- Binarização (como no pipeline recomendado) ----------

def binarizar(img_bgr: np.ndarray) -> np.ndarray:
    """ADAPTIVE_THRESH_MEAN_C, block 35, C 15, BINARY_INV."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    thr = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        35, 15
    )
    return thr


# ---------- Etapa B: grade da tabela (linhas verticais e horizontais) ----------

def extrair_linhas(thr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Extrai máscaras de linhas verticais e horizontais por morfologia."""
    h, w = thr.shape
    vk = max(12, h // 28)
    vkernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vk))
    v = cv2.erode(thr, vkernel, iterations=1)
    v = cv2.dilate(v, vkernel, iterations=2)
    hk = max(40, w // 18)
    hkernel = cv2.getStructuringElement(cv2.MORPH_RECT, (hk, 1))
    hh = cv2.erode(thr, hkernel, iterations=1)
    hh = cv2.dilate(hh, hkernel, iterations=3)
    return v, hh


def get_vertical_x(vmask: np.ndarray, min_height_ratio: float = 0.60) -> List[int]:
    """Posições x dos segmentos verticais (colunas)."""
    h, w = vmask.shape
    num, _, stats, _ = cv2.connectedComponentsWithStats((vmask > 0).astype(np.uint8), 8)
    xs = []
    for i in range(1, num):
        x, y, ww, hh, area = stats[i]
        if hh >= h * min_height_ratio and ww <= 12 and area > 200:
            xs.append(x + ww // 2)
    xs = sorted(xs)
    out = []
    for x in xs:
        if not out or abs(x - out[-1]) > 12:
            out.append(x)
    if not out or out[0] > w * 0.05:
        out = [0] + out
    if out[-1] < w * 0.95:
        out = out + [w - 1]
    return out


def get_horizontal_y(hmask: np.ndarray) -> List[int]:
    """Posições y dos segmentos horizontais (linhas)."""
    h, w = hmask.shape
    num, _, stats, _ = cv2.connectedComponentsWithStats((hmask > 0).astype(np.uint8), 8)
    ys = []
    for i in range(1, num):
        x, y, ww, hh, area = stats[i]
        if ww >= w * 0.70 and hh <= 22 and area > 500:
            ys.append(y + hh // 2)
    ys = sorted(ys)
    out = []
    for y in ys:
        if not out or abs(y - out[-1]) > 10:
            out.append(y)
    return out


def crop(img: np.ndarray, x1: int, x2: int, y1: int, y2: int, pad: int = 4) -> np.ndarray:
    """Recorta região com padding interno."""
    h, w = img.shape[:2]
    x1 = max(0, x1 + pad)
    y1 = max(0, y1 + pad)
    x2 = min(w, x2 - pad)
    y2 = min(h, y2 - pad)
    return img[y1:y2, x1:x2]


def pick_band(x_list: List[int], left_ratio: float, right_ratio: float, W: int) -> Tuple[int, int]:
    """Escolhe o par (x_inicio, x_fim) que cobre a faixa [left_ratio*W, right_ratio*W]."""
    left = int(W * left_ratio)
    right = int(W * right_ratio)
    for i in range(len(x_list) - 1):
        a, b = x_list[i], x_list[i + 1]
        if a <= left and b >= right:
            return (a, b)
    candidates = [(abs((a + b) // 2 - (left + right) // 2), (a, b)) for a, b in zip(x_list[:-1], x_list[1:])]
    return min(candidates, key=lambda t: t[0])[1]


# ---------- Etapa C: OCR matrícula (whitelist dígitos, PSM 7) ----------

def ocr_matricula(cell_bgr: np.ndarray) -> str:
    """OCR só dígitos na célula (whitelist 0123456789, PSM 7)."""
    if pytesseract is None:
        return ""
    gray = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2GRAY)
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    thr = 255 - thr
    config = r"--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789"
    txt = pytesseract.image_to_string(thr, config=config)
    return "".join(c for c in txt if c.isdigit())


# ---------- Etapa D: presença de assinatura (score densidade) ----------

def assinatura_presente(
    cell_bgr: np.ndarray,
    score_threshold: float = 0.003,
) -> Tuple[bool, float]:
    """
    Recorta célula, remove linhas da tabela, mede densidade de tinta.
    Calibre 1 vez: ~30 linhas (15 sem, 15 com assinatura) e escolha o corte.
    Em geral 0.002–0.01 funciona.
    """
    thr = binarizar(cell_bgr)
    v, h = extrair_linhas(thr)
    linhas = cv2.bitwise_or(v, h)
    sem_linhas = cv2.bitwise_and(thr, cv2.bitwise_not(linhas))
    sem_linhas = cv2.medianBlur(sem_linhas, 3)
    ink = np.count_nonzero(sem_linhas)
    area = sem_linhas.shape[0] * sem_linhas.shape[1]
    score = ink / max(1, area)
    return (score > score_threshold), float(score)


# ---------- Pipeline completo: warp → grade → por linha: matrícula + assinatura ----------

def extrair_matricula_e_presenca(
    img_bgr: np.ndarray,
    target_w: int = 2200,
    ratio_matricula: Tuple[float, float] = (0.10, 0.25),
    ratio_assinatura: Tuple[float, float] = (0.55, 0.85),
    score_threshold_assinatura: float = 0.003,
    skip_linhas_cabecalho: int = 2,
    min_altura_linha: int = 25,
    min_digitos_matricula: int = 4,
) -> List[Dict]:
    """
    Pipeline à prova de foto torta:
    Etapa A — warp (perspectiva + redimensionar)
    Etapa B — grade por morfologia (xs, ys)
    Por linha (pulando cabeçalho): OCR célula matrícula, score célula assinatura.

    Args:
        img_bgr: Imagem BGR (foto do documento).
        target_w: Largura alvo após warp (1800–2500 recomendado).
        ratio_matricula: (left_ratio, right_ratio) da faixa da coluna matrícula (ex. 10%–25%).
        ratio_assinatura: (left_ratio, right_ratio) da faixa da coluna assinatura (ex. 55%–85%).
        score_threshold_assinatura: Corte para considerar assinado (calibre; típico 0.002–0.01).
        skip_linhas_cabecalho: Quantas linhas horizontais pular no topo (cabeçalho).
        min_altura_linha: Ignorar faixas verticais menores que isso (ruído).
        min_digitos_matricula: Só incluir resultado se matrícula tiver >= N dígitos.

    Returns:
        Lista de dicts: matricula, assinou, score_assinatura.
    """
    warped = preprocess_and_warp(img_bgr, target_w=target_w)
    thr = binarizar(warped)
    vmask, hmask = extrair_linhas(thr)
    xs = get_vertical_x(vmask)
    ys = get_horizontal_y(hmask)
    W = warped.shape[1]

    x_mat1, x_mat2 = pick_band(xs, ratio_matricula[0], ratio_matricula[1], W)
    x_ass1, x_ass2 = pick_band(xs, ratio_assinatura[0], ratio_assinatura[1], W)

    resultados = []
    for i in range(skip_linhas_cabecalho, len(ys) - 1):
        y1, y2 = ys[i], ys[i + 1]
        if (y2 - y1) < min_altura_linha:
            continue
        cell_mat = crop(warped, x_mat1, x_mat2, y1, y2)
        cell_ass = crop(warped, x_ass1, x_ass2, y1, y2)
        matricula = ocr_matricula(cell_mat)
        assinou, score = assinatura_presente(cell_ass, score_threshold=score_threshold_assinatura)
        if len(matricula) >= min_digitos_matricula:
            resultados.append({
                "matricula": matricula,
                "assinou": assinou,
                "score_assinatura": round(score, 6),
            })
    return resultados
