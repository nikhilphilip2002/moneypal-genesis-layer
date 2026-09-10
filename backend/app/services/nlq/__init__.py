"""Genesis NLQ — natural-language query layer over governed `gold.*` views.

The legacy API uses the deterministic QuerySpec compiler. Workbench database access goes
through PostgreSQL MCP, whose AST validator and `nlq_readonly` role enforce the boundary.
"""
