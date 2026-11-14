FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
COPY appendix-a/requirements.txt appendix-a/requirements.txt
RUN python -m pip --isolated install --no-cache-dir --timeout 120 --retries 10 --index-url https://pypi.org/simple -r appendix-a/requirements.txt
COPY backend backend
COPY frontend frontend
COPY tools tools
COPY data data
COPY labs labs
COPY docs docs
RUN useradd --uid 10001 --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "backend.chat_app:app", "--host", "0.0.0.0", "--port", "8000"]
