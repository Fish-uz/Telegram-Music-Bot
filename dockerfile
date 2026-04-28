# 1. Usamos una imagen ligera de Python
FROM python:3.10-slim

# 2. Instalamos FFmpeg (necesario para procesar el audio)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# 3. Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Copiamos el archivo de requerimientos primero (optimiza la caché de Docker)
COPY requirements.txt .

# 5. Instalamos las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiamos el resto del código del bot
COPY . .

# 7. Comando para iniciar el bot
CMD ["python", "main.py"]