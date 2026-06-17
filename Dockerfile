FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# FastAPI 앱 구현 후 아래 두 줄 주석 해제
# COPY app/ ./app/
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

CMD ["python", "-c", "print('deundeun backend image ready')"]
