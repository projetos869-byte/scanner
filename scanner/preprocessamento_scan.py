"""
Pré-processamento: foto de celular → "scan padrão" (à prova de foto torta).

Pipeline Etapa A — Corrigir perspectiva (ordem importa):
  1. Grayscale
  2. Blur leve
  3. (Opcional) Fechamento morfológico antes do Canny — cola bordas quebradas
  4. Canny (bordas) — parâmetros 60–180 recomendados
  5. Fechar buracos nas bordas (dilate 3x3)
  6. Achar maior contorno retangular (folha ou, em fallback, a tabela)
  7. warpPerspective para "endireitar"
  8. Redimensionar para tamanho padrão (A4 ou largura fixa 1800–2500 px)
  9. Deskew + binarização (no fluxo principal)

Se não achar a folha: tenta a "tabela" (segundo retângulo grande) ou fallback sem warp.
"""

import cv2
import numpy as np
from typing import Optional, Tuple

# Tamanhos A4 virtuais (proporção 1:sqrt(2))
A4_200_DPI = (1654, 2339)   # width, height
A4_300_DPI = (2480, 3508)
# Largura alvo alternativa (como no pipeline recomendado: 1800–2500 px)
LARGURA_PADRAO_WARP = 2200


def _maior_contorno_retangular(
    imagem: np.ndarray,
    canny_low: int = 60,
    canny_high: int = 180,
    usar_fechamento_morfologico: bool = True,
    area_minima_folha: int = 10000,
    area_minima_tabela: int = 5000,
) -> Optional[np.ndarray]:
    """
    Encontra o maior contorno que se aproxima de um quadrilátero (folha ou tabela).
    - Fechamento morfológico antes do Canny ajuda quando bordas estão quebradas.
    - Se não achar "folha" (area_minima_folha), tenta "tabela" (area_minima_tabela).
    Retorna os 4 pontos (não ordenados).
    """
    if len(imagem.shape) == 3:
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    else:
        gray = imagem.copy()

    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Opcional: fechamento morfológico antes do Canny (cola bordas quebradas)
    if usar_fechamento_morfologico:
        kernel_close = np.ones((5, 5), np.uint8)
        blur = cv2.morphologyEx(blur, cv2.MORPH_CLOSE, kernel_close)

    edged = cv2.Canny(blur, canny_low, canny_high)
    # Fechar buracos nas bordas (como no pipeline recomendado)
    edged = cv2.dilate(edged, np.ones((3, 3), np.uint8), iterations=1)

    contornos, _ = cv2.findContours(
        edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    contornos = sorted(contornos, key=cv2.contourArea, reverse=True)

    # Primeiro: procurar folha (maior retângulo) nos top 10
    melhor_quad = None
    for cnt in contornos[:10]:
        area = cv2.contourArea(cnt)
        if area < area_minima_folha:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            melhor_quad = approx.reshape(4, 2)
            break

    # Fallback: procurar "a tabela" (retângulo grande com área menor)
    if melhor_quad is None and area_minima_tabela < area_minima_folha:
        for cnt in contornos[:15]:
            area = cv2.contourArea(cnt)
            if area < area_minima_tabela:
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                melhor_quad = approx.reshape(4, 2)
                break

    if melhor_quad is None:
        # Último fallback: limiar adaptativo (documentos com pouco contraste)
        thresh = cv2.adaptiveThreshold(
            blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        contornos2, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        contornos2 = sorted(contornos2, key=cv2.contourArea, reverse=True)
        for cnt in contornos2[:10]:
            area = cv2.contourArea(cnt)
            if area < area_minima_tabela:
                continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4:
                melhor_quad = approx.reshape(4, 2)
                break

    return melhor_quad


def _ordenar_pontos(pts: np.ndarray) -> np.ndarray:
    """
    Ordena 4 pontos na ordem: top-left, top-right, bottom-right, bottom-left.
    """
    pts = np.array(pts, dtype=np.float32)
    # Ordenar por y: os dois primeiros são o "topo", os dois últimos a "base"
    ordem_y = np.argsort(pts[:, 1])
    topo = pts[ordem_y[:2]]
    base = pts[ordem_y[2:]]
    # No topo: menor x = top-left, maior x = top-right
    topo = topo[np.argsort(topo[:, 0])]
    tl, tr = topo[0], topo[1]
    # Na base: menor x = bottom-left, maior x = bottom-right
    base = base[np.argsort(base[:, 0])]
    bl, br = base[0], base[1]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _warp_perspectiva(imagem: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Aplica transformação de perspectiva para retificar a folha."""
    pts = _ordenar_pontos(pts)
    (tl, tr, br, bl) = pts

    largura_superior = np.linalg.norm(tr - tl)
    largura_inferior = np.linalg.norm(br - bl)
    w = max(int(largura_superior), int(largura_inferior))

    altura_esq = np.linalg.norm(bl - tl)
    altura_dir = np.linalg.norm(br - tr)
    h = max(int(altura_esq), int(altura_dir))

    dst = np.array([
        [0, 0],
        [w - 1, 0],
        [w - 1, h - 1],
        [0, h - 1]
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(imagem, M, (w, h), flags=cv2.INTER_LINEAR)


def _deskew(imagem: np.ndarray) -> np.ndarray:
    """
    Corrige pequena inclinação (skew) da folha já retificada.
    Usa minAreaRect para estimar o ângulo.
    """
    if len(imagem.shape) == 3:
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    else:
        gray = imagem.copy()

    # Binarizar para detectar ângulo
    binario = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 10
    )
    coords = np.column_stack(np.where(binario == 0))
    if coords.size < 100:
        return imagem

    angle = cv2.minAreaRect(coords)[-1]
    # minAreaRect retorna -90 a 0; normalizar para rotação em torno de 0
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    # Só corrigir se inclinação relevante (evitar tremores)
    if abs(angle) < 0.3:
        return imagem

    h, w = imagem.shape[:2]
    centro = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(centro, angle, 1.0)
    return cv2.warpAffine(
        imagem, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE
    )


def _normalizar_tamanho(
    imagem: np.ndarray,
    largura: int,
    altura: int,
    manter_proporcao: bool = False
) -> np.ndarray:
    """
    Redimensiona para o tamanho alvo (ex.: A4 virtual).
    Se manter_proporcao=True, encaixa na caixa mantendo proporção e faz padding.
    """
    h, w = imagem.shape[:2]
    if manter_proporcao:
        scale = min(largura / w, altura / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(imagem, (nw, nh), interpolation=cv2.INTER_LINEAR)
        # Padding para atingir exatamente largura x altura
        pad_w = (largura - nw) // 2
        pad_h = (altura - nh) // 2
        result = np.ones((altura, largura), dtype=imagem.dtype) * 255
        if len(imagem.shape) == 3:
            result = np.stack([result] * 3, axis=-1)
        result[pad_h:pad_h + nh, pad_w:pad_w + nw] = resized
        return result
    return cv2.resize(imagem, (largura, altura), interpolation=cv2.INTER_LINEAR)


def _binarizar_adaptativo(imagem: np.ndarray) -> np.ndarray:
    """Binarização com threshold adaptativo (scan padrão)."""
    if len(imagem.shape) == 3:
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    else:
        gray = imagem.copy()

    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=15,
        C=10
    )


def normalizar_para_scan(
    imagem: np.ndarray,
    tamanho_a4: Optional[Tuple[int, int]] = None,
    target_width: Optional[int] = None,
    aplicar_deskew: bool = True,
    aplicar_binarizacao: bool = True,
    retornar_bgr: bool = True,
    usar_fechamento_morfologico: bool = True,
    canny_low: int = 60,
    canny_high: int = 180,
) -> np.ndarray:
    """
    Pipeline completo: foto → scan padrão (à prova de foto torta).
    Etapa A: perspectiva (folha ou tabela) + warp + redimensionar (A4 ou largura fixa 1800–2500).

    Args:
        imagem: Imagem BGR (OpenCV) ou grayscale.
        tamanho_a4: (largura, altura) do A4 virtual. Se None e target_width não informado, usa A4_200_DPI.
        target_width: Se informado, redimensiona por largura fixa (ex.: 2200) mantendo proporção (recomendado 1800–2500).
        aplicar_deskew: Se True, corrige inclinação após o warp.
        aplicar_binarizacao: Se True, aplica threshold adaptativo no final.
        retornar_bgr: Se True, retorna 3 canais (BGR).
        usar_fechamento_morfologico: Se True, faz fechamento morfológico antes do Canny (cola bordas quebradas).
        canny_low, canny_high: Limiares do Canny (recomendado 60–180).

    Returns:
        Imagem normalizada (reto, tamanho padrão, binária ou cinza).
    """
    if imagem is None or imagem.size == 0:
        return imagem

    if tamanho_a4 is None and target_width is None:
        tamanho_a4 = A4_200_DPI

    # 1. Tons de cinza
    if len(imagem.shape) == 3:
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    else:
        gray = imagem.copy()

    # 2. Blur leve (reduzir ruído)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # 3 e 4. Contorno da folha (ou tabela) + perspectiva
    quad = _maior_contorno_retangular(
        imagem,
        canny_low=canny_low,
        canny_high=canny_high,
        usar_fechamento_morfologico=usar_fechamento_morfologico,
    )
    if quad is not None:
        # Warp na imagem colorida (ou cinza) para preservar qualidade
        img_warp = _warp_perspectiva(imagem, quad)
    else:
        # Fallback: usar imagem com blur (reduz ruído), sem warp
        if len(imagem.shape) == 3:
            img_warp = cv2.cvtColor(blur, cv2.COLOR_GRAY2BGR)
        else:
            img_warp = blur

    # 5. Deskew
    if aplicar_deskew:
        img_warp = _deskew(img_warp)

    # 6. Normalizar tamanho: largura fixa (ex. 2200) ou A4 virtual
    h, w = img_warp.shape[:2]
    if target_width is not None:
        scale = target_width / w
        new_w = target_width
        new_h = int(h * scale)
        img_norm = cv2.resize(img_warp, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    elif tamanho_a4 is not None:
        largura, altura = tamanho_a4
        img_norm = _normalizar_tamanho(img_warp, largura, altura, manter_proporcao=True)
    else:
        img_norm = img_warp

    # 7. Binarizar
    if aplicar_binarizacao:
        img_final = _binarizar_adaptativo(img_norm)
    else:
        if len(img_norm.shape) == 3:
            img_final = cv2.cvtColor(img_norm, cv2.COLOR_BGR2GRAY)
        else:
            img_final = img_norm

    if retornar_bgr and len(img_final.shape) == 2:
        img_final = cv2.cvtColor(img_final, cv2.COLOR_GRAY2BGR)

    return img_final


def normalizar_arquivo_para_scan(
    caminho_entrada: str,
    caminho_saida: Optional[str] = None,
    tamanho_a4: Tuple[int, int] = A4_200_DPI,
    **kwargs
) -> np.ndarray:
    """
    Carrega uma imagem do disco, aplica o pipeline de normalização e,
    opcionalmente, salva o resultado.

    Args:
        caminho_entrada: Caminho da foto (ex.: celular).
        caminho_saida: Se informado, salva a imagem normalizada neste caminho.
        tamanho_a4: (largura, altura) A4 virtual.
        **kwargs: Repassados para normalizar_para_scan.

    Returns:
        Imagem normalizada (numpy array).
    """
    img = cv2.imread(caminho_entrada)
    if img is None:
        raise FileNotFoundError(f"Não foi possível carregar: {caminho_entrada}")

    result = normalizar_para_scan(img, tamanho_a4=tamanho_a4, **kwargs)

    if caminho_saida:
        cv2.imwrite(caminho_saida, result)

    return result
