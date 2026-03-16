FROM python:3.10-slim

# Disable python cache
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (FFmpeg required for encoding)
RUN apt-get update && \
    apt-get install -y ffmpeg gcc libffi-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (docker caching)
COPY requirements.txt .

# Install python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Run bot
CMD ["python3", "bot.py"]
