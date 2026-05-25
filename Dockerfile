FROM python:3.12-slim

# Metadata
LABEL org.opencontainers.image.title="aura-frame-downloader"
LABEL org.opencontainers.image.description="Scheduled S3 backup for Aura digital picture frames"

WORKDIR /app

# Install Python dependencies first (layer cache friendly)
COPY requirements-container.txt .
RUN pip install --no-cache-dir -r requirements-container.txt

# Copy only the package code and the container entry point
# (no GUI files, no PyInstaller spec, no build scripts)
COPY aura/ aura/
COPY aura_container.py .

# Run as a non-root user for security
RUN useradd --system --no-create-home aura
USER aura

CMD ["python", "aura_container.py"]
