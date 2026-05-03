"""
API routes for natural language queries.
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger
import redis.asyncio as redis

from app.api.schemas import QueryRequest, QueryResponse, SQLResult, SemanticChunk
from app.core.database import get_db
from app.core.config import get_settings

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["Query"])
settings = get_settings()

# Redis for caching
redis_client = redis.from_url(settings.REDIS_URL)


async def get_cache_key(merchant_id: str, question: str) -> str:
    """Generate cache key for query."""
    import hashlib
    question_hash = hashlib.md5(question.lower().encode()).hexdigest()
    return f"query:{merchant_id}:{question_hash}"


@router.post("", response_model=QueryResponse)
async def post_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a natural language query.
    
    Returns answer with SQL results and semantic context.
    """
    # Get merchant (in production, extract from JWT)
    from sqlalchemy import select
    from app.models import Merchant
    
    result = await db.execute(select(Merchant).limit(1))
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="No merchant found")
    
    merchant_id = merchant.id
    question = request.question
    
    # Check cache
    cache_key = await get_cache_key(merchant_id, question)
    cached = await redis_client.get(cache_key)
    
    if cached:
        logger.info("Query cache hit", merchant_id=merchant_id)
        cached_data = json.loads(cached)
        return QueryResponse(**cached_data)
    
    # Process query
    from app.services.query_engine import QueryEngine
    
    query_engine = QueryEngine(db)
    
    # Step 1: Classify intent
    intent = await query_engine.classify_intent(question)
    logger.info("Intent classified", intent=intent)
    
    # Step 2: Generate and execute SQL
    sql_result = None
    try:
        sql_info = await query_engine.generate_sql(question, intent)
        if sql_info:
            execution_result = await query_engine.execute_sql(sql_info["sql"])
            sql_result = SQLResult(
                sql=sql_info["sql"],
                explanation=sql_info.get("explanation", ""),
                rows=execution_result["rows"],
                row_count=execution_result["row_count"],
            )
    except Exception as e:
        logger.warning("SQL path failed, falling back to semantic only", error=str(e))
    
    # Step 3: Retrieve semantic context
    semantic_chunks_data = await query_engine.retrieve_semantic_context(
        merchant_id=merchant_id,
        question=question,
        k=3,
    )
    semantic_chunks = [
        SemanticChunk(
            content=chunk["content"],
            period_start=chunk["period_start"],
            period_end=chunk["period_end"],
            similarity_score=chunk["similarity_score"],
        )
        for chunk in semantic_chunks_data
    ]
    
    # Step 4: Generate answer
    answer = await query_engine.generate_answer(
        question=question,
        sql_results=sql_result.model_dump() if sql_result else None,
        semantic_chunks=[c.model_dump() for c in semantic_chunks],
    )
    
    # Determine conversation ID
    conversation_id = request.conversation_id or "default"
    
    # Build response
    response = QueryResponse(
        answer=answer,
        sql_results=sql_result,
        semantic_chunks=semantic_chunks,
        conversation_id=conversation_id,
        streaming=False,
    )
    
    # Cache for 1 hour
    await redis_client.setex(
        cache_key,
        settings.CACHE_TTL_SECONDS,
        json.dumps(response.model_dump()),
    )
    
    logger.info("Query processed", merchant_id=merchant_id, cached=False)
    
    return response


@router.post("/stream")
async def stream_query(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a natural language query with streaming response.
    
    Streams the answer as Server-Sent Events (SSE).
    """
    from sqlalchemy import select
    from app.models import Merchant
    from app.services.query_engine import QueryEngine
    
    # Get merchant
    result = await db.execute(select(Merchant).limit(1))
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="No merchant found")
    
    async def generate():
        query_engine = QueryEngine(db)
        
        # Classify intent
        intent = await query_engine.classify_intent(request.question)
        
        # Generate SQL (non-blocking)
        sql_result = None
        try:
            sql_info = await query_engine.generate_sql(request.question, intent)
            if sql_info:
                execution_result = await query_engine.execute_sql(sql_info["sql"])
                sql_result = {
                    "sql": sql_info["sql"],
                    "explanation": sql_info.get("explanation", ""),
                    "rows": execution_result["rows"],
                    "row_count": execution_result["row_count"],
                }
        except Exception as e:
            logger.warning("SQL path failed", error=str(e))
        
        # Get semantic context
        semantic_chunks = await query_engine.retrieve_semantic_context(
            merchant_id=merchant.id,
            question=request.question,
            k=3,
        )
        
        # Stream answer generation
        from langchain_anthropic import ChatAnthropic
        
        llm = ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            temperature=0.3,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
        
        system_prompt = """You are an analytics assistant answering questions about payment data.
Rules:
1. Always cite specific figures from the data provided
2. Be concise but complete
3. Format currency as ₹X.XX (rupees)
4. Answer precisely based on the data provided."""

        # Prepare context
        context_parts = []
        if sql_result:
            context_parts.append(f"SQL Results: {json.dumps(sql_result['rows'][:5])}")
        if semantic_chunks:
            context_parts.append(f"Context: {[c['content'] for c in semantic_chunks]}")
        
        full_context = "\n\n".join(context_parts) if context_parts else "No additional data."
        
        # Stream tokens
        from langchain_core.messages import HumanMessage, SystemMessage
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Question: {request.question}\n\n{full_context}"),
        ]
        
        async for chunk in llm.astream(messages):
            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
            yield f"data: {json.dumps({'token': token})}\n\n"
        
        # Send completion signal
        yield f"data: {json.dumps({'done': True})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
