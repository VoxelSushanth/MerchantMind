# Razorpay AI Analytics SaaS

A production-ready AI-powered analytics platform for Razorpay merchants. Ask natural language questions about your payment data and get accurate, cited answers backed by real transaction data.

## Features

- **OAuth Integration**: Securely connect your Razorpay account
- **Natural Language Queries**: Ask questions like "Which payment method had the highest failure rate last month?"
- **Dual-Path Query Engine**: Combines SQL generation with semantic search for accurate answers
- **Real-time Data Sync**: Automatic synchronization every 6 hours + on-demand triggers
- **Streaming Responses**: Get answers streamed in real-time with Markdown support
- **Auto-Generated Insights**: Weekly narrative reports with anomaly detection
- **Conversation History**: Persistent chat history with context awareness

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Next.js   │────▶│   FastAPI    │────▶│  PostgreSQL │
│   Frontend  │     │   Backend    │     │  + pgvector │
└─────────────┘     └──────────────┘     └─────────────┘
                          │                     ▲
                          ▼                     │
                    ┌──────────────┐            │
                    │    Redis     │────────────┘
                    │  (Cache/Queue)│
                    └──────────────┘
                          │
                          ▼
                    ┌──────────────┐
                    │    Celery    │
                    │   Workers    │
                    └──────────────┘
                          │
                          ▼
                    ┌──────────────┐
                    │   Razorpay   │
                    │     API      │
                    └──────────────┘
```

### Query Pipeline

```
User Question
     │
     ▼
┌─────────────────┐
│ Intent Classifi-│
│ cation (LLM)    │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌──────────┐
│  SQL    │ │ Semantic │
│Generation│ │  Search  │
│ (Path A) │ │ (Path B) │
└────┬────┘ └────┬─────┘
     │           │
     └─────┬─────┘
           ▼
    ┌─────────────┐
    │  Re-ranker  │
    │     LLM     │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │  Streaming  │
    │   Response  │
    └─────────────┘
```

## Tech Stack

### Backend
- **Python 3.12** with **FastAPI**
- **SQLAlchemy** + **Alembic** for ORM and migrations
- **LangChain** for LLM orchestration
- **Claude Sonnet 4** (or GPT-4o) for reasoning
- **pgvector** for vector embeddings
- **Celery** + **Redis** for async tasks
- **Fernet** encryption for sensitive data

### Frontend
- **Next.js 14** with App Router
- **Tailwind CSS** + **shadcn/ui**
- **Recharts** for data visualization
- **Server-Sent Events (SSE)** for streaming

### Infrastructure
- **PostgreSQL** with pgvector extension
- **Redis** for caching and message queue
- **Docker** + **Docker Compose** for containerization

## Installation

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local development)
- Python 3.12+ (for local development)
- Razorpay Account (for OAuth testing)
- Anthropic API Key (or OpenAI)

### Quick Start with Docker

```bash
# Clone the repository
git clone <repository-url>
cd razorpay-ai-analytics

# Copy environment variables
cp .env.example .env

# Edit .env with your credentials
# - ANTHROPIC_API_KEY
# - RAZORPAY_KEY_ID
# - RAZORPAY_KEY_SECRET
# - JWT_SECRET

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Local Development Setup

#### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Initialize database
alembic upgrade head

# Run database migrations
alembic upgrade head

# Start Redis (required)
docker run -d -p 6379:6379 --name redis redis:latest

# Start Celery worker
celery -A app.celery worker --loglevel=info

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your backend URL

# Start development server
npm run dev

# Access at http://localhost:3000
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/razorpay_analytics

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT Authentication
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Razorpay OAuth
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# LLM Provider (Anthropic)
ANTHROPIC_API_KEY=sk-ant-your-key
ANTHROPIC_MODEL=claude-sonnet-4-20250514
MAX_TOKENS=2048

# Alternative: OpenAI
# OPENAI_API_KEY=sk-your-key
# OPENAI_MODEL=gpt-4o

# Encryption
ENCRYPTION_KEY=your-32-byte-fernet-key-generate-with-cryptography-fernet

# Rate Limiting
FREE_TIER_QUERY_LIMIT=20
QUERY_CACHE_TTL=3600

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Generate Fernet Key

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## API Documentation

### Authentication Endpoints

#### `POST /auth/razorpay/initiate`
Initiates OAuth flow with Razorpay.

**Response:**
```json
{
  "authorization_url": "https://auth.razorpay.com/oauth/authorize?..."
}
```

#### `POST /auth/razorpay/callback`
Handles OAuth callback, stores encrypted access token.

**Request:**
```json
{
  "code": "oauth_authorization_code",
  "state": "merchant_id"
}
```

