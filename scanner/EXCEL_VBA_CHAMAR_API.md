# Excel VBA — Chamar a API Scanner no Render

Use este código na planilha **controle_treinamentos_profissional** (ou outra) para: colocar as imagens na pasta → clicar no botão → o scanner (API) faz o trabalho e **as informações voltam direto para a aba ListaScanner**; lá você faz o resto.

---

## 1. Módulo VBA

No VBA do Excel: **Inserir → Módulo** e cole o código abaixo.

Altere a constante `URL_API` para a URL do seu serviço no Render (ex.: `https://scanner-api.onrender.com`).

```vba
Option Explicit

' URL da API no Render (altere após o deploy)
Private Const URL_API As String = "https://scanner-api.onrender.com"

' Coloca imagens na pasta → clica no botão → scanner faz o trabalho e preenche a aba ListaScanner; lá você faz o resto.
Public Sub EnviarScannerAPI()
    Dim pastaImagens As String
    Dim dataTreino As String
    Dim idTreino As String
    Dim ok As Boolean

    pastaImagens = ThisWorkbook.Path & "\imagens"
    If Dir(pastaImagens, vbDirectory) = "" Then
        MsgBox "Pasta não encontrada: " & pastaImagens, vbExclamation
        Exit Sub
    End If
    If Not HaImagensNaPasta(pastaImagens) Then
        MsgBox "Nenhuma imagem (.png, .jpg, .jpeg, .bmp) na pasta: " & pastaImagens, vbExclamation
        Exit Sub
    End If

    dataTreino = Format(Date, "dd/mm/yyyy")
    idTreino = "FO0603060006"   ' ou: idTreino = Trim(Range("B2").Value)

    ok = ChamarAPIePreencherListaScanner(pastaImagens, dataTreino, idTreino)

    If ok Then
        MsgBox "Pronto. Dados na aba ListaScanner. Faça o resto por lá.", vbInformation
    Else
        MsgBox "Erro ao chamar a API ou preencher a ListaScanner. Verifique a pasta de imagens e a URL da API.", vbCritical
    End If
End Sub

' Chama a API, recebe o CSV e preenche a aba ListaScanner (Nome_Treinamento | Matrícula).
Public Function ChamarAPIePreencherListaScanner( _
    ByVal pastaImagens As String, _
    ByVal dataTreino As String, _
    ByVal idTreino As String) As Boolean
    Dim url As String
    Dim body() As Byte
    Dim resp() As Byte
    Dim boundary As String

    url = URL_API & "/scan"
    boundary = "----ScannerBoundary" & Replace(CreateObject("Scriptlet.TypeLib").Guid, "-", "")

    If Not MontarBodyMultipart(pastaImagens, dataTreino, idTreino, boundary, body) Then
        ChamarAPIePreencherListaScanner = False
        Exit Function
    End If

    If Not EnviarPOST(url, boundary, body, resp) Then
        ChamarAPIePreencherListaScanner = False
        Exit Function
    End If

    If Not PreencherAbaListaScanner(resp) Then
        ChamarAPIePreencherListaScanner = False
        Exit Function
    End If

    ChamarAPIePreencherListaScanner = True
End Function

' Verifica se há pelo menos uma imagem na pasta (extensões aceitas pelo scanner).
Private Function HaImagensNaPasta(ByVal pasta As String) As Boolean
    Dim fso As Object, arquivo As Object, pastaObj As Object
    Dim ext As String
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FolderExists(pasta) Then
        HaImagensNaPasta = False
        Exit Function
    End If
    Set pastaObj = fso.GetFolder(pasta)
    HaImagensNaPasta = False
    For Each arquivo In pastaObj.Files
        ext = LCase(fso.GetExtensionName(arquivo.Name))
        If ext = "png" Or ext = "jpg" Or ext = "jpeg" Or ext = "bmp" Then
            HaImagensNaPasta = True
            Exit Function
        End If
    Next arquivo
End Function

' Converte bytes da resposta (CSV UTF-8) em texto, parseia e preenche a aba ListaScanner.
Private Function PreencherAbaListaScanner(ByRef bytesResp() As Byte) As Boolean
    Dim ws As Worksheet
    Dim csvTexto As String
    Dim linhas() As String
    Dim i As Long
    Dim linhaPlanilha As Long
    Dim partes() As String
    Dim nomeAba As String

    On Error GoTo errPreencher

    nomeAba = "ListaScanner"
    On Error Resume Next
    Set ws = ThisWorkbook.Sheets(nomeAba)
    On Error GoTo errPreencher
    If ws Is Nothing Then
        Set ws = ThisWorkbook.Sheets.Add(After:=ThisWorkbook.Sheets(ThisWorkbook.Sheets.Count))
        ws.Name = nomeAba
    End If

    csvTexto = BytesUTF8ParaString(bytesResp)
    If Len(Trim(csvTexto)) = 0 Then
        PreencherAbaListaScanner = False
        Exit Function
    End If

    ' Remove BOM se existir; normaliza quebras de linha
    If Left(csvTexto, 1) = ChrW(65279) Then csvTexto = Mid(csvTexto, 2)
    csvTexto = Replace(csvTexto, vbCrLf, vbLf)
    csvTexto = Replace(csvTexto, vbCr, vbLf)
    linhas = Split(csvTexto, vbLf)
    If UBound(linhas) < 0 Then
        PreencherAbaListaScanner = False
        Exit Function
    End If

    ws.Cells.Clear
    linhaPlanilha = 1
    For i = LBound(linhas) To UBound(linhas)
        If Len(Trim(linhas(i))) = 0 Then GoTo nextLinha
        partes = Split(linhas(i), ";")
        If UBound(partes) >= 1 Then
            ws.Cells(linhaPlanilha, 1).Value = Trim(partes(0))
            ws.Cells(linhaPlanilha, 2).Value = Trim(partes(1))
        ElseIf UBound(partes) = 0 Then
            ws.Cells(linhaPlanilha, 1).Value = Trim(partes(0))
        End If
        linhaPlanilha = linhaPlanilha + 1
nextLinha:
    Next i

    PreencherAbaListaScanner = True
    Exit Function
errPreencher:
    PreencherAbaListaScanner = False
End Function

' Converte array de bytes UTF-8 em string VBA.
Private Function BytesUTF8ParaString(ByRef bytes() As Byte) As String
    Dim st As Object
    If UBound(bytes) < 0 Then
        BytesUTF8ParaString = ""
        Exit Function
    End If
    Set st = CreateObject("ADODB.Stream")
    st.Type = 1
    st.Open
    st.Write bytes
    st.Position = 0
    st.Type = 2
    st.Charset = "UTF-8"
    BytesUTF8ParaString = st.ReadText
    st.Close
End Function

' Monta body multipart/form-data com imagens + data + id_treinamento + retorno=csv
Private Function MontarBodyMultipart( _
    ByVal pastaImagens As String, _
    ByVal dataTreino As String, _
    ByVal idTreino As String, _
    ByVal boundary As String, _
    ByRef outBody() As Byte) As Boolean
    Dim st As Object, stFile As Object
    Dim fso As Object, pasta As Object, arq As Object
    Dim nomeArq As String
    Dim ext As String
    Dim bytes() As Byte
    Dim i As Long

    On Error GoTo errMultipart

    Set st = CreateObject("ADODB.Stream")
    st.Type = 1
    st.Open

    ' Parte: data
    AppendPart st, boundary, "data", dataTreino
    ' Parte: id_treinamento
    AppendPart st, boundary, "id_treinamento", idTreino
    ' Parte: retorno=csv (para a API devolver CSV puro)
    AppendPart st, boundary, "retorno", "csv"

    ' Partes: arquivos de imagem
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set pasta = fso.GetFolder(pastaImagens)
    For Each arq In pasta.Files
        nomeArq = arq.Name
        ext = LCase(fso.GetExtensionName(nomeArq))
        If ext = "png" Or ext = "jpg" Or ext = "jpeg" Or ext = "bmp" Then
            AppendFilePart st, boundary, "images", arq.Path, nomeArq, "image/png"
        End If
    Next arq

    ' Fechamento do boundary
    AppendStringToStream st, vbCrLf & "--" & boundary & "--" & vbCrLf

    st.Position = 0
    outBody = st.Read
    MontarBodyMultipart = True
    Exit Function
errMultipart:
    MontarBodyMultipart = False
End Function

Private Sub AppendPart(ByVal st As Object, ByVal boundary As String, ByVal nomeCampo As String, ByVal valor As String)
    AppendStringToStream st, "--" & boundary & vbCrLf
    AppendStringToStream st, "Content-Disposition: form-data; name=""" & nomeCampo & """" & vbCrLf & vbCrLf
    AppendStringToStream st, valor & vbCrLf
End Sub

Private Sub AppendFilePart(ByVal st As Object, ByVal boundary As String, ByVal nomeCampo As String, ByVal caminhoCompleto As String, ByVal nomeArquivo As String, ByVal contentType As String)
    Dim stFile As Object
    AppendStringToStream st, "--" & boundary & vbCrLf
    AppendStringToStream st, "Content-Disposition: form-data; name=""" & nomeCampo & """; filename=""" & nomeArquivo & """" & vbCrLf
    AppendStringToStream st, "Content-Type: " & contentType & vbCrLf & vbCrLf
    Set stFile = CreateObject("ADODB.Stream")
    stFile.Type = 1
    stFile.Open
    stFile.LoadFromFile caminhoCompleto
    stFile.Position = 0
    st.Write stFile.Read
    stFile.Close
    AppendStringToStream st, vbCrLf
End Sub

Private Sub AppendStringToStream(ByVal st As Object, ByVal s As String)
    Dim stAux As Object
    Set stAux = CreateObject("ADODB.Stream")
    stAux.Type = 2
    stAux.Charset = "UTF-8"
    stAux.Open
    stAux.WriteText s
    stAux.Position = 0
    stAux.Type = 1
    st.Write stAux.Read
    stAux.Close
End Sub

' Envia POST com body e retorna o corpo da resposta em resp()
Private Function EnviarPOST(ByVal url As String, ByVal boundary As String, ByRef body() As Byte, ByRef resp() As Byte) As Boolean
    Dim http As Object
    On Error GoTo errPost
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.Open "POST", url, False
    http.setRequestHeader "Content-Type", "multipart/form-data; boundary=" & boundary
    http.setRequestHeader "Accept", "text/csv"
    http.Send body
    If http.Status <> 200 Then
        EnviarPOST = False
        Exit Function
    End If
    resp = http.ResponseBody
    EnviarPOST = True
    Exit Function
errPost:
    EnviarPOST = False
End Function

Private Function SalvarBytesEmArquivo(ByVal caminho As String, ByRef bytes() As Byte) As Boolean
    Dim st As Object
    On Error GoTo errSave
    Set st = CreateObject("ADODB.Stream")
    st.Type = 1
    st.Open
    st.Write bytes
    st.SaveToFile caminho, 2
    st.Close
    SalvarBytesEmArquivo = True
    Exit Function
errSave:
    SalvarBytesEmArquivo = False
End Function
```

