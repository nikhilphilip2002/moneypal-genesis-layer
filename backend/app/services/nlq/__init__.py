"""Genesis NLQ — natural-language query layer over `silver.*`.

See docs/GENESIS_NLQ_BUILD_PLAN.md. Two paths reach the database: a deterministic
QuerySpec compiler (the trusted path) and an LLM text-to-SQL fallback behind an AST
validator. Both execute under the `nlq_readonly` Postgres role.
"""
