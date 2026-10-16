FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. deps first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. only the code the API needs (the UI has its own image)
COPY ticket_agent ./ticket_agent
COPY api ./api
COPY manage.py demo.py ./

RUN useradd -m appuser
USER appuser

EXPOSE 8000

# One worker on purpose: chat history is held in process memory.
# 0.0.0.0 so other containers (and the published port) can reach it.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
                                                