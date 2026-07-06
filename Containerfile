FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate-load.py .
COPY prompts/ prompts/

USER 1001

ENTRYPOINT ["python", "generate-load.py"]
