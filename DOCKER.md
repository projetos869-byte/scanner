# Rodar o Scanner OCR em Docker

A API pode ser construída e executada com Docker (local ou em cloud, ex.: Render com Native Docker).

---

## Pré-requisito

- [Docker](https://docs.docker.com/get-docker/) instalado (e opcionalmente Docker Compose).

---

## Build e execução

### Opção 1: Docker Compose (recomendado local)

Na pasta do projeto (onde está o `Dockerfile` e o `docker-compose.yml`):

```bash
docker compose up --build
```

- A API sobe em **http://localhost:8000**
- Documentação interativa: **http://localhost:8000/docs**
- Para rodar em segundo plano: `docker compose up -d --build`

### Opção 2: Comandos Docker

```bash
# Build da imagem
docker build -t scanner-api .

# Executar o container (porta 8000)
docker run -p 8000:8000 scanner-api
```

Teste:

```bash
curl http://localhost:8000/
# Resposta: {"api":"scanner-ocr","endpoint":"POST /scan"}
```

---

## Envio de imagens para a API (ex.: teste local)

Exemplo com `curl` (substitua pelos seus arquivos e pasta):

```bash
curl -X POST http://localhost:8000/scan \
  -F "data=25/02/2026" \
  -F "id_treinamento=FO0603060006" \
  -F "retorno=csv" \
  -F "images=@scanner/imagem_teste.png"
```

O corpo da resposta é o CSV (Nome_Treinamento; Matrícula). O Excel VBA pode apontar para `http://localhost:8000` (ou para a URL do Render em produção).

---

## Deploy no Render com Docker

1. No [Render](https://render.com), crie um **Web Service**.
2. Conecte o repositório (GitHub/GitLab).
3. Em **Environment**, escolha **Docker**.
4. Render usa o `Dockerfile` na raiz do repositório; não é necessário definir Build Command nem Start Command (o `Dockerfile` já define o `CMD`).
5. A variável `PORT` é definida pelo Render; o `Dockerfile` já usa `ENV PORT=8000` e `uvicorn ... --port ${PORT}`.

Se a imagem ficar pesada ou demorar para iniciar, pode ser necessário ajustar o plano (memória) ou o uso do EasyOCR/PyTorch.

---

## Estrutura esperada no build

O build espera na raiz do projeto:

- `Dockerfile`
- `requirements.txt`
- `main.py`
- Pasta `scanner/` com os módulos Python do OCR (`ler_documento_completo.py`, `extrair_cabecalho.py`, etc.)

Arquivos e pastas listados no `.dockerignore` (build do exe, planilhas, imagens de teste, etc.) não entram na imagem.
