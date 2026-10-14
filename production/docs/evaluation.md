# Evaluate before release

## Execution and business accuracy

Build a version-controlled set of representative questions with reviewed SQL and expected
results against a fixed dataset. Compare result sets after normalizing order where order
does not matter, numeric precision, and date representations. SQL string similarity is
not an accuracy metric: different SQL can return the same correct result.

Cover total revenue, monthly revenue, category joins, distinct customers, filters,
empty results, cancellation/refunds, duplicate joins, nulls, and date boundaries. Add
questions outside the supported grammar and ambiguous requests that should clarify.

The synthetic integration fixtures have known expected totals: tenant A north 300,
tenant A all regions 1,000, and tenant B north 9,000. These exercise the demo provider
and database path; they do not measure an external LLM's SQL accuracy.

## Security regression

The tests include multiple statements, writes in CTEs, unsafe functions, catalog access,
wrong schemas, unknown columns, cross-tenant history access, and export approval controls.
Extend them whenever adding syntax/functions, datasets, roles, authentication flows,
or caching. Run adversarial questions against each supported real model as well as
direct validator tests. A model should never be the final authorization decision-maker.

## Generation and charts

Review whether narrative claims match returned rows, units and time range are stated,
truncation is disclosed, empty results are handled, and charts reference actual columns.
Check chart suitability and aggregation semantics with human-reviewed examples.
The code validates chart fields and renders trusted Plotly functions; it does not execute
model-provided Python or guarantee that every proposed chart is analytically appropriate.

## Reliability and performance

Test worker termination before/after each node, model 429/5xx, invalid JSON, exhausted
budgets, database timeouts, concurrent duplicate requests, pool saturation, and permissions
changed during execution. Record successful answer rate, result correctness, rejection
precision/recall, p50/p95 latency, and provider tokens/cost. Publish observed measurements
with dataset/model/dependency versions; do not present illustrative targets as results.
