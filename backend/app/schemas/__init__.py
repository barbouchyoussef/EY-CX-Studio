"""Pydantic request and response models -- the API's contract with the frontend.

Distinct from `db/models`: those describe storage, these describe what crosses the wire. The two
diverge on purpose, so an internal column can change without altering the public shape.
"""
