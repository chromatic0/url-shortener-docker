FROM python:3.13
WORKDIR /src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 4242

RUN useradd app
USER app

CMD ["python3", "app.py"]