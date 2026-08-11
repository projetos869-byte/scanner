# Scanner — Documentação completa

Documento único com tudo que compõe o scanner, o que cada arquivo faz e os detalhes de uso.

---

## 1. Visão geral

O **scanner** é um programa que:

1. Recebe o caminho da **planilha Excel** (obrigatório) e da **pasta de imagens** (lista de presença).
2. Faz OCR com **Tesseract** (sem rede neural) para extrair **matrícula** e **nome**; OpenCV verifica apenas se o campo de assinatura está preenchido.
3. Gera um **CSV** com 3 colunas: **Nome_Treinamento**, **Matrícula** e **Nome** (apenas linhas com assinatura preenchida; não valida a assinatura).
4. **Não edita** o Excel; a planilha (ex.: `controle_treinamentos_profissional.xltm` com macro) importa o CSV e trata o resto (PRESENÇA, MATRIZ_CONTROLE, etc.).

**Planilha:** uso com `controle_treinamentos_profissional.xltm` (ou .xlsx). O Excel chama o exe via VBA passando `--excel` e `--images`.

---

## 2. Estrutura de arquivos do scanner

```
scanner/
├── scanner_cli.py          # Ponto de entrada (main); argumentos; orquestra OCR e CSV
├── ler_documento_completo.py  # OCR de matrículas e nomes com Tesseract
├── extrair_cabecalho.py    # Nome do treinamento e data no cabeçalho do documento
├── planilha_relacional.py  # gerar_csv_presenca, obter_nome_treinamento; estrutura de abas
├── preprocessamento_scan.py   # Normalização de imagem (warp, A4, deskew)
├── pipeline_foto_torta.py  # Grade da tabela; detecção de assinatura por linha
├── build_exe.bat           # Gera scanner.exe com PyInstaller
├── requirements.txt        # Dependências Python
├── EXCEL_CHAMAR_SCANNER.md # Instruções para o usuário (Excel, VBA, pasta imagens)
└── SCANNER_COMPLETO.md     # Este arquivo
```

**Pasta de uso (onde o usuário coloca):**

- Pasta `scanner` (copiada de `scanner\dist\scanner`, contendo o EXE e suas dependências)
- `controle_treinamentos_profissional.xltm` (ou .xlsx)
- Pasta `imagens/` com as fotos da lista de presença (.png, .jpg)

---

## 3. Dependências (requirements.txt)

| Pacote      | Versão   | Uso |
|------------|----------|-----|
| opencv-python | >=4.8.0 | Leitura de imagem, warp, morfologia, Canny |
| numpy      | >=1.24.0 | Arrays e operações em imagem |
| pandas     | >=2.0.0  | DataFrame; CSV e leitura do Excel |
| openpyxl   | >=3.1.0  | Ler/escrever Excel (planilha_relacional) |
| pytesseract | >=0.3.10 | OCR (Tesseract) |
| Pillow     | >=10.0.0 | Imagem (suporte a formatos) |

**Build:** PyInstaller (e opcionalmente pywin32).

---

## 4. Fluxo do programa (passo a passo)

1. **Entrada**
   - `--excel` (obrigatório): caminho da planilha.
   - `--images`: pasta ou arquivo de imagem (padrão: pasta `imagens` ao lado do exe).
   - `--data`, `--id-treinamento`: para modo relacional (gerar CSV).
   - `--abrir-excel` / `--no-abrir-excel`: abrir ou não a planilha ao terminar.

2. **Lista de imagens**
   - Se `--images` for pasta: busca `.png`, `.jpg`, `.jpeg`, `.bmp` ordenados.
   - Se for arquivo: usa só esse arquivo.
   - Se não houver imagens: só abre o Excel (se existir) e termina.

3. **OCR**
   - Uma imagem: `extrair_matriculas_e_assinaturas(imagem, faixa_x, ratio_assinatura, ...)`.
   - Várias: `extrair_matriculas_e_assinaturas_varias_folhas(lista, ...)`.
   - Parâmetros fixos: `faixa_x=(0.05, 0.38)`, `ratio_assinatura=(0.55, 0.80)`, `score_threshold_assinatura=0.018`, `min_digitos=4`, `max_digitos=7`, `matriculas_manuscritas=False`.

4. **Matrículas presentes**
   - Coluna `matricula` do DataFrame retornado pelo OCR → lista de strings (quem assinou).

5. **Modo relacional** (se `--data` e `--id-treinamento` forem passados)
   - Nome do treinamento: 1) OCR do cabeçalho (`extrair_cabecalho_documento(primeira)`), 2) aba TREINAMENTOS da planilha (`obter_nome_treinamento`), 3) fallback = ID.
   - Gera CSV: `gerar_csv_presenca(data, id_treinamento, matriculas_presentes, nome_treinamento=..., pasta_saida=_SCRIPT_DIR)`.
   - Nome do arquivo: `presenca_{ID}_{data}.csv` (ex.: `presenca_FO0603060006_25-02-2026.csv`).

