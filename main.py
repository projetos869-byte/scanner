"""
API OCR do Scanner — para deploy no Render.
Recebe imagens + data + id_treinamento via POST /scan e devolve CSV (Nome_Treinamento; Matrícula).
Compatível com a aba ListaScanner da planilha Excel.
"""

import os
import sys
import io
import warnings

# Pasta do scanner (mesmo nível que main.py)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_SCANNER_DIR = os.path.join(_APP_DIR, "scanner")
if _SCANNER_DIR not in sys.path:
    sys.path.insert(0, _SCANNER_DIR)
os.chdir(_APP_DIR)

# Suprimir avisos do PyTorch/EasyOCR
warnings.filterwarnings("ignore", message=".*pin_memory.*", category=UserWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="torch")

from typing import Annotated

import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Scanner OCR API", version="1.0")


def _custom_openapi():
    """Garante que o campo 'images' no /scan seja schema de arquivo (format: binary) no Swagger."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    # Ajustar requestBody do POST /scan para images = array de arquivo (binary)
    for path, path_item in (schema.get("paths") or {}).items():
        if path != "/scan":
            continue
        post = path_item.get("post")
        if not post:
            continue
        content = post.get("requestBody", {}).get("content", {}).get("multipart/form-data")
        if not content or "schema" not in content:
            continue
        props = content["schema"].get("properties") or {}
        if "images" in props:
            props["images"] = {
                "type": "array",
                "items": {"type": "string", "format": "binary"},
                "description": "Arquivo(s) de imagem (PNG, JPG, etc.) — use Choose File",
            }
        break
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bytes_to_image(content: bytes) -> np.ndarray | None:
    """Converte bytes da imagem em array para OpenCV."""
    arr = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _gerar_csv_string(nome_treinamento: str, matriculas: list[str]) -> str:
    """Gera CSV no formato da ListaScanner: Nome_Treinamento; Matrícula (UTF-8 com BOM)."""
    buf = io.StringIO()
    buf.write("Nome_Treinamento;Matrícula\n")
    for m in matriculas:
        buf.write(f"{nome_treinamento};{m}\n")
    return "\ufeff" + buf.getvalue()  # BOM para Excel abrir em UTF-8


@app.get("/")
def root():
    return {"api": "scanner-ocr", "endpoint": "POST /scan"}


def _resposta_csv_ou_json(request: Request, retorno: str | None, csv_body: str, erro: str | None, nome_arquivo: str, quantidade: int = 0):
    """Se o cliente pediu CSV (retorno=csv ou Accept: text/csv), retorna Response CSV; senão JSON."""
    accept = (request.headers.get("accept") or "").lower()
    quer_csv = (retorno or "").strip().lower() == "csv" or "text/csv" in accept
    if quer_csv:
        # BOM já está em csv_body; codificar como UTF-8 (sem utf-8-sig para não duplicar BOM)
        return Response(
            content=csv_body.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="{nome_arquivo}"'},
        )
    out = {"csv": csv_body, "nome_arquivo": nome_arquivo, "quantidade": quantidade}
    if erro:
        out["erro"] = erro
    return out


@app.post("/scan")
def scan(
    request: Request,
    data: str = Form(...),
    id_treinamento: str = Form(...),
    nome_treinamento: str | None = Form(None),
    retorno: str | None = Form(None),
    images: Annotated[list[UploadFile], File(description="Arquivo(s) de imagem — use o botão Choose File")],
):
    """
    Recebe **arquivos de imagem** da lista de presença (multipart/form-data), data e id do treinamento.
    Campo obrigatório: **images** — um ou mais arquivos de imagem (não texto).
    Retorna JSON ou CSV (se retorno=csv ou Accept: text/csv) para a aba ListaScanner.
    """
    data_arq = data.replace("/", "-").replace(".", "-").strip()
    nome_arquivo = f"presenca_{id_treinamento}_{data_arq}.csv"
    csv_vazio = "\ufeffNome_Treinamento;Matrícula\n"

    from ler_documento_completo import extrair_matriculas_e_assinaturas

    # Ordenar por nome para manter ordem das folhas
    imagens_ordenadas = sorted(images, key=lambda f: (f.filename or "").lower())
    if not imagens_ordenadas:
        return _resposta_csv_ou_json(request, retorno, csv_vazio, "Nenhuma imagem enviada", nome_arquivo)

    # Ler cada arquivo de imagem (bytes) e converter para array OpenCV
    listas_imagens = []
    for up in imagens_ordenadas:
        content = up.file.read()
        img = _bytes_to_image(content)
        if img is not None and img.size > 0:
            listas_imagens.append(img)

    if not listas_imagens:
        return _resposta_csv_ou_json(request, retorno, csv_vazio, "Nenhuma imagem válida", nome_arquivo)

    # OCR com a mesma lógica do scanner_cli
    faixa_x = (0.05, 0.38)
    ratio_assinatura = (0.50, 0.88)
    score_threshold = 0.018
    min_digitos, max_digitos = 4, 7

    if len(listas_imagens) == 1:
        df = extrair_matriculas_e_assinaturas(
            listas_imagens[0],
            faixa_x=faixa_x,
            ratio_assinatura=ratio_assinatura,
            score_threshold_assinatura=score_threshold,
            min_digitos=min_digitos,
            max_digitos=max_digitos,
            usar_easyocr=True,
            matriculas_manuscritas=False,
        )
    else:
        # Várias folhas: precisamos de caminhos para a função atual; usar temp ou passar arrays
        # A função varias_folhas espera lista de caminhos. Precisamos verificar assinatura.
        # extrair_matriculas_e_assinaturas aceita Union[str, np.ndarray] — então podemos
        # chamar extrair_matriculas_e_assinaturas para cada imagem e concatenar, ou
        # ver se varias_folhas aceita só paths. Pelo código, varias_folhas recebe lista_caminhos.
        # Então vamos processar cada imagem e concatenar manualmente.
        listas_df = []
        for idx, img in enumerate(listas_imagens, 1):
            df_one = extrair_matriculas_e_assinaturas(
                img,
                faixa_x=faixa_x,
                ratio_assinatura=ratio_assinatura,
                score_threshold_assinatura=score_threshold,
                min_digitos=min_digitos,
                max_digitos=max_digitos,
                usar_easyocr=True,
                matriculas_manuscritas=False,
            )
            if not df_one.empty:
                df_one.insert(0, "folha", idx)
                listas_df.append(df_one)
        import pandas as pd
        df = pd.concat(listas_df, ignore_index=True) if listas_df else pd.DataFrame()

    if df.empty:
        csv_str = _gerar_csv_string(nome_treinamento or id_treinamento, [])
        return _resposta_csv_ou_json(request, retorno, csv_str, "Nenhuma matrícula encontrada no OCR", nome_arquivo)

    # Só considera presente quem tem assinatura detectada (coluna assinou); se não existir, usa todas as matrículas
    if "assinou" in df.columns:
        df_presentes = df[df["assinou"] == True]
    else:
        df_presentes = df
    matriculas_presentes = df_presentes["matricula"].astype(str).str.strip().tolist()

    # Nome do treinamento: vem do form ou id_treinamento (sem OCR de cabeçalho — reduz tamanho e dependências)
    nome_final = (nome_treinamento or id_treinamento).strip()

    csv_str = _gerar_csv_string(nome_final, matriculas_presentes)
    return _resposta_csv_ou_json(request, retorno, csv_str, None, nome_arquivo, len(matriculas_presentes))
