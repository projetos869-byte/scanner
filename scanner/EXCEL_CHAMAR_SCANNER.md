# Chamar o scanner.exe a partir do Excel

## Como rodar

### 1. Com Python (pasta `scanner`)

Abra o terminal na pasta `scanner` e execute:

```batch
cd caminho\do\seu\projeto\scanner

python scanner_cli.py --images "imagem_teste.png" --data 25/02/2026 --id-treinamento T01
```

- **Uma imagem:** use `--images "caminho\arquivo.png"`.
- **Pasta com várias imagens:** use `--images "caminho\pasta_imagens"`.
- **Com planilha:** use `--excel "controle_treinamentos.xlsx"`.
- **Não abrir o Excel ao terminar:** use `--no-abrir-excel`.

O CSV será gerado na mesma pasta do script (ex: `presenca_T01_25-02-2026.csv`).

### 2. Com o .exe (após gerar)

Na pasta `scanner` rode (no PowerShell use `.\build_exe.bat`):

```batch
.\build_exe.bat
```

Depois use:

```batch
dist\scanner\scanner.exe --images "imagens" --data 25/02/2026 --id-treinamento T01
```

Ou copie a pasta `dist\scanner` inteira para a pasta da planilha e use `scanner\scanner.exe`.

### 3. Pelo Excel (botão VBA)

Crie um botão que chama a macro que executa o `scanner.exe` (veja a seção **Botão no Excel (VBA)** mais abaixo). Você informa Data e ID do treinamento; o exe gera o CSV e você importa na ListaScanner.

---

## Estrutura da planilha

### 1️⃣ ABA FUNCIONÁRIOS

| Matrícula | Nome | Setor | Ativo |

### 2️⃣ ABA TREINAMENTOS

Coloque todos os treinamentos (FO) com **ID sem espaço** para evitar erro:

| ID | Nome |
|----|------|
| FO0603060006 | FO 060 306-0006 |
| FO0603060011 | FO 060 306-0011 |
| FO0603060016 | FO 060 306-0016 |

### 3️⃣ ABA PRESENÇA (banco oficial)

Aqui fica tudo registrado — é o coração do sistema:

| Data | ID_Treinamento | Matrícula | Status |
|------|----------------|-----------|--------|
| 25/02/2026 | FO0603060006 | 140398 | OK |

### 4️⃣ ABA MATRIZ_CONTROLE

Matriz com uma coluna por treinamento (ID). Fórmula automática em cada célula:

`=SE(CONT.SES(PRESENÇA!B:B;C$1;PRESENÇA!C:C;$A2)>0;"OK";"")`

- **C$1** = ID do treinamento (ex: FO0603060006)  
- **$A2** = matrícula  
- Se existir no banco PRESENÇA → mostra **OK**

| Matrícula | Nome | FO0603060006 | FO0603060011 | FO0603060016 | ... |
|-----------|------|--------------|--------------|--------------|-----|

### Outras abas

- **ListaScanner** — onde você importa o CSV do scanner (Nome_Treinamento, Matrícula); o resto você faz manual (incluir na PRESENÇA com o ID correto).  
- **Por Treinamento**, **Status por treinamento**, **Faltam por treinamento**, **DASHBOARD** — opcionais; use a **MATRIZ_CONTROLE** como visão principal.  

## O que o scanner faz (só isso)

O scanner **puxa apenas**:
- **Matrículas** (quem assinou / quem estava na lista)
- **Nome do treinamento** (lido do documento pelo OCR)

Gera um CSV com **2 colunas**: **Nome_Treinamento**, **Matrícula**. **O resto você faz manual** no Excel (importar na ListaScanner, fórmulas, quem falta, etc.).

## Fluxo

1. Você chama o scanner (`scanner.exe --data ... --id-treinamento T01 --excel ... --images ...`).  
2. O exe faz OCR e gera o CSV (Nome_Treinamento, Matrícula — só quem assinou).  
3. **Você importa** o CSV na aba **ListaScanner**.  
4. O resto (Por Treinamento, Status, Faltam, PRESENÇA) você configura e usa **manual** no Excel.  

## Onde colocar os arquivos (planilha controle treinamento profissional)

- **pasta scanner** — mesma pasta da planilha, contendo `scanner.exe` e suas dependências.
- **Planilha** — FUNCIONÁRIOS, TREINAMENTOS, PRESENÇA, MATRIZ_CONTROLE, ListaScanner, etc. (crie com `criar_estrutura_profissional` ou use a sua).  
- **imagens** — pasta na mesma pasta da planilha, com as fotos da lista de presença (.png, .jpg).  
- O exe gera o CSV (ex: **presenca_FO0603060006_25-02-2026.csv**) na mesma pasta; importe na aba **ListaScanner**.  

## Botão no Excel (VBA) — ImportarScanner (planilha controle treinamento profissional)

Use este código para a planilha **controle treinamento profissional** (ou qualquer nome). O exe recebe o caminho da planilha e da pasta **imagens**; assim o CSV é gerado na pasta certa e você atualiza a aba ListaScanner.

