r"""
Ponto de entrada para o scanner.exe.
Fluxo: Excel chama o exe → exe faz OCR → atualiza a planilha Excel → abre/salva e fecha.

Uso:
  scanner.exe [--excel "C:\caminho\controle.xlsx"] [--images "C:\pasta\imagens"]
  Ou sem argumentos: usa controle_treinamentos.xlsx na pasta do exe e pasta "imagens".
"""

import os
import sys
import argparse
import subprocess

# Pasta do exe (quando congelado) ou do script
if getattr(sys, "frozen", False):
    _SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != _SCRIPT_DIR:
    os.chdir(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)


def _obter_lista_imagens(entrada):
    """Retorna lista de caminhos de imagens (arquivo, pasta ou lista)."""
    exts = (".png", ".jpg", ".jpeg", ".bmp")
    if entrada is None:
        # Padrão: pasta "imagens" ao lado do exe/script
        pasta = os.path.join(_SCRIPT_DIR, "imagens")
        if os.path.isdir(pasta):
            return [os.path.join(pasta, f) for f in sorted(os.listdir(pasta)) if f.lower().endswith(exts)]
        return []
    if isinstance(entrada, (list, tuple)):
        return [p for p in entrada if isinstance(p, str) and os.path.exists(p)]
    if os.path.isfile(entrada):
        return [entrada]
    if os.path.isdir(entrada):
        exts = (".png", ".jpg", ".jpeg", ".bmp")
        return [os.path.join(entrada, f) for f in sorted(os.listdir(entrada)) if f.lower().endswith(exts)]
    return []


def main():
    parser = argparse.ArgumentParser(description="Scanner: OCR de documentos → gera CSV para a planilha Excel")
    parser.add_argument("--excel", "-e", required=True, help="Caminho da planilha Excel (ex.: controle_treinamentos_profissional.xltm com macro)")
    parser.add_argument("--images", "-i", default=None, help="Pasta de imagens ou arquivo (padrão: pasta 'imagens')")
    parser.add_argument("--data", "-d", default=None, help="Data do treinamento (ex: 25/02/2026) — modo relacional")
    parser.add_argument("--id-treinamento", "-t", default=None, help="ID do treinamento (ex: T01 ou FO0603060006) — modo relacional")
    parser.add_argument("--abrir-excel", action="store_true", default=True, help="Abrir Excel ao terminar")
    parser.add_argument("--no-abrir-excel", dest="abrir_excel", action="store_false", help="Não abrir Excel (útil para testes)")
    args = parser.parse_args()

    caminho_excel = args.excel
    lista = _obter_lista_imagens(args.images)
    modo_relacional = args.data and args.id_treinamento

    if not lista:
        if args.abrir_excel and os.path.exists(caminho_excel):
            os.startfile(caminho_excel)
        return 0

    # OCR
    from ler_documento_completo import (
        extrair_matriculas_e_assinaturas,
        extrair_matriculas_e_assinaturas_varias_folhas,
    )
    from extrair_cabecalho import extrair_cabecalho_documento

    usar_varias = len(lista) > 1
    primeira = lista[0]
    if usar_varias:
        df = extrair_matriculas_e_assinaturas_varias_folhas(
            lista, faixa_x=(0.095, 0.21), ratio_assinatura=(0.55, 0.80),
            score_threshold_assinatura=0.018, min_digitos=4, max_digitos=7,
            matriculas_manuscritas=False,
        )
    else:
        df = extrair_matriculas_e_assinaturas(
            primeira, faixa_x=(0.095, 0.21), ratio_assinatura=(0.55, 0.80),
            score_threshold_assinatura=0.018, min_digitos=4, max_digitos=7,
            matriculas_manuscritas=False,
        )
        if not df.empty:
            df.insert(0, "folha", 1)
            df.insert(1, "arquivo", os.path.basename(primeira))

    if df.empty:
        if args.abrir_excel and os.path.exists(caminho_excel):
            os.startfile(caminho_excel)
        return 0

    # Matrículas presentes (quem estava na lista de presença lida pelo OCR)
    presentes = df[df["assinou"] == True].copy() if "assinou" in df.columns else df.copy()
    matriculas_presentes = presentes["matricula"].astype(str).str.strip().tolist()

    # Só gera CSV no modo relacional (--data e --id-treinamento); planilha = controle_treinamentos_profissional
    if modo_relacional:
        from planilha_relacional import gerar_csv_presenca, obter_nome_treinamento
        data_str = args.data.strip()
        id_treino = args.id_treinamento.strip()
        nome_treino, _ = extrair_cabecalho_documento(primeira)
        if not nome_treino:
            nome_treino = obter_nome_treinamento(caminho_excel, id_treino)
        if not nome_treino:
            nome_treino = id_treino
        gerar_csv_presenca(
            data_str, id_treino, matriculas_presentes,
            nome_treinamento=nome_treino, pasta_saida=_SCRIPT_DIR,
        )

    if args.abrir_excel and os.path.exists(caminho_excel):
        os.startfile(caminho_excel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
