FROM python:3.13
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 4242

RUN useradd app
USER app

CMD ["python3", "./src/app.py"]