# Kafka Queue SDK Example - Docker Setup

This is a complete Docker-based setup for a Kafka-based microservices architecture using the kafkaQueueSdk framework.

## Architecture Overview

### Infrastructure Services
- **Zookeeper** (port 2181) - Kafka coordination service
- **Kafka** (port 9092) - Message broker
- **Kafka UI** (port 8020) - Web interface for Kafka management
- **PostgreSQL** (port 5433) - Database for services
- **MinIO** (ports 9090, 9091) - S3-compatible object storage
  - API endpoint: http://localhost:9090
  - Web Console: http://localhost:9091

### Application Services
- **in_gateway** (port 7091) - Input gateway service
- **out_gateway** (port 7092) - Output gateway service
- **file_storage** (port 7093) - File storage service
- **admin** (port 7094) - Admin/monitoring service
- **logic** (ports 7095, 7096) - Logic processing service
- **hold_service** (ports 7097, 7098) - Message hold and management service

## Prerequisites

- Docker
- Docker Compose v3.8+

## Quick Start

**Important:** The docker-compose.yaml uses a build context that includes the parent `kafkaQueueSdk` directory. Make sure you run docker-compose from the `kafka_queue_sdk_example` directory.

1. **Start all services:**
   ```bash
   cd kafka_queue_sdk_example
   docker-compose up -d
   ```

2. **View logs:**
   ```bash
   # All services
   docker-compose logs -f
   
   # Specific service
   docker-compose logs -f in_gateway
   ```

3. **Stop all services:**
   ```bash
   docker-compose down
   ```

4. **Stop and remove volumes:**
   ```bash
   docker-compose down -v
   ```

## Service Details

### in_gateway
- **Purpose**: Entry point for incoming requests
- **Port**: 7091
- **Dependencies**: Kafka, PostgreSQL, S3
- **Config**: `in_gateway/config.json`

### out_gateway
- **Purpose**: Exit point for outgoing responses
- **Port**: 7092
- **Dependencies**: Kafka, PostgreSQL
- **Config**: `out_gateway/config.json`

### file_storage
- **Purpose**: File storage and retrieval service
- **Port**: 7093
- **Dependencies**: Kafka, PostgreSQL, S3
- **Config**: `file_storage/config.json`

### logic
- **Purpose**: Business logic processing service
- **Ports**: 7095 (main), 7096 (admin)
- **Dependencies**: Kafka
- **Config**: `logic/server_config.json`, `logic/admin_config.json`

### hold_service
- **Purpose**: Message holding and management service for controlled message flow
- **Ports**: 7097 (main), 7098 (admin)
- **Dependencies**: Kafka
- **Config**: `hold_service/config.json`, `hold_service/server_config.json`, `hold_service/admin_config.json`
- **Features**: 
  - Holds messages from logic service
  - Provides API for message management (hold/release)
  - Forwards released messages to file_storage
  - SQLite database for message persistence

### admin
- **Purpose**: Queue administration and monitoring
- **Port**: 7094
- **Dependencies**: All application services
- **Config**: `admin/config.json`

## Kafka Topics

The following Kafka topics are automatically created:
- `logic_in` - Input topic for logic service
- `hold_in` - Input topic for hold service (from logic)
- `files_proxy` - Input topic for file storage (from hold service)
- `events` - Events topic for all services
- `out` - Output topic

## Message Flow

The architecture follows this message flow:
1. **in_gateway** receives requests → publishes to `logic_in`
2. **logic** processes messages from `logic_in` → publishes to `hold_in`
3. **hold_service** receives messages from `hold_in` → holds/manages them → publishes to `files_proxy`
4. **file_storage** processes messages from `files_proxy` → publishes to `out`
5. **out_gateway** sends responses from `out` topic

## Access Points

- **Kafka UI**: http://localhost:8020
- **In Gateway**: http://localhost:7091
- **Out Gateway**: http://localhost:7092
- **File Storage**: http://localhost:7093
- **Admin Panel**: http://localhost:7094
- **Logic Service**: http://localhost:7095 (admin: 7096)
- **Hold Service**: http://localhost:7097 (admin: 7098)
- **S3 Server**: http://localhost:9090
- **PostgreSQL**: localhost:5433

## Configuration

### Environment Variables
Edit `.env` file to configure:
- PostgreSQL credentials
- S3 access keys

### Service Configurations
Each service has its own configuration files in its directory:
- `in_gateway/config.json`
- `out_gateway/config.json`
- `file_storage/config.json`, `server_config.json`, `admin_config.json`
- `logic/server_config.json`, `admin_config.json`
- `hold_service/config.json`, `server_config.json`, `admin_config.json`
- `admin/config.json`

## Health Checks

All infrastructure services have health checks configured:
- **Zookeeper**: Port 2181 connectivity
- **Kafka**: Topic listing capability
- **PostgreSQL**: `pg_isready` check
- **S3 Server**: HTTP endpoint check

Application services will wait for healthy infrastructure before starting.

## Logs

Service logs are mounted to local directories:
- `in_gateway/logs/`
- `out_gateway/logs/`
- `file_storage/logs/`
- `logic/logs/`
- `hold_service/logs/`
- `admin/logs/`

## Troubleshooting

### Services not starting
```bash
# Check service status
docker-compose ps

# Check specific service logs
docker-compose logs <service_name>
```

### Kafka connection issues
```bash
# Verify Kafka is healthy
docker-compose ps kafka

# Check Kafka logs
docker-compose logs kafka
```

### Database connection issues
```bash
# Verify PostgreSQL is healthy
docker-compose ps postgres_db

# Connect to database
docker-compose exec postgres_db psql -U postgres
```

### Reset everything
```bash
# Stop and remove all containers, networks, and volumes
docker-compose down -v

# Rebuild and start
docker-compose up -d --build
```

## Development

### Rebuild specific service
```bash
docker-compose up -d --build <service_name>
```

### Access service shell
```bash
docker-compose exec <service_name> /bin/bash
```

### View service configuration
```bash
docker-compose exec <service_name> cat config.json
```

## Network

All services are connected via the `app_net` bridge network, allowing them to communicate using service names as hostnames.

## Volumes

- `postgres_data`: PostgreSQL data persistence
- `scalityS3_data`: S3 storage data persistence

## Framework Documentation

For more details about the kafkaQueueSdk framework, see:
- `../kafkaQueueSdk/doc/server/quickstart.md`
- `../kafkaQueueSdk/doc/server/configs.md`
- `../kafkaQueueSdk/doc/server/middleware.md`
