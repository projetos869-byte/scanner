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

- **Tesseract:** No Render (Linux), o Tesseract pode não estar instalado no sistema. Se der erro de `pytesseract`, você pode:
  - Instalar no Build: adicionar no Build Command algo como `apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-por` (se o Render permitir) ou
  - Usar só EasyOCR (no código dá para tornar o Tesseract opcional).
- **Memória:** O EasyOCR/PyTorch consome bastante RAM. No plano free o serviço pode dormir após inatividade; a primeira requisição pode demorar (cold start).

## 3. URL do serviço

Após o deploy, a URL ficará no formato:

```
https://scanner-api.onrender.com
```

Endpoint do scan:

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

Para testar só se a API está no ar:

```powershell
Invoke-RestMethod -Uri "https://scanner-api.onrender.com/" -Method Get
```

Resposta esperada: `{"api":"scanner-ocr","endpoint":"POST /scan"}`.