---

## 2. Ajustes importantes

- **URL da API:** altere `URL_API` para a URL do seu Web Service no Render (ex.: `https://scanner-api.onrender.com`).
- **Pasta das imagens:** por padrão usa `ThisWorkbook.Path & "\imagens"`. Coloque as fotos das listas de presença nessa pasta (folha1.png, folha2.png, etc.).
- **Data e ID:** no código está fixo `dataTreino = Format(Date, "dd/mm/yyyy")` e `idTreino = "FO0603060006"`. Pode trocar para células, por exemplo:
  - `dataTreino = Format(Range("B1").Value, "dd/mm/yyyy")`
  - `idTreino = Trim(Range("B2").Value)`

---

## 3. Botão na planilha

1. **Inserir → Formas** (ou **Desenho → Botão**).
2. Desenhe o botão e, quando pedir a macro, escolha **EnviarScannerAPI**.
3. Ao clicar: envia as imagens para a API; o scanner faz o OCR e as informações voltam direto para a aba **ListaScanner**; a mensagem avisa que pode fazer o resto por lá.

---

## 4. Fluxo resumido

1. Você coloca as imagens na pasta `...\imagens` (folha1.png, folha2.png, etc.).
2. Clica no botão no Excel (macro **EnviarScannerAPI**).
3. O scanner (API) faz o trabalho (OCR) e devolve os dados.
4. O VBA preenche a aba **ListaScanner** com Nome_Treinamento e Matrícula.
5. Na ListaScanner você faz o resto (incluir na PRESENÇA, fórmulas, etc.).

Corrigindo o VBA: o boundary precisa ser o mesmo no body e no header. Então vamos gerar o boundary em `ChamarAPIeSalvarCSV` e passar para `MontarBodyMultipart` e para `EnviarPOST`.
<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
StrReplace