# ADR-001: Local Docker Infrastructure

- **Status:** Accepted
- **Date:** 2026-11-26
- **Decision:** Use a fully self-hosted, Docker Compose-based infrastructure for Agentic AI Engineering Lab.

## Context

The platform requires a reproducible local environment for agent development, RAG, document processing, vector search, workflow execution, and LLM observability.

The infrastructure should provide local control, persistent storage, minimal resource overhead, and clear service isolation.

## Architecture Decisions

| Area | Decision | Rationale |
|---|---|---|
| Deployment | Docker Compose | Reproducible local deployment and simpler management |
| Networking | Private Docker bridge network | Internal service communication through Docker DNS |
| Frontend | Next.js | Web application, exposed on port 3001 |
| Backend | FastAPI | API and Swagger documentation, exposed on port 8001 |
| Relational database | PostgreSQL 17 | Persistent application data and workflow checkpoints |
| PostgreSQL topology | One server, separate databases | Lower resource consumption with logical isolation |
| Cache and queues | Valkey 8+ | Shared caching and queue infrastructure |
| Vector database | Qdrant | Semantic search and vector retrieval |
| Object storage | SeaweedFS | Self-hosted, S3-compatible object storage |
| Object storage topology | Single-node | Simple development deployment with persistent storage |
| Analytics database | ClickHouse | Langfuse trace and event analytics |
| LLM observability | Self-hosted Langfuse | Tracing, prompt management and experimentation |
| Persistence | Docker named volumes | Preserve data across container recreation |
| Configuration | Root `.env` and `.env.example` | Separate actual secrets from documented defaults |

## Network Exposure

Only selected interfaces are published to the Windows host.

| Service | Host Address | Exposure |
|---|---|---|
| Frontend | `localhost:3001` | Published |
| Backend | `localhost:8001` | Published |
| Langfuse | `localhost:3002` | Published |
| SeaweedFS Master UI | `localhost:9333` | Published |
| SeaweedFS Filer UI | `localhost:8888` | Published |
| PostgreSQL | Internal Docker network | Internal only |
| Valkey | Internal Docker network | Internal only |
| Qdrant | Internal Docker network | Internal only |
| ClickHouse | Internal Docker network | Internal only |
| SeaweedFS S3 API | Internal Docker network | Internal only |

All published management interfaces bind to `127.0.0.1`.

## PostgreSQL Database Separation

A single PostgreSQL server will host separate databases:

- `agentlab`: Application data, users, and LangGraph checkpoints.
- `langfuse`: Langfuse application metadata.

Langfuse will use a separate database user and credentials.

## Storage Strategy

Persistent Docker volumes will be maintained for:

- PostgreSQL
- Valkey
- Qdrant
- SeaweedFS
- ClickHouse

SeaweedFS will provide S3-compatible storage for application documents, datasets, generated artifacts, and Langfuse event uploads.

## Security Decisions

- Keep infrastructure services inaccessible directly from the host.
- Bind published application and management ports to localhost.
- Store credentials and API keys in the root `.env`.
- Commit only `.env.example`.
- Use separate PostgreSQL credentials for application and Langfuse databases.
- Enable authentication for Valkey, Qdrant, ClickHouse, and SeaweedFS S3 access.

## Consequences

### Benefits

- Complete local ownership and control.
- No dependency on Langfuse Cloud.
- Lower resource overhead through shared infrastructure.
- Persistent data across container recreation.
- Clear separation between application and observability data.
- Reproducible development environment.

### Trade-offs

- Single-node services do not provide high availability.
- Shared infrastructure requires careful resource management.
- Backups and upgrades remain the application's responsibility.
- Local development topology may require adjustments for production deployment.

## Future Considerations

- Automated backups and restore procedures.
- Resource limits and monitoring.
- Production deployment architecture.
- Authentication and authorization for management interfaces.
- Independent scaling of high-load services.

---

**Decision Summary:** Build a fully local, persistent, Dockerized Agentic AI Lab using open-source infrastructure, shared PostgreSQL and Valkey services, Qdrant, SeaweedFS, ClickHouse, and self-hosted Langfuse.