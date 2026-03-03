# Build context: repository root
# docker build -f humanizedoc/backend/Dockerfile .
FROM python:3.11-slim

WORKDIR /app

COPY humanizedoc/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY humanizedoc/ humanizedoc/

EXPOSE 8000

CMD ["uvicorn", "humanizedoc.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