6. **Encerramento**
   - Se `--abrir-excel` e o arquivo da planilha existir: `os.startfile(caminho_excel)`.

---

## 5. Detalhamento por arquivo

### 5.1 scanner_cli.py

- **Função:** ponto de entrada do exe; argumentos; orquestra imagens → OCR → CSV.
- **Funções principais:**
  - `_obter_lista_imagens(entrada)`: monta lista de caminhos de imagens (pasta, arquivo ou lista).
  - `main()`: parse dos argumentos, chamada ao OCR, geração do CSV (se modo relacional), abertura do Excel.
- **Diretório de trabalho:** ao rodar, o script usa a pasta do exe (ou do .py) como `_SCRIPT_DIR` e troca o cwd para ela.

### 5.2 ler_documento_completo.py

- **Função:** OCR de página inteira com Tesseract; extração de matrícula e nome, mais verificação do preenchimento da assinatura com OpenCV.
- **Principais funções:**
  - `_ocr_pagina_inteira_tesseract(imagem)`: idem com Tesseract (por).
  - `_eh_matricula_valida(txt, min_len, max_len, manuscrito)`: valida e normaliza dígitos (5–7 dígitos; manuscrito: 3–8 e normalização O→0, l→1, etc.).
  - `extrair_todas_matriculas(imagem, faixa_x, ...)`: filtra detecções por faixa horizontal (coluna de matrícula) e valida matrícula.
  - `extrair_todas_matriculas_com_retry(imagem, ...)`: tenta com e sem normalização e escolhe o melhor resultado.
  - `_adicionar_assinaturas_por_linha(df, imagem, ...)`: usa `pipeline_foto_torta.assinatura_presente` por linha para marcar presença de assinatura.
  - `extrair_matriculas_e_assinaturas(imagem, faixa_x, ratio_assinatura, score_threshold_assinatura, ...)`: pipeline completo (matrículas + assinaturas) para uma imagem.
  - `extrair_matriculas_e_assinaturas_varias_folhas(lista_imagens, ...)`: mesma lógica para várias folhas.
- **Dependências locais:** `preprocessamento_scan` (normalizar_para_scan, A4_200_DPI), `pipeline_foto_torta` (assinatura_presente).

### 5.3 extrair_cabecalho.py

- **Função:** extrair do **cabeçalho** do documento (faixa superior) o **nome do treinamento** e a **data**.
- **Constantes:** `PALAVRAS_TREINAMENTO`, `REGEX_DATA`.
- **Principais funções:**
  - `_ocr_topo_imagem(imagem, fracao_topo=0.22)`: OCR Tesseract na faixa superior.
  - `extrair_cabecalho_documento(caminho_ou_imagem, fracao_topo)`: retorna `(nome_treinamento, data_treinamento)`.

### 5.4 planilha_relacional.py

- **Função:** funções ligadas à planilha (ler abas, obter nome do treinamento, **gerar CSV**). O scanner **não** escreve na planilha; só gera o CSV.
- **Funções usadas pelo scanner:**
  - `obter_nome_treinamento(caminho_excel, id_treinamento)`: lê a aba TREINAMENTOS e retorna o Nome para o ID (colunas ID/Nome ou ID_Treinamento/Nome_Treinamento).
  - `gerar_csv_presenca(data, id_treinamento, matriculas_presentes, nome_treinamento=None, pasta_saida=None)`: gera o CSV com 2 colunas (Nome_Treinamento, Matrícula), separador `;`, encoding UTF-8-sig. Nome do arquivo: `presenca_{id_treinamento}_{data}.csv`.
- **Outras funções (não usadas pelo fluxo atual do exe):** `criar_estrutura_profissional`, `ler_funcionarios`, `ler_treinamentos`, `ler_presenca`, `adicionar_presenca_ocr`, `atualizar_dashboard` (úteis para scripts ou planilha modelo).

### 5.5 preprocessamento_scan.py

- **Função:** pré-processamento de imagem (foto de celular → “scan”): correção de perspectiva (warp), redimensionamento (A4 ou largura alvo), deskew, binarização.
- **Constantes:** `A4_200_DPI`, `A4_300_DPI`, `LARGURA_PADRAO_WARP`.
- **Função principal:** `normalizar_para_scan(imagem, tamanho_a4, target_width, aplicar_deskew, aplicar_binarizacao, retornar_bgr)`.
- **Uso:** chamado por `ler_documento_completo` e por `pipeline_foto_torta` (warp).

### 5.6 pipeline_foto_torta.py

- **Função:** pipeline “à prova de foto torta”: warp (se disponível via preprocessamento_scan), grade da tabela por morfologia, extração de matrícula e **presença de assinatura** por faixas.
- **Funções usadas pelo scanner:**
  - `assinatura_presente(cell_bgr, score_threshold)`: detecta se há assinatura na célula (retorna booleano e score).
