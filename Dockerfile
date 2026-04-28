# ================== STAGE 1: Builder ==================
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ================== STAGE 2: Runtime ==================
FROM python:3.12-slim AS runtime

RUN useradd -m -u 1000 injector

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY main.py .
COPY logger.py .
COPY config.yml .

RUN chown -R injector:injector /app

USER injector

EXPOSE 3110

CMD ["python", "main.py"]