"""All SQL lives here. Services call repositories; services never build queries themselves.

Keeping data access in one layer is what makes a service testable without a database and what
stops the same join being written five slightly different ways.
"""
