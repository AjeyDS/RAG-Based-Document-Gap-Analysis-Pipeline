FROM python:3.11-slim-bullseye

RUN apt-get update && apt-get install -y libpq-dev gcc libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Install CPU-only torch before docling so pip doesn't pull the CUDA variant (~2 GB) as a transitive dep
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/

COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

RUN mkdir -p /app/data/uploads/kb

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
