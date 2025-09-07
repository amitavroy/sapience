# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Verify uv installation
RUN uv --version

# Copy project files
COPY pyproject.toml ./
COPY main.py ./
COPY app/ ./app/

# Install dependencies
RUN uv sync

# Expose port
EXPOSE 8000

# Start the application
CMD ["uv", "run", "python", "main.py"]
