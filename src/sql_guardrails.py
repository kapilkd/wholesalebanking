"""
Validation guardrails for LLM-generated SQL (chat path).

Per CLAUDE.md's SQL-only orchestration constraint, every generated query
must pass ALL of these checks before touching the database:

1. Parses as exactly ONE statement (sqlglot, MySQL dialect).
2. The statement is a plain SELECT (CTEs/UNIONs of SELECTs allowed) —
   any DDL/DML/administrative node anywhere in the AST is rejected.
3. Every referenced table is on the caller-supplied allow-list (built from
   the retrieved schema slice).
4. A LIMIT is enforced: appended when missing, clamped when too large.

validate_sql() returns the sanitized SQL string to execute, or raises
SQLValidationError with a reason suitable for feeding back to the LLM.
"""
from typing import Iterable

import sqlglot
from sqlglot import exp

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

# AST node types that must never appear anywhere in a chat query.
_FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge,
    exp.Create, exp.Drop, exp.Alter, exp.TruncateTable,
    exp.Grant, exp.Set, exp.Command, exp.Use, exp.Transaction,
    exp.Commit, exp.Rollback, exp.LoadData,
)


class SQLValidationError(ValueError):
    """Generated SQL failed a guardrail; message says which and why."""


def validate_sql(query: str, allowed_tables: Iterable[str],
                 default_limit: int = DEFAULT_LIMIT,
                 max_limit: int = MAX_LIMIT) -> str:
    """
    Validate one LLM-generated query against the guardrails.

    Args:
        query: raw SQL text from the NL2SQL step
        allowed_tables: table names permitted for this question (the
            retrieved schema slice; matching is case-insensitive)

    Returns:
        Sanitized SQL (single SELECT, LIMIT enforced) ready to execute.

    Raises:
        SQLValidationError: on parse failure, multiple statements,
            non-SELECT constructs, or tables off the allow-list.
    """
    if not query or not query.strip():
        raise SQLValidationError("Empty query.")

    try:
        statements = sqlglot.parse(query, dialect="mysql")
    except sqlglot.errors.ParseError as e:
        raise SQLValidationError(f"SQL failed to parse: {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SQLValidationError(
            f"Exactly one statement is allowed, got {len(statements)}."
        )
    stmt = statements[0]

    if not isinstance(stmt, (exp.Select, exp.Union)):
        raise SQLValidationError(
            f"Only SELECT statements are allowed, got {stmt.key.upper()}."
        )

    for node in stmt.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise SQLValidationError(
                f"Forbidden SQL construct: {node.key.upper()}."
            )
        # SELECT ... INTO OUTFILE / INTO @var style exfiltration
        if isinstance(node, exp.Select) and node.args.get("into"):
            raise SQLValidationError("SELECT ... INTO is not allowed.")

    allowed = {t.upper() for t in allowed_tables}
    cte_names = {cte.alias_or_name.upper() for cte in stmt.find_all(exp.CTE)}
    for table in stmt.find_all(exp.Table):
        name = table.name.upper()
        if name in cte_names:
            continue
        if name not in allowed:
            raise SQLValidationError(
                f"Table {name} is not in the allowed schema slice. "
                f"Allowed tables: {', '.join(sorted(allowed))}."
            )

    # Enforce LIMIT on the outermost SELECT/UNION.
    limit_node = stmt.args.get("limit")
    if limit_node is None:
        stmt = stmt.limit(default_limit)
    else:
        try:
            current = int(limit_node.expression.name)
        except (AttributeError, ValueError):
            raise SQLValidationError("LIMIT must be a plain integer.")
        if current > max_limit:
            stmt = stmt.limit(max_limit)

    return stmt.sql(dialect="mysql")
