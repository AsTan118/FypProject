FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

EXPOSE 5000

# Run with Uvicorn (better than Python dev server)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
