# scannerWeb

Aplicação web para listas de presença, pronta para Docker/Render. Abra o link, selecione a pasta de imagens e copie as matrículas das linhas com o campo de assinatura preenchido. Usa uma única leitura Tesseract restrita à coluna de matrícula e OpenCV para o campo de assinatura, sem rede neural e sem validar a assinatura.

## Uso rápido

- **Docker:** `docker compose up --build` → página em http://localhost:8000
- **Excel:** Configure a URL da API no VBA e use o botão que envia as imagens da pasta e preenche a ListaScanner

Ver [DOCKER.md](DOCKER.md) e [scanner/EXCEL_VBA_CHAMAR_API.md](scanner/EXCEL_VBA_CHAMAR_API.md).
