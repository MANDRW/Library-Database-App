# Library Database App

A FastAPI application integrated with PostgreSQL.

## Prerequisites

* Docker
* Docker Compose

## Quick Start

1. Create a `.env` file in the root directory with the required database credentials (e.g., `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`).
2. Build and start the containers:

```bash
docker compose up -d --build
