# Deploy da API Scanner no Render

## 1. Criar Web Service no Render

1. Acesse [render.com](https://render.com) e crie um **Web Service**.
2. Conecte o repositório (GitHub/GitLab) ou faça deploy manual.

---

## Opção A: Deploy com Docker (recomendado)

| Campo | Valor |
|-------|--------|
| **Environment** | **Docker** |
| **Branch** | `main` (ou a branch do projeto) |

O Render usa o `Dockerfile` na raiz do repositório. Não é necessário definir Build Command nem Start Command — o `Dockerfile` já instala dependências (incluindo Tesseract) e sobe a API com `uvicorn`. A variável `PORT` é injetada pelo Render.

---

## Opção B: Deploy com Python (sem Docker)

| Campo | Valor |
|-------|--------|
| **Runtime** | Python 3 |
| **Root Directory** | *(deixe em branco)* |

### Build

| Campo | Valor |
|-------|--------|
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

*Nota:* No ambiente Python nativo do Render pode ser necessário configurar o Tesseract (depende do stack). Com **Docker** o Tesseract já vem na imagem.

### Observações

- **Tesseract:** prefira o deploy Docker deste projeto, pois a imagem já instala o OCR e o idioma português.
- **Plano gratuito:** o serviço pode dormir após inatividade; a primeira abertura pode demorar alguns segundos.

## 3. Abrir a página

Após o deploy, abra a URL do serviço no navegador:

```
https://scanner-api.onrender.com
```

A página permite selecionar uma pasta de imagens, processar e copiar as matrículas. O endpoint usado internamente continua disponível:

```
POST https://scanner-api.onrender.com/scan
```

## 4. Teste rápido (PowerShell)

```powershell
$uri = "https://scanner-api.onrender.com/scan"
$boundary = [System.Guid]::NewGuid().ToString()
# Montar multipart com imagens + data + id_treinamento (exemplo com um arquivo)
# Ou use Postman/Insomnia para testar.
```

Para testar somente a saúde da aplicação:

```powershell
Invoke-RestMethod -Uri "https://scanner-api.onrender.com/health" -Method Get
```

Resposta esperada: `{"status":"ok","api":"scanner-ocr"}`.
