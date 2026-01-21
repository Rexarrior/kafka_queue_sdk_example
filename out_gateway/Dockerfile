FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy kafkaQueueSdk for installation
COPY kafkaQueueSdk /tmp/kafkaQueueSdk

# Copy requirements
COPY kafka_queue_sdk_example/out_gateway/requirements.txt .

# Install kafka packages from local copy
RUN pip install --no-cache-dir /tmp/kafkaQueueSdk/client
RUN pip install --no-cache-dir /tmp/kafkaQueueSdk

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Clean up
RUN rm -rf /tmp/kafkaQueueSdk

# Copy the service code
COPY kafka_queue_sdk_example/out_gateway/ .

# Create logs directory
RUN mkdir -p logs

# Make sure the script is executable
RUN chmod +x run_kafka.sh

# Expose the port
EXPOSE 7092

# Run the service
CMD ["./run_kafka.sh"]