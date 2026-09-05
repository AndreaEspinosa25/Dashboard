FROM python:3.11-slim

# Evitar que Python escriba archivos .pyc y forzar salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias primero para aprovechar la caché de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Exponer el puerto por defecto (Render lo sobreescribirá en tiempo de ejecución)
EXPOSE 8501

# Ejecutar Streamlit. 
# Usamos sh -c para asegurarnos de que la variable de entorno $PORT se resuelva.
# Render asigna $PORT dinámicamente. Si no está definida (ej: localmente), usa 8501.
CMD ["sh", "-c", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]
