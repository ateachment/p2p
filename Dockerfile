FROM python:3.11-slim

WORKDIR /usr/src/app

# install curl and clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["python", "./publishSomePeerIPs.py"]  # Fallback, wird überschrieben durch docker-compose.yml, um den Bootstrap-Server zu starten
