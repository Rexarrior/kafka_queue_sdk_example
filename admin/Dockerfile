FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy kafkaQueueSdk for local installation
COPY kafkaQueueSdk /tmp/kafkaQueueSdk

# Copy requirements
COPY kafka_queue_sdk_example/admin/requirements.txt .

# Install kafka packages from local copy
RUN pip install --no-cache-dir /tmp/kafkaQueueSdk/client
RUN pip install --no-cache-dir /tmp/kafkaQueueSdk
RUN python -c "import kafka_queue_client, kafka_server_sdk; assert kafka_queue_client.__version__ == '1.0.0'; assert kafka_server_sdk.__version__ == '1.0.0'"

# Install application-only dependencies; SDK packages came from the sibling checkout.
RUN awk '!/^kafka_(server_sdk|queue_client)==/' requirements.txt > requirements_filtered.txt && \
    pip install --no-cache-dir -r requirements_filtered.txt

# Clean up
RUN rm -rf /tmp/kafkaQueueSdk

# Copy the service code
COPY kafka_queue_sdk_example/admin/ .

# Create logs directory
RUN mkdir -p logs

# Expose the port
EXPOSE 7094

# Run the service
CMD ["python3", "run.py"]
