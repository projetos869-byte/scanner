"""
API OCR do Scanner — para deploy no Render.
Recebe imagens via POST /scan e devolve somente as matrículas das linhas assinadas.
"""

import os
import sys
import io

# Pasta do scanner (mesmo nível que main.py)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_SCANNER_DIR = os.path.join(_APP_DIR, "scanner")
if _SCANNER_DIR not in sys.path:
    sys.path.insert(0, _SCANNER_DIR)
os.chdir(_APP_DIR)

from typing import Annotated

import numpy as np
import cv2
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, Response
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


def _gerar_csv_string(matriculas: list[str]) -> str:
    """Gera uma única coluna de matrículas para colar ou abrir no Excel."""
    import csv
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerow(["Matrícula"])
    for matricula in matriculas:
        writer.writerow([matricula])
    return "\ufeff" + buf.getvalue()  # BOM para Excel abrir em UTF-8


@app.get("/")
def root():
    """Página web para selecionar uma pasta, processar e copiar as matrículas."""
    return FileResponse(os.path.join(_APP_DIR, "web", "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "api": "scanner-ocr"}


def _resposta_csv_ou_json(
    request: Request,
    retorno: str | None,
    csv_body: str,
    erro: str | None,
    nome_arquivo: str,
    quantidade: int = 0,
    matriculas: list[str] | None = None,
    quantidade_lidas: int = 0,
):
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
    matriculas = matriculas or []
    out = {
        "csv": csv_body,
        "nome_arquivo": nome_arquivo,
        "quantidade": quantidade,
        "quantidade_lidas": quantidade_lidas,
        "matriculas": matriculas,
    }
    if erro:
        out["erro"] = erro
    return out


@app.post("/scan")
def scan(
    request: Request,
    images: Annotated[list[UploadFile], File(description="Arquivo(s) de imagem — use o botão Choose File")],
    data: str = Form("lista"),
    id_treinamento: str = Form("matriculas"),
    retorno: str | None = Form(None),
):
    """
    Recebe **arquivos de imagem** da lista de presença (multipart/form-data), data e id do treinamento.
    Campo obrigatório: **images** — um ou mais arquivos de imagem (não texto).
    Retorna JSON ou CSV (se retorno=csv ou Accept: text/csv) para a aba ListaScanner.
    """
    data_arq = data.replace("/", "-").replace(".", "-").strip()
    nome_arquivo = f"presenca_{id_treinamento}_{data_arq}.csv"
    csv_vazio = "\ufeffMatrícula\n"

    from ler_documento_completo import extrair_matriculas_e_assinaturas_lote

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
    faixa_x = (0.095, 0.21)
    ratio_assinatura = (0.55, 0.80)
    score_threshold = 0.018
    min_digitos, max_digitos = 4, 7

    df = extrair_matriculas_e_assinaturas_lote(
        listas_imagens,
        faixa_x=faixa_x,
        ratio_assinatura=ratio_assinatura,
        score_threshold_assinatura=score_threshold,
        min_digitos=min_digitos,
        max_digitos=max_digitos,
    )

    if df.empty:
        csv_str = _gerar_csv_string([])
        return _resposta_csv_ou_json(request, retorno, csv_str, "Nenhuma matrícula encontrada no OCR", nome_arquivo)

    # Só considera presente quem tem assinatura detectada (coluna assinou); se não existir, usa todas as matrículas
    if "assinou" in df.columns:
        df_presentes = df[df["assinou"] == True]
    else:
        df_presentes = df
    matriculas_presentes = df_presentes["matricula"].astype(str).str.strip().tolist()
    csv_str = _gerar_csv_string(matriculas_presentes)
    return _resposta_csv_ou_json(
        request,
        retorno,
        csv_str,
        None,
        nome_arquivo,
        len(matriculas_presentes),
        matriculas_presentes,
        len(df),
    )
