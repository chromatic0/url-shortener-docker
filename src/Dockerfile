FROM python:3.13-slim
WORKDIR /src

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 4242

RUN useradd --no-create-home app
USER app

CMD ["gunicorn", "--bind", "0.0.0.0:4242", "--workers", "2", "--preload", "app:create_app_with_db()"]
