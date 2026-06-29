FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app/app
EXPOSE 8501
HEALTHCHECK CMD python -c "import os, urllib.request; port=os.environ.get('PORT', '8501'); urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health')"
CMD streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501}
