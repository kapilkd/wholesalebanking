"""
Grounded chat assistant: schema-RAG + NL2SQL over the wholesale database.

Implements CLAUDE.md's chat-path design. Every data question follows one
strict pipeline — the LLM can never answer with client figures it didn't
just read from the database:

    retrieve schema slice (src/schema_retriever.py — catalog docs, not rows)
        -> generate ONE SELECT (temperature 0, MySQL dialect, few-shots)
        -> validate (src/sql_guardrails.py: single SELECT, allow-list, LIMIT)
        -> execute (src/db_reader.execute_readonly_sql: READ ONLY session,
           statement timeout, read-only credentials when configured)
        -> narrate the returned rows (never-invent rules, temperature 0.1)

Failed generation/validation/execution gets ONE corrective retry with the
error fed back; after that the assistant says it couldn't answer rather
than guessing. General product/service questions (no data needed) are
answered directly, with client-specific figures explicitly forbidden.
"""
import json
from typing import Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from config.langchain_config import get_llm
from src import db_reader
from src.schema_retriever import get_retriever
from src.schema_catalog import render_table_doc
from src.sql_guardrails import SQLValidationError, validate_sql

NO_QUERY_SENTINEL = "NO_QUERY"

SQL_GENERATION_RULES = """You translate a banking user's question into ONE MySQL SELECT statement.

RULES:
- Output ONLY the SQL statement, no prose, no markdown fences.
- Exactly one SELECT; never INSERT/UPDATE/DELETE/DDL; no comments.
- Use ONLY the tables and columns listed in the schema slice below.
- Table/column names are UPPER_SNAKE_CASE exactly as listed.
- Client-scoped tables carry APR_CLIENT_CODE — always filter by the
  current client's code unless the question explicitly asks across
  clients or about a different, fully-spelled-out client code.
- Monetary columns are stored in INR Crores.
- Aggregate in SQL (SUM/COUNT/AVG/GROUP BY); return few rows, not raw dumps.
- Include a sensible LIMIT.
- If the question needs NO database data (a general question about
  banking products, services, or concepts), output exactly: NO_QUERY

EXAMPLES:
Q: What is the total outstanding loan amount for this client?
SQL: SELECT SUM(LD.OUTSTANDING_AMOUNT) AS TOTAL_OUTSTANDING_CR FROM ASSET_LOAN_DETAILS LD JOIN ASSET_ACCOUNT_MASTER AAM ON AAM.ASSET_ACCOUNT_ID = LD.ASSET_ACCOUNT_ID WHERE AAM.APR_CLIENT_CODE = 'APR00000001' LIMIT 10

Q: Which term deposits mature in the next 90 days?
SQL: SELECT TD.ASSET_ACCOUNT_ID, TD.DEPOSIT_AMOUNT, TD.MATURITY_DATE FROM LIABILITY_TERM_DEPOSIT_DETAILS TD JOIN LIABILITY_ACCOUNT_MASTER LAM ON LAM.LIABILITY_ACCOUNT_ID = TD.LIABILITY_ACCOUNT_ID WHERE LAM.APR_CLIENT_CODE = 'APR00000001' AND TD.MATURITY_DATE BETWEEN CURRENT_DATE AND DATE_ADD(CURRENT_DATE, INTERVAL 90 DAY) ORDER BY TD.MATURITY_DATE LIMIT 50"""

NARRATOR_SYSTEM_PROMPT = """You are a banking assistant for ABC Bank Wholesale Banking Department.
You answer the user's question using ONLY the database rows provided as JSON.

STRICT RULES:
- Every number, name, and date you state must appear in the provided rows.
- NEVER invent, estimate, or extrapolate values.
- If the rows are empty, say no matching records were found — nothing else.
- Monetary values are in INR Crores: format as ₹**XX.XX CR**.
- Bold all numbers and dates with markdown (**...**).
- Be concise and professional; answer the question directly."""

GENERAL_SYSTEM_PROMPT = """You are an AI assistant for ABC Bank Wholesale Banking Department.
Answer general questions about wholesale banking products, services, and concepts
(corporate banking, trade finance, cash management, FX, credit facilities).
You have NO database rows in this conversation turn, so you MUST NOT state any
client-specific figures, balances, holdings, or events — if asked for client
data, say you'll need to look it up and ask the user to rephrase as a data
question. Use Indian Rupees (₹) for any generic monetary examples.
Be concise, clear, and professional."""


