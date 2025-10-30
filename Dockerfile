FROM python:3.11-slim
WORKDIR /app
COPY main.py .
RUN pip install flask requests
EXPOSE 8000
CMD ["python", "main.py"]