**Response:**
```json
{
  "access_token": "jwt_token",
  "merchant": {
    "id": "uuid",
    "name": "Merchant Name",
    "email": "merchant@example.com"
  }
}
```

### Data Sync Endpoints

#### `POST /sync/trigger`
Triggers manual data synchronization.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "task_id": "celery-task-uuid",
  "status": "queued",
  "message": "Sync job initiated for last 90 days"
}
```

#### `GET /sync/status/:task_id`
Check sync job status.

**Response:**
```json
{
  "task_id": "celery-task-uuid",
  "status": "completed",
  "progress": 100,
  "records_synced": {
    "payments": 1250,
    "refunds": 45,
    "settlements": 30
  }
}
```

### Query Endpoints

#### `POST /query`
Main natural language query endpoint with streaming support.

**Headers:**
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
Accept: text/event-stream
```

**Request:**
```json
{
  "question": "What was my refund rate in April compared to March?",
  "conversation_id": "optional-uuid-for-context"
}
```

**Streaming Response (SSE):**
```
data: {"type": "thought", "content": "Analyzing refund patterns..."}

data: {"type": "sql", "content": "SELECT MONTH(created_at)..."}

data: {"type": "data", "content": {"march_refund_rate": 2.3, "april_refund_rate": 1.8}}

data: {"type": "answer", "content": "Your refund rate **decreased** from **2.3%** in March to **1.8%** in April, representing a **21.7% improvement**.\n\n**Key Figures:**\n- March: 2.3% (45 refunds / 1,956 transactions)\n- April: 1.8% (38 refunds / 2,111 transactions)"}

data: {"type": "done"}
```

#### `GET /conversations/:id`
Fetch conversation history.

**Response:**
```json
{
  "id": "uuid",
  "messages": [
    {
      "role": "user",
      "content": "What was my refund rate...",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "role": "assistant",
      "content": "Your refund rate decreased...",
      "sources": ["sql_results", "semantic_chunks"],
      "timestamp": "2024-01-15T10:30:05Z"
    }
  ]
}
```

### Insights Endpoints

#### `GET /insights/auto`
Get auto-generated weekly insights (cron-triggered).

**Response:**
```json
{
  "week_start": "2024-01-08",
  "week_end": "2024-01-14",
  "summary": "This week saw a 15% increase in GMV...",
  "kpis": {
    "gmv": 125000,
    "gmv_change": 15.2,
    "success_rate": 97.8,
    "avg_ticket": 1250,
    "refund_rate": 1.9
  },
  "anomalies": [
    {
      "type": "spike",
      "metric": "failed_transactions",
      "description": "Unusual spike in UPI failures on Jan 12",
      "severity": "medium"
    }
  ],
  "recommendations": [
    "Consider enabling retry logic for UPI payments",
    "Peak hour detected: 8-9 PM IST"
  ]
}
```

## Database Schema

### Core Tables

```sql
-- Merchants table
CREATE TABLE merchants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    razorpay_merchant_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    last_synced_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Payments cache
CREATE TABLE payments_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID REFERENCES merchants(id),
    razorpay_id VARCHAR(255) UNIQUE NOT NULL,
    amount INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    method VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    settled_at TIMESTAMP WITH TIME ZONE,
    fees INTEGER,
    tax INTEGER
);

-- Refunds cache
CREATE TABLE refunds_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id UUID REFERENCES payments_cache(id),
    amount INTEGER NOT NULL,
    reason TEXT,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Vector embeddings for RAG
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID REFERENCES merchants(id),
    content TEXT NOT NULL,
    embedding vector(1536),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    metadata JSONB
);

-- Conversations history
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID REFERENCES merchants(id),
    messages JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for vector similarity search
CREATE INDEX ON embeddings USING ivfflat (embedding vector_cosine_ops);
```

## Data Ingestion Pipeline

The Celery-based pipeline synchronizes data from Razorpay:

1. **Scheduled Sync**: Runs every 6 hours automatically
2. **On-Demand Sync**: Triggered via API or UI
3. **Incremental Updates**: Only fetches new/updated records
4. **Data Normalization**: Standardizes formats across payment methods

### Sync Process

```python
# Pseudocode
@celery.task
def sync_merchant_data(merchant_id, days=90):
    # 1. Decrypt access token
    token = decrypt(merchant.access_token_encrypted)
    
    # 2. Fetch payments
    payments = razorpay.payment.all({
        'from': now - timedelta(days=days),
        'count': 100
    })
    
    # 3. Normalize and store
    for payment in payments:
        normalized = normalize_payment(payment)
        db.upsert(normalized)
    
    # 4. Fetch related refunds
    refunds = razorpay.refund.all({...})
    
    # 5. Create embeddings for summaries
    create_daily_summaries(merchant_id)
    generate_embeddings(summaries)
    
    # 6. Update last_synced_at
    merchant.last_synced_at = now
```

