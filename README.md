# scannerWeb

API de OCR do Scanner (listas de presença) — roda em Docker / Render. O Excel (VBA) envia as imagens e recebe os dados direto na aba ListaScanner.

## Uso rápido

- **Docker:** `docker compose up --build` → API em http://localhost:8000
- **Excel:** Configure a URL da API no VBA e use o botão que envia as imagens da pasta e preenche a ListaScanner

Ver [DOCKER.md](DOCKER.md) e [scanner/EXCEL_VBA_CHAMAR_API.md](scanner/EXCEL_VBA_CHAMAR_API.md).
