FROM python:3.10-slim

WORKDIR /app
COPY . /app/

RUN apt-get update && apt-get install -y binutils
RUN pip install pyqt5 pyinstaller

RUN pyinstaller --onefile --name Stenography main.py