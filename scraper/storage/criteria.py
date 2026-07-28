"""
scraper.storage.criteria
~~~~~~~~~~~~~~~~~~~~~~~~
Declarative Criteria Pattern implementation for building dynamic database queries
without writing hardcoded SQL statements.

Supports filtering, ordering, limiting, and aggregations (e.g. MAX, MIN, COUNT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FilterOperator(str, Enum):
    """Supported SQL comparison operators for filtering criteria."""
    EQ = "="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    LIKE = "LIKE"
    IN = "IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"


class OrderDirection(str, Enum):
    """Sorting directions for order-by conditions."""
    ASC = "ASC"
    DESC = "DESC"


class AggregateFunction(str, Enum):
    """SQL aggregation functions."""
    MAX = "MAX"
    MIN = "MIN"
    COUNT = "COUNT"
    SUM = "SUM"
    AVG = "AVG"


@dataclass
class FilterCondition:
    """A single WHERE condition in the criteria."""
    field: str
    operator: FilterOperator
    value: Any = None


@dataclass
class OrderCondition:
    """A single ORDER BY clause in the criteria."""
    field: str
    direction: OrderDirection = OrderDirection.ASC


@dataclass
class AggregateProjection:
    """An aggregation function applied to a column."""
    function: AggregateFunction
    field: str
    alias: str | None = None

    @property
    def output_alias(self) -> str:
        if self.alias:
            return self.alias
        return f"{self.function.value.lower()}_{self.field}"


@dataclass
class Criteria:
    """Declarative specification for a dynamic SQL query.

    Example usage::

        # Build a query to get the maximum timestamp from Telemetria_Tanque_N
        criteria = (
            Criteria.for_table("Telemetria_Tanque_N", schema="dbo")
            .select_max("timestamp", alias="last_val")
        )

        # Build a filtered query
        criteria = (
            Criteria.for_table("Telemetria_Tanque_N")
            .where("nivel_tanque_pct", ">", 50.0)
            .order_by_desc("timestamp")
            .take(10)
        )
    """
    table: str
    schema: str = "dbo"
    filters: list[FilterCondition] = field(default_factory=list)
    order_by: list[OrderCondition] = field(default_factory=list)
    limit: int | None = None
    offset: int | None = None
    select_fields: list[str] = field(default_factory=list)
    aggregate: AggregateProjection | None = None

    @classmethod
    def for_table(cls, table: str, schema: str = "dbo") -> "Criteria":
        """Start a new Criteria specification for the given table and schema."""
        return cls(table=table, schema=schema)

    def where(
        self,
        field_name: str,
        op: str | FilterOperator = FilterOperator.EQ,
        value: Any = None,
    ) -> "Criteria":
        """Add a filter condition to the WHERE clause."""
        if isinstance(op, str):
            op = FilterOperator(op)
        self.filters.append(FilterCondition(field_name, op, value))
        return self

    def order_by_asc(self, field_name: str) -> "Criteria":
        """Add an ascending ORDER BY clause."""
        self.order_by.append(OrderCondition(field_name, OrderDirection.ASC))
        return self

    def order_by_desc(self, field_name: str) -> "Criteria":
        """Add a descending ORDER BY clause."""
        self.order_by.append(OrderCondition(field_name, OrderDirection.DESC))
        return self

    def take(self, limit: int) -> "Criteria":
        """Set the maximum number of rows to return (LIMIT / TOP)."""
        self.limit = limit
        return self

    def skip(self, offset: int) -> "Criteria":
        """Set the number of rows to skip (OFFSET)."""
        self.offset = offset
        return self

    def select(self, *field_names: str) -> "Criteria":
        """Specify which columns to select."""
        self.select_fields.extend(field_names)
        return self

    def select_max(self, field_name: str, alias: str = "max_val") -> "Criteria":
        """Specify a MAX() aggregation projection."""
        self.aggregate = AggregateProjection(AggregateFunction.MAX, field_name, alias)
        return self

    def select_min(self, field_name: str, alias: str = "min_val") -> "Criteria":
        """Specify a MIN() aggregation projection."""
        self.aggregate = AggregateProjection(AggregateFunction.MIN, field_name, alias)
        return self

    def select_count(self, field_name: str = "*", alias: str = "cnt") -> "Criteria":
        """Specify a COUNT() aggregation projection."""
        self.aggregate = AggregateProjection(AggregateFunction.COUNT, field_name, alias)
        return self


def compile_criteria_to_sqlserver(
    criteria: Criteria,
) -> tuple[str, dict[str, Any]]:
    """Compile a Criteria object into a parameterized SQL Server T-SQL string and params dict.

    Returns:
        (sql_query_string, parameters_dict)
    """
    params: dict[str, Any] = {}
    full_table = f"[{criteria.schema}].[{criteria.table}]"

    # 1. SELECT clause
    if criteria.aggregate:
        agg = criteria.aggregate
        if agg.field == "*":
            field_expr = "*"
        else:
            field_expr = f"[{agg.field}]"
        select_clause = f"{agg.function.value}({field_expr}) AS [{agg.output_alias}]"
    elif criteria.select_fields:
        select_clause = ", ".join(f"[{f}]" for f in criteria.select_fields)
    else:
        select_clause = "*"

    # In SQL Server, TOP is used when there's no OFFSET
    top_clause = ""
    if criteria.limit is not None and criteria.offset is None:
        top_clause = f"TOP ({criteria.limit}) "

    # 2. WHERE clause
    where_parts: list[str] = []
    for i, filter_cond in enumerate(criteria.filters):
        param_name = f"p_{i}"
        if filter_cond.operator == FilterOperator.IS_NULL:
            where_parts.append(f"[{filter_cond.field}] IS NULL")
        elif filter_cond.operator == FilterOperator.IS_NOT_NULL:
            where_parts.append(f"[{filter_cond.field}] IS NOT NULL")
        elif filter_cond.operator == FilterOperator.IN and isinstance(filter_cond.value, (list, tuple)):
            in_params = []
            for j, val in enumerate(filter_cond.value):
                pname = f"{param_name}_{j}"
                in_params.append(f":{pname}")
                params[pname] = val
            where_parts.append(f"[{filter_cond.field}] IN ({', '.join(in_params)})")
        else:
            where_parts.append(f"[{filter_cond.field}] {filter_cond.operator.value} :{param_name}")
            params[param_name] = filter_cond.value

    where_clause = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""

    # 3. ORDER BY clause
    order_clause = ""
    if criteria.order_by:
        orders = [f"[{o.field}] {o.direction.value}" for o in criteria.order_by]
        order_clause = f" ORDER BY {', '.join(orders)}"
    elif criteria.offset is not None:
        # SQL Server OFFSET requires an ORDER BY clause; default to first selected field or (SELECT NULL)
        default_order = f"[{criteria.select_fields[0]}]" if criteria.select_fields else "(SELECT NULL)"
        order_clause = f" ORDER BY {default_order}"

    # 4. OFFSET / FETCH clause (for pagination)
    paging_clause = ""
    if criteria.offset is not None:
        paging_clause = f" OFFSET {criteria.offset} ROWS"
        if criteria.limit is not None:
            paging_clause += f" FETCH NEXT {criteria.limit} ROWS ONLY"

    query = f"SELECT {top_clause}{select_clause} FROM {full_table}{where_clause}{order_clause}{paging_clause};"
    return query, params
