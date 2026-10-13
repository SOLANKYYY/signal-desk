FROM python:3.12-slim
WORKDIR /lab
RUN pip install --no-cache-dir pymongo==4.18.2
COPY lab9.py README.md /lab/
ENV RESULTS_DIR=/results
ENTRYPOINT ["python", "/lab/lab9.py"]
CMD ["help"]
COPY compose.yaml start.ps1 run-partition.ps1 README.md Dockerfile Dockerfile.submission .dockerignore /kit/
