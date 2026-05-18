FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY web/ web/
COPY pyproject.toml .

# Install the package
RUN pip install --no-cache-dir -e .

# Create private directory structure
RUN mkdir -p private/photos private/documents private/config private/data

EXPOSE 8000

CMD ["gunicorn", "web_server:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--chdir", "src"]
