"""The semantic catalog — the layer that makes opaque column names answerable.

`pg_description` is empty for both schemas, so nothing in the database explains what
`gnlnac_pri_repay_amt` means. This package is where that knowledge lives.
"""

from app.services.nlq.catalog.loader import (
    Catalog,
    CatalogError,
    Dimension,
    DrillGraph,
    DrillPath,
    EnumBlock,
    Join,
    Metric,
    Table,
    get_catalog,
)

__all__ = [
    "Catalog",
    "CatalogError",
    "Dimension",
    "DrillGraph",
    "DrillPath",
    "EnumBlock",
    "Join",
    "Metric",
    "Table",
    "get_catalog",
]
