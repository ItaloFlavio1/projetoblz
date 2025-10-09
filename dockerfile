# Usar uma imagem oficial do Python como base
FROM python:3.11-slim

# Definir o diretório de trabalho dentro do contêiner
WORKDIR /app

# Instalar as dependências de sistema necessárias para o WeasyPrint
# O apt-get é o gestor de pacotes do Debian/Ubuntu (usado na imagem Python)
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copiar o ficheiro de dependências do Python primeiro
COPY requirements.txt .

# Instalar as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o resto do código da aplicação
COPY . .

# Expor a porta que a aplicação vai usar
EXPOSE 5000

# Comando para iniciar a aplicação quando o contêiner arrancar
# Gunicorn é um servidor WSGI pronto para produção
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
