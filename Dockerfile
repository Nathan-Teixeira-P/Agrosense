FROM python:3.12-slim
WORKDIR /app
COPY server.py analisar_ia.py openai_client.py index.html ./
ENV HOST=0.0.0.0
EXPOSE 3000
CMD ["python3", "server.py"]
