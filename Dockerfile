FROM python:3.11-slim
WORKDIR /atlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY project project
ENV PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python","project/app/atlas.py"]