```vba
Sub ImportarScanner()
    Dim caminhoExe As String
    Dim caminhoPlanilha As String
    Dim pastaImagens As String
    Dim dataHoje As String
    Dim idTreino As String
    Dim cmd As String
    
    caminhoExe = ThisWorkbook.Path & "\scanner\scanner.exe"
    
    If Dir(caminhoExe) = "" Then
        MsgBox "scanner.exe não encontrado!", vbCritical
        Exit Sub
    End If
    
    ' Planilha atual e pasta imagens (mesma pasta do arquivo)
    caminhoPlanilha = ThisWorkbook.FullName
    pastaImagens = ThisWorkbook.Path & "\imagens"
    dataHoje = Format(Date, "dd/mm/yyyy")
    ' ID do treinamento: altere ou use uma célula, ex: Range("B1").Value
    idTreino = "FO0603060006"
    
    cmd = Chr(34) & caminhoExe & Chr(34)
    cmd = cmd & " --excel " & Chr(34) & caminhoPlanilha & Chr(34)
    cmd = cmd & " --images " & Chr(34) & pastaImagens & Chr(34)
    cmd = cmd & " --data " & Chr(34) & dataHoje & Chr(34)
    cmd = cmd & " --id-treinamento " & Chr(34) & idTreino & Chr(34)
    
    Shell cmd, vbNormalFocus
    
    MsgBox "Scanner executado! Atualize a aba ListaScanner (importe o CSV gerado).", vbInformation
End Sub
```

**Para funcionar:**
- **scanner\scanner.exe** na pasta da planilha.
- Pasta **imagens** na mesma pasta, com as fotos da lista de presença (.png, .jpg).
- Ajuste `idTreino` no VBA (ou use `idTreino = Range("B1").Value` para ler de uma célula).
- Depois de rodar, importe o CSV (presenca_ID_data.csv) na aba **ListaScanner**.

---

## Botão alternativo (ExecutarScanner) — com Data e ID em células

Se preferir definir Data e ID do treinamento em células da planilha:

```vba
Sub ExecutarScanner()
    Dim exePath As String, excelPath As String, imagesPath As String, cmd As String
    Dim dataTreino As String, idTreino As String
    
    dataTreino = Format(Date, "dd/mm/yyyy")   ' ou: Range("B1").Value
    idTreino = "T01"   ' ou: Range("B2").Value
    
    excelPath = ThisWorkbook.FullName
    exePath = ThisWorkbook.Path & "\scanner\scanner.exe"
    imagesPath = ThisWorkbook.Path & "\imagens"
    
    If Dir(exePath) = "" Then
        MsgBox "Não encontrado: " & exePath, vbExclamation
        Exit Sub
    End If
    
    cmd = Chr(34) & exePath & Chr(34) & " --excel " & Chr(34) & excelPath & Chr(34)
    cmd = cmd & " --images " & Chr(34) & imagesPath & Chr(34)
    cmd = cmd & " --data " & Chr(34) & dataTreino & Chr(34) & " --id-treinamento " & Chr(34) & idTreino & Chr(34)
    Shell cmd, 1
End Sub
```

## Argumentos do scanner.exe

| Argumento             | Descrição |
|-----------------------|-----------|
| `--excel` / `-e`      | **Obrigatório.** Caminho da planilha (ex.: .xltm com macro) |
| `--images` / `-i`     | Pasta com imagens (padrão: pasta `imagens`) |
| `--data` / `-d`       | Data do treinamento (ex: 25/02/2026) — **modo relacional** |
| `--id-treinamento` / `-t` | ID do treinamento (ex: T01) — **modo relacional** |
| `--abrir-excel`       | Abre o Excel ao terminar (padrão: sim) |

- Se **--data** e **--id-treinamento** forem passados: o exe **só gera** o CSV com **2 colunas** (Nome_Treinamento, Matrícula — só matrículas de quem assinou). O nome do treinamento é lido pelo OCR do documento. O resto você faz manual no Excel.  
- Se não forem passados: o exe usa o modo antigo (Resumo + Presenças).  

Exemplo (modo relacional):

```batch
scanner.exe --excel "C:\Controle\controle.xlsx" --images "C:\Controle\imagens" --data 25/02/2026 --id-treinamento T01
```

## Gerar o .exe

Na pasta `scanner` (no PowerShell use `.\` antes do nome):

```batch
.\build_exe.bat
```

O executável ficará em `dist\scanner\scanner.exe`. Copie a pasta `dist\scanner` inteira para junto da planilha; não copie somente o EXE. O modo pasta reduz falsos positivos de antivírus em comparação com `--onefile`.

## Criar a planilha com as 4 abas (template)

Na pasta `scanner`, execute:

```batch
python -c "from planilha_relacional import criar_estrutura_profissional; criar_estrutura_profissional(); print('Planilha criada: controle_treinamentos.xlsx')"
```

Isso gera a planilha com todas as abas. O CSV do scanner tem só **Nome_Treinamento** e **Matrícula** (coluna A e B na ListaScanner). O resto você ajusta manual.
