FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Make sure the script is executable
RUN chmod +x run_kafka.sh

# Expose the port
EXPOSE 7091

# Run the service
CMD ["./run_kafka.sh"]