## Query Engine Details

### Two-Path Approach

#### Path A: Structured SQL Generation

1. **Intent Classification**: LLM identifies query type (COMPARISON, TREND, AGGREGATION, etc.)
2. **SQL Generation**: LLM generates read-only SQL with chain-of-thought
3. **Validation**: Block INSERT/UPDATE/DELETE, limit result rows
4. **Execution**: Run against merchant's data

**Example Generated SQL:**
```sql
SELECT 
    DATE_TRUNC('month', created_at) as month,
    COUNT(*) FILTER (WHERE status = 'refunded') * 100.0 / COUNT(*) as refund_rate
FROM payments_cache
WHERE merchant_id = :merchant_id
    AND created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '2 months')
GROUP BY month
ORDER BY month;
```

#### Path B: Semantic Search

1. **Embedding**: Convert question to vector using same model as chunks
2. **Similarity Search**: Find top-k relevant daily/weekly summaries
3. **Context Augmentation**: Add retrieved chunks to LLM prompt

### Answer Generation

Final prompt to LLM:
```
You are an analytics assistant. Answer based ONLY on the provided data.

DATA FROM SQL:
{sql_results}

RELEVANT CONTEXT:
{semantic_chunks}

QUESTION: {user_question}

Rules:
1. Cite exact figures with percentages
2. Be concise but thorough
3. If data is insufficient, say so
4. Use Markdown formatting
5. Highlight key insights in bold

Answer:
```

## Security Features

- **Encrypted Tokens**: All OAuth tokens encrypted with Fernet at rest
- **SQL Injection Prevention**: Read-only queries, parameterized statements
- **JWT Authentication**: Short-lived tokens with refresh mechanism
- **CORS Configuration**: Strict origin validation
- **Rate Limiting**: 20 queries/day on free tier
- **Prompt Injection Guards**: Input sanitization and validation
- **Audit Logging**: All LLM calls logged with latency and cost

## Monitoring & Observability

### Logged Metrics

- LLM call latency (p50, p95, p99)
- Token consumption per request
- Cost estimates per query
- Cache hit/miss ratios
- Sync job success rates
- Query intent distribution

### Example Log Entry

```json
{
  "timestamp": "2024-01-15T10:30:05Z",
  "merchant_id": "uuid",
  "query_type": "COMPARISON",
  "llm_model": "claude-sonnet-4-20250514",
  "latency_ms": 1250,
  "prompt_tokens": 450,
  "completion_tokens": 180,
  "estimated_cost_usd": 0.0034,
  "cache_hit": false,
  "sql_generated": true,
  "semantic_chunks_used": 3
}
```

## Testing

### Run Tests

```bash
# Backend tests
cd backend
pytest tests/ -v --cov=app

# Frontend tests
cd frontend
npm run test

# Integration tests
docker-compose -f docker-compose.test.yml up
```

### Test Coverage Targets

- API endpoints: >90%
- Query pipeline: >85%
- Data ingestion: >80%
- OAuth flow: >95%

## Deployment

### Production Checklist

- [ ] Rotate all default secrets and keys
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Configure database backups (daily + point-in-time)
- [ ] Set up monitoring (Prometheus + Grafana)
- [ ] Configure log aggregation (ELK stack)
- [ ] Enable rate limiting at API gateway level
- [ ] Set up alerting for failed sync jobs
- [ ] Review CORS origins for production domains
- [ ] Enable database connection pooling
- [ ] Configure horizontal pod autoscaling (if using K8s)

### Docker Production Build

```bash
# Build optimized images
docker-compose -f docker-compose.prod.yml build

# Deploy with scaling
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3
```

## Performance Optimization

- **Query Caching**: Redis cache with 1-hour TTL for identical queries
- **Vector Index**: IVFFlat index for fast similarity search
- **Database Indexes**: Strategic indexes on merchant_id, created_at, status
- **Connection Pooling**: SQLAlchemy pool with pre-ping
- **Async Operations**: Celery for all long-running tasks
- **Streaming Responses**: SSE for real-time answer delivery

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use TypeScript strict mode for frontend
- Write tests for new features
- Update documentation for API changes
- Use conventional commits

## License

MIT License - see [LICENSE](LICENSE) for details.

## 🆘 Support

- **Documentation**: https://docs.razorpay-ai-analytics.com
- **Issues**: https://github.com/your-org/razorpay-ai-analytics/issues
- **Email**: support@razorpay-ai-analytics.com

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- UI components from [shadcn/ui](https://ui.shadcn.com/)
- Vector search powered by [pgvector](https://github.com/pgvector/pgvector)
- LLM orchestration via [LangChain](https://langchain.com/)

---

**Built with ❤️ for Razorpay merchants**
