"""
Query engine with two-path approach: SQL generation + semantic search.
"""
import json
import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.core.config import get_settings
from app.services.embeddings_service import EmbeddingsService

logger = get_logger(__name__)
settings = get_settings()


class QueryEngine:
    """
    Two-path query engine for natural language questions.
    
    Path A: NL -> SQL -> Execute -> Results
    Path B: NL -> Embedding -> Similarity Search -> Context
    
    Combines both paths for comprehensive answers.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embeddings_service = EmbeddingsService(db)

    async def classify_intent(self, question: str) -> dict[str, Any]:
        """
        Classify the intent of the question using LLM.
        
        Returns intent type and relevant parameters.
        """
        from langchain_anthropic import ChatAnthropic
        
        llm = ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            temperature=0.0,
            max_tokens=500,
        )

        system_prompt = """You are an intent classifier for a payments analytics system.
Classify the user's question into one of these categories:
- COMPARISON: Comparing metrics across time periods or segments
- TREND: Asking about trends over time
- AGGREGATION: Asking for totals, averages, counts
- BREAKDOWN: Asking for breakdown by category (method, status, etc.)
- ANOMALY: Asking about unusual patterns or outliers
- GENERAL: General questions not fitting other categories

Also identify:
- Primary metric: payment_amount, refund_amount, success_rate, transaction_count, etc.
- Time filter: specific dates/periods mentioned
- Filters: any specific filters (payment method, status, etc.)

Return JSON: {"intent": "...", "primary_metric": "...", "time_filter": "...", "filters": {}}"""

        try:
            response = await llm.ainvoke([
                ("system", system_prompt),
                ("user", question)
            ])
            
            # Parse JSON from response
            content = response.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"intent": "GENERAL", "primary_metric": None, "time_filter": None, "filters": {}}
        except Exception as e:
            logger.warning("Intent classification failed", error=str(e))
            return {"intent": "GENERAL", "primary_metric": None, "time_filter": None, "filters": {}}

    async def generate_sql(self, question: str, intent: dict[str, Any]) -> Optional[dict[str, str]]:
        """
        Generate SQL query from natural language question.
        
        Returns dict with 'sql' and 'explanation' keys.
        """
        from langchain_anthropic import ChatAnthropic
        
        llm = ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            temperature=0.0,  # Deterministic for SQL
            max_tokens=1000,
        )

        schema_info = """
Database Schema:
- payments_cache: id, merchant_id, razorpay_id, amount (paise), status, method, created_at, settled_at, fees, tax, currency
- refunds_cache: id, payment_id, merchant_id, razorpay_id, amount (paise), reason, status, created_at

Status values: 'captured', 'failed', 'authorized', 'refunded'
Method values: 'card', 'upi', 'netbanking', 'wallet', 'emi', 'paylater'
Amount is stored in paise (1 rupee = 100 paise)
"""

        system_prompt = f"""You are a SQL expert generating read-only queries for a payments analytics system.

{schema_info}

Rules:
1. ONLY generate SELECT queries - NO INSERT, UPDATE, DELETE, DROP, or any write operations
2. Always include merchant_id filter when applicable
3. Convert amounts from paise to rupees by dividing by 100
4. Use appropriate date functions for time filtering
5. Return valid PostgreSQL syntax
6. Think step by step before generating the SQL

Return JSON with exactly this structure:
{{"sql": "SELECT ...", "explanation": "Brief explanation of what the query does"}}"""

        try:
            response = await llm.ainvoke([
                ("system", system_prompt),
                ("user", f"Question: {question}\n\nIntent: {json.dumps(intent)}")
            ])
            
            content = response.content
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                # Validate SQL safety
                if self._validate_sql(result.get("sql", "")):
                    return result
                else:
                    logger.warning("Generated SQL failed validation")
                    return None
            return None
        except Exception as e:
            logger.warning("SQL generation failed", error=str(e))
            return None

    def _validate_sql(self, sql: str) -> bool:
        """Validate that SQL is safe (read-only)."""
        if not sql:
            return False
        
        sql_upper = sql.upper().strip()
        
        # Block dangerous operations
        dangerous_keywords = [
            "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", 
            "ALTER", "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE"
        ]
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False
        
        # Must start with SELECT or WITH
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False
        
        return True

    async def execute_sql(self, sql: str) -> dict[str, Any]:
        """Execute validated SQL query."""
        try:
            result = await self.db.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            
            return {
                "sql": sql,
                "rows": rows,
                "row_count": len(rows),
            }
        except Exception as e:
            logger.error("SQL execution failed", sql=sql, error=str(e))
            raise

    async def retrieve_semantic_context(
        self,
        merchant_id: str,
        question: str,
        k: int = 3,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant context from embeddings."""
        try:
            results = await self.embeddings_service.similarity_search(
                merchant_id=merchant_id,
                query=question,
                k=k,
            )
            
            return [
                {
                    "content": emb.content,
                    "period_start": emb.period_start.isoformat(),
                    "period_end": emb.period_end.isoformat(),
                    "similarity_score": sim,
                }
                for emb, sim in results
            ]
        except Exception as e:
            logger.warning("Semantic retrieval failed", error=str(e))
            return []

    async def generate_answer(
        self,
        question: str,
        sql_results: Optional[dict[str, Any]],
        semantic_chunks: list[dict[str, Any]],
    ) -> str:
        """Generate final answer using LLM, grounded in retrieved data."""
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
3. If data is insufficient, say so clearly
4. Never make up numbers or speculate beyond the data
5. Format currency as ₹X.XX (rupees)
6. Include percentages where relevant
7. If SQL results are provided, prioritize them over semantic context

Answer the question precisely based on the data provided."""

        context_parts = []
        
        if sql_results:
            sql_context = f"SQL Query Results:\n- Query: {sql_results['sql']}\n- Rows returned: {sql_results['row_count']}\n- Data: {json.dumps(sql_results['rows'][:10], indent=2)}"
            if sql_results['row_count'] > 10:
                sql_context += f"\n... and {sql_results['row_count'] - 10} more rows"
            context_parts.append(sql_context)
        
        if semantic_chunks:
            semantic_context = "Relevant Historical Context:\n" + "\n".join(
                f"- [{chunk['period_start']} to {chunk['period_end']}] {chunk['content']} (similarity: {chunk['similarity_score']:.2f})"
                for chunk in semantic_chunks
            )
            context_parts.append(semantic_context)

        full_context = "\n\n".join(context_parts) if context_parts else "No additional data available."

        try:
            response = await llm.ainvoke([
                ("system", system_prompt),
                ("user", f"Question: {question}\n\n{full_context}")
            ])
            
            return response.content
        except Exception as e:
            logger.error("Answer generation failed", error=str(e))
            return "I apologize, but I encountered an error generating the answer. Please try again."
