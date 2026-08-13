"""
Estratégia: ler TODO o documento com OCR (página inteira) e extrair TODAS as matrículas.
Usa Tesseract com bbox; filtra por posição (coluna MATRÍCULA) e padrão (5–7 dígitos).
Objetivo: fazer funcionar e mostrar todas as matrículas.
"""

import os
import re
from typing import List, Dict, Optional, Tuple, Union
import cv2
import numpy as np
import pandas as pd

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _SCRIPT_DIR:
    os.chdir(_SCRIPT_DIR)

from preprocessamento_scan import normalizar_para_scan, A4_200_DPI


def _digitos(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


# Confusões comuns em OCR de manuscrito: letra → dígito
_NORM_MANUSCRITO = str.maketrans({
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "l": "1", "I": "1", "i": "1", "L": "1", "|": "1",
    "Z": "2", "z": "2", "S": "5", "s": "5",
    "B": "8", "G": "6", "g": "6",
})


def _normalizar_texto_manuscrito(txt: str) -> str:
    """
    Normaliza texto lido de matrícula manuscrita: troca letras que o OCR confunde com dígitos.
    Depois retorna só o que for dígito (ou foi convertido).
    """
    if not txt:
        return ""
    t = txt.strip().translate(_NORM_MANUSCRITO)
    return "".join(c for c in t if c.isdigit())


def _eh_matricula_valida(
    txt: str,
    min_len: int = 5,
    max_len: int = 7,
    manuscrito: bool = False,
) -> Optional[str]:
    """
    Retorna só dígitos se tiver min_len–max_len caracteres; senão None.
    Se manuscrito=True, aceita 3–8 dígitos e normaliza O→0, l→1, S→5, etc.
    """
    if manuscrito:
        dig = _normalizar_texto_manuscrito(txt)
        if 3 <= len(dig) <= 8:
            return dig
        return None
    dig = _digitos(txt)
    if min_len <= len(dig) <= max_len:
        return dig
    return None


def _preprocessar_para_manuscrito(imagem: np.ndarray) -> np.ndarray:
    """
    Pré-processamento para melhorar OCR de matrículas manuscritas:
    escala de cinza, CLAHE (contraste), fechamento morfológico leve (unir traços).
    """
    if len(imagem.shape) == 3:
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    else:
        gray = imagem.copy()
    try:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
    except Exception:
        pass
    kernel = np.ones((2, 2), np.uint8)
    gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _ocr_pagina_inteira_tesseract(
    imagem: np.ndarray,
    config: str = "--oem 1 --psm 6",
) -> List[Tuple[float, float, str, float]]:
    """
    Tesseract image_to_data na página inteira. Retorna (center_x, center_y, texto, conf/100).
    """
    try:
        import pytesseract
    except ImportError:
        return []
    if len(imagem.shape) == 3:
        gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    else:
        gray = imagem
    try:
        d = pytesseract.image_to_data(
            gray, lang="por", config=config, output_type=pytesseract.Output.DICT
        )
    except Exception:
        try:
            d = pytesseract.image_to_data(
                gray, config=config, output_type=pytesseract.Output.DICT
            )
        except Exception:
            return []
    n = len(d.get("text", []))
    if n == 0:
        return []
    out = []
    for i in range(n):
        txt = (d.get("text") or [""])[i]
        if not txt or not txt.strip():
            continue
        left = int((d.get("left") or [0])[i])
        top = int((d.get("top") or [0])[i])
        ww = int((d.get("width") or [0])[i])
        hh = int((d.get("height") or [0])[i])
        conf = int((d.get("conf") or [0])[i])
        if conf <= 0:
            continue
        cx = left + ww / 2
        cy = top + hh / 2
        out.append((cx, cy, txt.strip(), conf / 100.0))
    return out


def extrair_todas_matriculas(
    caminho_ou_imagem: Union[str, np.ndarray],
    faixa_x: Tuple[float, float] = (0.095, 0.21),
    min_digitos: int = 4,
    max_digitos: int = 7,
    normalizar_imagem: bool = True,
    ignorar_cabecalho: bool = True,
    altura_cabecalho_px: int = 80,
    matriculas_manuscritas: bool = False,
) -> pd.DataFrame:
    """
    Lê o documento inteiro com OCR e extrai todas as matrículas.
    - Se matriculas_manuscritas=True: pré-processa imagem (CLAHE, morfologia) e aceita 3–8 dígitos
      com normalização O→0, l→1, S→5, etc., para matrículas escritas à mão.
    - Filtra detecções: centro x na faixa (coluna MATRÍCULA); ordena por y e remove duplicatas.
    """
    if isinstance(caminho_ou_imagem, np.ndarray):
        img = caminho_ou_imagem.copy()
    else:
        if not os.path.exists(caminho_ou_imagem):
            return pd.DataFrame()
        img = cv2.imread(caminho_ou_imagem)
    if img is None or img.size == 0:
        return pd.DataFrame()
    if normalizar_imagem:
        img = normalizar_para_scan(img, tamanho_a4=A4_200_DPI, aplicar_binarizacao=False)
    if matriculas_manuscritas:
        img = _preprocessar_para_manuscrito(img)
    h, w = img.shape[:2]
    x_min = int(w * faixa_x[0])
    x_max = int(w * faixa_x[1])
    # Lê somente a coluna de matrícula. Além de ser mais rápido, evita que textos
    # das demais colunas confundam o OCR. O eixo Y continua igual ao da folha.
    coluna_matricula = img[:, x_min:x_max]
    # As fotos enviadas costumam ter apenas 130–170 px nessa coluna. Ampliar
    # antes do OCR preserva os traços dos dígitos e melhora muito a leitura.
    escala_ocr = 3.0
    coluna_ampliada = cv2.resize(
        coluna_matricula,
        None,
        fx=escala_ocr,
        fy=escala_ocr,
        interpolation=cv2.INTER_CUBIC,
    )
    deteccoes_coluna = _ocr_pagina_inteira_tesseract(
        coluna_ampliada,
        config=(
            "--oem 1 --psm 4 -c tessedit_char_whitelist=0123456789 "
            "-c user_defined_dpi=300"
        ),
    )
    deteccoes = [
        (cx / escala_ocr + x_min, cy / escala_ocr, texto, conf)
        for cx, cy, texto, conf in deteccoes_coluna
    ]
    if not deteccoes:
        return pd.DataFrame()
    mn, mx = (3, 8) if matriculas_manuscritas else (min_digitos, max_digitos)
    candidatos = []
    for cx, cy, texto, conf in deteccoes:
        if not (x_min <= cx <= x_max):
            continue
        mat = _eh_matricula_valida(texto, min_len=mn, max_len=mx, manuscrito=matriculas_manuscritas)
        if mat is None:
            continue
        candidatos.append({"y": cy, "x": cx, "matricula": mat, "confianca": conf})
    if not candidatos:
        return pd.DataFrame()
    # Ordenar por y (linha); agrupar só detecções na MESMA linha (tol_y pequeno para não juntar linhas distintas)
    candidatos.sort(key=lambda r: r["y"])
    linhas_agrupadas = []
    # Linhas da tabela costumam ter 50–80 px de distância; tol_y menor que metade para não fundir duas linhas
    tol_y = min(32, max(12, h // 65))
    i = 0
    while i < len(candidatos):
        r = candidatos[i]
        grupo = [r]
        j = i + 1
        while j < len(candidatos) and abs(candidatos[j]["y"] - r["y"]) <= tol_y:
            grupo.append(candidatos[j])
            j += 1
        # Na mesma linha: ficar com a de maior confiança (evita duplicata do mesmo número)
        melhor = max(grupo, key=lambda x: (x["confianca"], -abs(len(x["matricula"]) - 5)))
        linhas_agrupadas.append(melhor)
        i = j
    # Ignorar primeira linha se for cabeçalho (y no topo; limite relativo à altura)
    limite_cabecalho = min(altura_cabecalho_px, max(40, h // 10))
    if ignorar_cabecalho and linhas_agrupadas and linhas_agrupadas[0]["y"] < limite_cabecalho:
        linhas_agrupadas = linhas_agrupadas[1:]
    rows = []
    for idx, r in enumerate(linhas_agrupadas, 1):
        rows.append({
            "linha": idx,
            "matricula": r["matricula"],
            "confianca": round(r["confianca"], 4),
            "x_centro": int(r["x"]),
            "y_centro": int(r["y"]),
        })
    return pd.DataFrame(rows)


def _merge_resultados_por_y_relativo(
    df1: pd.DataFrame, h1: int, df2: pd.DataFrame, h2: int, tol_rel: float = 0.018
) -> pd.DataFrame:
    """
    União por posição relativa (y/h): mesma linha em imagens de alturas diferentes
    fica na mesma faixa. Evita 23 matrículas (duplicatas) quando uma era normalizada e outra crua.
    """
    if df1.empty and df2.empty:
        return pd.DataFrame()
    if df1.empty:
        return df2.reset_index(drop=True)
    if df2.empty:
        return df1.reset_index(drop=True)
    rows = []
    for _, r in df1.iterrows():
        y_rel = r["y_centro"] / max(1, h1)
        rows.append({"y_rel": y_rel, "y": r["y_centro"], "matricula": r["matricula"], "confianca": r["confianca"], "x": r["x_centro"]})
    for _, r in df2.iterrows():
        y_rel = r["y_centro"] / max(1, h2)
        rows.append({"y_rel": y_rel, "y": r["y_centro"], "matricula": r["matricula"], "confianca": r["confianca"], "x": r["x_centro"]})
    rows.sort(key=lambda x: x["y_rel"])
    merged = []
    i = 0
    while i < len(rows):
        r = rows[i]
        grupo = [r]
        j = i + 1
        while j < len(rows) and abs(rows[j]["y_rel"] - r["y_rel"]) <= tol_rel:
            grupo.append(rows[j])
            j += 1
        melhor = max(grupo, key=lambda x: (x["confianca"], -abs(len(x["matricula"]) - 5)))
        merged.append(melhor)
        i = j
    merged.sort(key=lambda x: x["y_rel"])
    return pd.DataFrame([
        {"linha": i + 1, "matricula": r["matricula"], "confianca": round(r["confianca"], 4), "x_centro": r["x"], "y_centro": r["y"]}
        for i, r in enumerate(merged)
    ])


def extrair_todas_matriculas_com_retry(
    caminho_ou_imagem: Union[str, np.ndarray],
    faixa_x: Tuple[float, float] = (0.095, 0.21),
    min_digitos: int = 4,
    max_digitos: int = 7,
    unir_normalizado_e_cru: bool = True,
    retornar_imagem_usada: bool = False,
    matriculas_manuscritas: bool = False,
) -> Union[pd.DataFrame, Tuple[pd.DataFrame, np.ndarray]]:
    """
    Extrai matrículas rodando COM e SEM normalização; fica com o resultado que tiver
    mais linhas (e sem duplicar matrícula). Se retornar_imagem_usada=True, retorna (df, img)
    para poder recortar células de assinatura na mesma imagem.
    """
    if isinstance(caminho_ou_imagem, np.ndarray):
        img = caminho_ou_imagem.copy()
        path = None
    else:
        if not os.path.exists(caminho_ou_imagem):
            return (pd.DataFrame(), np.array([])) if retornar_imagem_usada else pd.DataFrame()
        img = cv2.imread(caminho_ou_imagem)
        path = caminho_ou_imagem
    if img is None or img.size == 0:
        return (pd.DataFrame(), np.array([])) if retornar_imagem_usada else pd.DataFrame()
    # Tentativa rápida na imagem original. Mantém as proporções reais da tabela
    # e evita que um recorte parcial seja deformado para o formato A4.
    df_cru = extrair_todas_matriculas(
        img,
        faixa_x=faixa_x,
        min_digitos=min_digitos,
        max_digitos=max_digitos,
        normalizar_imagem=False,
        matriculas_manuscritas=matriculas_manuscritas,
    )
    if not df_cru.empty or not unir_normalizado_e_cru:
        if retornar_imagem_usada:
            return df_cru, img
        return df_cru

    # Fallback: somente se a imagem original não produzir nenhuma matrícula,
    # corrige perspectiva e tenta mais uma vez.
    img_norm = normalizar_para_scan(
        img, tamanho_a4=None, target_width=1800, aplicar_binarizacao=False
    )
    df_norm = extrair_todas_matriculas(
        img_norm,
        faixa_x=faixa_x,
        min_digitos=min_digitos,
        max_digitos=max_digitos,
        normalizar_imagem=False,
        matriculas_manuscritas=matriculas_manuscritas,
    )
    if retornar_imagem_usada:
        return df_norm, img_norm
    return df_norm


def _adicionar_assinaturas_por_linha(
    img: np.ndarray,
    df: pd.DataFrame,
    ratio_assinatura: Tuple[float, float] = (0.55, 0.80),
    score_threshold_assinatura: float = 0.018,
) -> pd.DataFrame:
    """
    Para cada linha do df (y_centro), recorta a célula da coluna ASSINATURA e
    detecta se está assinada. Adiciona colunas assinou e score_assinatura.
    """
    if img is None or img.size == 0 or df.empty or "y_centro" not in df.columns:
        df = df.copy()
        df["assinou"] = False
        df["score_assinatura"] = 0.0
        return df
    try:
        from pipeline_foto_torta import assinatura_presente
    except ImportError:
        df = df.copy()
        df["assinou"] = False
        df["score_assinatura"] = 0.0
        return df
    h, w = img.shape[:2]
    x1 = int(w * ratio_assinatura[0])
    x2 = int(w * ratio_assinatura[1])
    ys = df["y_centro"].values
    n = len(ys)
    assinou_list = []
    score_list = []
    for i in range(n):
        yc = int(ys[i])
        if n == 1:
            dy = max(25, h // 12)
        elif i == 0:
            # Primeira linha: recorte mais conservador para não pegar linha da tabela ou linha de baixo
            dy = max(20, int((ys[1] - yc) * 0.4))
        elif i == n - 1:
            dy = max(25, (yc - ys[i - 1]) // 2)
        else:
            dy = max(25, min(ys[i + 1] - yc, yc - ys[i - 1]) // 2)
        y1 = max(0, yc - dy)
        y2 = min(h, yc + dy)
        cell = img[y1:y2, x1:x2]
        if cell.size == 0:
            assinou_list.append(False)
            score_list.append(0.0)
            continue
        assinou, score = assinatura_presente(cell, score_threshold=score_threshold_assinatura)
        assinou_list.append(assinou)
        score_list.append(round(score, 6))
    out = df.copy()
    out["assinou"] = assinou_list
    out["score_assinatura"] = score_list
    return out


def extrair_matriculas_e_assinaturas(
    caminho_ou_imagem: Union[str, np.ndarray],
    faixa_x: Tuple[float, float] = (0.095, 0.21),
    ratio_assinatura: Tuple[float, float] = (0.55, 0.80),
    score_threshold_assinatura: float = 0.018,
    min_digitos: int = 4,
    max_digitos: int = 7,
    matriculas_manuscritas: bool = False,
) -> pd.DataFrame:
    """
    Passo 1: extrai todas as matrículas (com/sem normalização, melhor resultado).
    Passo 2: para cada linha, recorta a célula ASSINATURA e detecta se está assinada.
    Se matriculas_manuscritas=True: pré-processa e normaliza O→0, l→1, etc. para matrículas à mão.
    """
    df, img_used = extrair_todas_matriculas_com_retry(
        caminho_ou_imagem,
        faixa_x=faixa_x,
        min_digitos=min_digitos,
        max_digitos=max_digitos,
        # Imagem original primeiro; normalização apenas como fallback se o OCR
        # não encontrar nenhuma matrícula.
        unir_normalizado_e_cru=True,
        retornar_imagem_usada=True,
        matriculas_manuscritas=matriculas_manuscritas,
    )
    if df.empty:
        return df
    return _adicionar_assinaturas_por_linha(
        img_used,
        df,
        ratio_assinatura=ratio_assinatura,
        score_threshold_assinatura=score_threshold_assinatura,
    )


def extrair_matriculas_e_assinaturas_varias_folhas(
    lista_caminhos: List[str],
    faixa_x: Tuple[float, float] = (0.095, 0.21),
    ratio_assinatura: Tuple[float, float] = (0.55, 0.80),
    score_threshold_assinatura: float = 0.018,
    min_digitos: int = 4,
    max_digitos: int = 7,
    matriculas_manuscritas: bool = False,
) -> pd.DataFrame:
    """
    Processa várias folhas (imagens) de uma vez.
    Para cada caminho em lista_caminhos, extrai matrículas e assinaturas e concatena
    os resultados em um único DataFrame com colunas folha e arquivo.
    """
    if not lista_caminhos:
        return pd.DataFrame()
    listas = []
    for idx, caminho in enumerate(lista_caminhos, 1):
        if not os.path.exists(caminho):
            continue
        df = extrair_matriculas_e_assinaturas(
            caminho,
            faixa_x=faixa_x,
            ratio_assinatura=ratio_assinatura,
            score_threshold_assinatura=score_threshold_assinatura,
            min_digitos=min_digitos,
            max_digitos=max_digitos,
            matriculas_manuscritas=matriculas_manuscritas,
        )
        if df.empty:
            df = pd.DataFrame(columns=["linha", "matricula", "confianca", "x_centro", "y_centro", "assinou", "score_assinatura"])
        df.insert(0, "folha", idx)
        df.insert(1, "arquivo", os.path.basename(caminho))
        listas.append(df)
    if not listas:
        return pd.DataFrame()
    return pd.concat(listas, ignore_index=True)


def main():
    import sys
    script_dir = os.path.dirname(os.path.abspath(__file__))
    padrao_img = os.path.join(script_dir, "img_teste.png")
    img = sys.argv[1] if len(sys.argv) > 1 else padrao_img
    saida = sys.argv[2] if len(sys.argv) > 2 else "matriculas_completo.xlsx"
    if not os.path.exists(img):
        print("Uso: python ler_documento_completo.py  [caminho_imagem] [saida.xlsx]")
        print("Padrão: img_teste.png na pasta scanner. Não encontrado:", img)
        return
    print("Lendo documento completo (OCR na página inteira)...")
    df = extrair_todas_matriculas_com_retry(img, unir_normalizado_e_cru=True)
    if df.empty:
        print("Nenhuma matrícula encontrada.")
        return
    df.to_excel(saida, index=False)
    print(f"\nTotal: {len(df)} matrículas")
    print(df.to_string(index=False))
    print(f"\nSalvo em: {saida}")


if __name__ == "__main__":
    main()
