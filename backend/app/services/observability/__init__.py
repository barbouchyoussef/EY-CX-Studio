"""Per-call LLM metering: tokens, latency, cost and outcome into the `llm_calls` table.

That table is the only record of what the platform actually spends, and it is what proved most
failures were a configuration error rather than a rate limit.
"""