class WholesaleBankingChatbot:
    """Schema-RAG + NL2SQL chat over the wholesale banking database."""

    def __init__(self, client_code: str = None, retriever=None):
        self.client_code = client_code
        self.sql_llm = get_llm(temperature=0)
        self.narrator_llm = get_llm(temperature=0.1)
        self.retriever = retriever or get_retriever()
        self.conversation_history: List[Dict[str, str]] = []

    # ------------------------------------------------------------------ #
    # Pipeline steps
    # ------------------------------------------------------------------ #

    def _history_context(self, limit: int = 3) -> str:
        if not self.conversation_history:
            return ""
        turns = self.conversation_history[-limit:]
        lines = [f"User: {t['user']}\nAssistant: {t['assistant']}" for t in turns]
        return "Recent conversation (for follow-up questions):\n" + "\n".join(lines)

    def _generate_sql(self, question: str, schema_text: str,
                      previous_error: Optional[str] = None) -> str:
        client_line = (
            f"Current client context: APR_CLIENT_CODE = '{self.client_code}'"
            if self.client_code else
            "No client context is set — only answer cross-client questions "
            "or ones that name a client code explicitly."
        )
        user_parts = [client_line, self._history_context(),
                      f"Schema slice (the ONLY tables/columns you may use):\n{schema_text}"]
        if previous_error:
            user_parts.append(
                "Your previous attempt failed with this error — fix it:\n"
                f"{previous_error}"
            )
        user_parts.append(f"Question: {question}")
        response = self.sql_llm.invoke([
            SystemMessage(content=SQL_GENERATION_RULES),
            HumanMessage(content="\n\n".join(p for p in user_parts if p)),
        ])
        sql = response.content.strip()
        # Tolerate a fenced answer despite the no-fences instruction.
        if sql.startswith("```"):
            sql = sql.strip("`")
            if sql.lower().startswith("sql"):
                sql = sql[3:]
        return sql.strip()

    def _narrate_rows(self, question: str, sql: str, rows: List[Dict]) -> str:
        response = self.narrator_llm.invoke([
            SystemMessage(content=NARRATOR_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Question: {question}\n\n"
                f"SQL that was executed:\n{sql}\n\n"
                f"Rows returned ({len(rows)}):\n{json.dumps(rows, default=str)}"
            )),
        ])
        return response.content

    def _answer_general(self, question: str) -> str:
        messages = [SystemMessage(content=GENERAL_SYSTEM_PROMPT)]
        for turn in self.conversation_history[-5:]:
            messages.append(HumanMessage(content=turn["user"]))
            messages.append(SystemMessage(content=f"(previous answer) {turn['assistant']}"))
        messages.append(HumanMessage(content=question))
        return self.narrator_llm.invoke(messages).content

    # ------------------------------------------------------------------ #
    # Public API (same surface app.py already uses)
    # ------------------------------------------------------------------ #

    def get_response(self, user_input: str) -> str:
        """Answer one user message through the grounded pipeline."""
        schema_docs = self.retriever.retrieve(user_input)
        schema_text = "\n\n".join(render_table_doc(d) for d in schema_docs)
        allowed_tables = [d["table"] for d in schema_docs]

        answer = None
        error: Optional[str] = None
        executed_sql: Optional[str] = None

        for _attempt in range(2):  # first try + one corrective retry
            sql = self._generate_sql(user_input, schema_text, previous_error=error)
            if sql.upper() == NO_QUERY_SENTINEL:
                answer = self._answer_general(user_input)
                break
            try:
                validated = validate_sql(sql, allowed_tables)
                rows = db_reader.execute_readonly_sql(validated)
            except SQLValidationError as e:
                error = f"Guardrail rejection: {e}"
                continue
            except Exception as e:
                error = f"Database error: {e}"
                continue
            executed_sql = validated
            answer = self._narrate_rows(user_input, validated, rows)
            break

        if answer is None:
            answer = (
                "I couldn't build a safe database query for that question "
                f"(last error: {error}). Try rephrasing it — for example, "
                "name the product area (loans, deposits, holdings) you're "
                "asking about."
            )
        elif executed_sql:
            answer += f"\n\n<sub>Query used: `{executed_sql}`</sub>"

        self.conversation_history.append({
            "user": user_input,
            "assistant": answer,
        })
        return answer

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []

    def update_client_code(self, client_code: str):
        """Switch the client context (keeps retriever and history handling)."""
        self.client_code = client_code
        self.clear_history()