- **Outras:** `preprocess_and_warp`, `extrair_linhas`, `get_vertical_x`, `get_horizontal_y`, `pick_band`, `ocr_matricula`, `extrair_matricula_e_presenca` (usadas internamente ou por `ler_documento_completo`).

---

## 6. Argumentos da linha de comando

| Argumento | Obrigatório | Descrição |
|-----------|-------------|-----------|
| `--excel` / `-e` | **Sim** | Caminho da planilha (ex.: controle_treinamentos_profissional.xltm com macro). |
| `--images` / `-i` | Não | Pasta de imagens ou um arquivo; padrão: pasta `imagens` ao lado do exe. |
| `--data` / `-d` | Não* | Data do treinamento (ex.: 25/02/2026). *Obrigatório para gerar CSV (modo relacional). |
| `--id-treinamento` / `-t` | Não* | ID do treinamento (ex.: T01 ou FO0603060006). *Obrigatório para gerar CSV. |
| `--abrir-excel` | Não | Abre a planilha ao terminar (padrão: sim). |
| `--no-abrir-excel` | Não | Não abre o Excel (útil para testes). |

Exemplo completo:

```batch
scanner.exe --excel "C:\pasta\controle_treinamentos_profissional.xltm" --images "C:\pasta\imagens" --data 25/02/2026 --id-treinamento FO0603060006
```

---

## 7. Formato do CSV gerado

- **Nome do arquivo:** `presenca_{ID_Treinamento}_{data}.csv`  
  Ex.: `presenca_FO0603060006_25-02-2026.csv`
- **Colunas (2):** `Nome_Treinamento` ; `Matrícula`
- **Encoding:** UTF-8 com BOM (utf-8-sig).
- **Separador:** `;` (ponto e vírgula).
- **Conteúdo:** uma linha por matrícula **presente** (quem o OCR identificou na lista de presença). O nome do treinamento vem do cabeçalho (OCR), da aba TREINAMENTOS ou do ID.

Exemplo:

```csv
Nome_Treinamento;Matrícula
CONTROLE DE PARTICIPAÇÃO EM TREINAMENTO;140398
CONTROLE DE PARTICIPAÇÃO EM TREINAMENTO;155194
```

---

## 8. Gerar o executável (scanner.exe)

1. Instalar dependências: `pip install -r requirements.txt`
2. Na pasta `scanner` (PowerShell): `.\build_exe.bat`
3. O exe é gerado em: `scanner\dist\scanner\scanner.exe`
4. O PyInstaller usa `--onedir`, `--noconsole` e `--noupx`. O modo pasta evita a extração automática em diretório temporário feita por `--onefile`, reduzindo falsos positivos de antivírus.

Copie a pasta `dist\scanner` inteira para a pasta onde estão a planilha e as imagens. Não distribua somente o EXE. Em ambiente corporativo, a solução definitiva é assinar digitalmente o executável com um certificado confiável.

---

## 9. Uso com Excel (VBA)

- A planilha deve ter **macro** (ex.: .xltm ou .xlsm) e chamar o exe com `Shell` passando **obrigatoriamente** `--excel` com o caminho completo da própria planilha (ex.: `ThisWorkbook.FullName`).
- Exemplo de comando montado no VBA:

  `scanner.exe --excel "C:\pasta\controle_treinamentos_profissional.xltm" --images "C:\pasta\imagens" --data 25/02/2026 --id-treinamento FO0603060006`

- Depois de rodar o scanner, o usuário **importa o CSV** na aba ListaScanner (ex.: Dados → Obter dados → Arquivo de texto/CSV). O resto (PRESENÇA, MATRIZ_CONTROLE, etc.) fica por conta da planilha e das fórmulas/macro.

Para instruções detalhadas (botão, pasta imagens, estrutura das abas), ver **EXCEL_CHAMAR_SCANNER.md**.

---

## 10. Resumo rápido

| Item | Descrição |
|------|-----------|
| **Entrada** | Planilha (--excel obrigatório), pasta de imagens (--images), opcionalmente --data e --id-treinamento. |
| **Processamento** | OCR Tesseract em `ler_documento_completo` + `extrair_cabecalho`; detecção de campo preenchido em `pipeline_foto_torta`. |
| **Saída** | CSV com Nome_Treinamento e Matrícula (só presentes), na pasta do exe. |
| **Planilha** | Controle treinamento profissional (.xltm/.xlsx); o scanner não edita a planilha. |
| **Exe** | `.\build_exe.bat` → `dist\scanner\scanner.exe`; distribuir a pasta inteira. |

Este arquivo (**SCANNER_COMPLETO.md**) é a documentação técnica única do scanner com tudo que é utilizado e os detalhes descritos acima.
