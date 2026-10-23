"""The CX Studio backend: a FastAPI application serving five analysis modules.

Layering runs api/routes -> services -> repositories -> db/models. Routes stay thin and own
HTTP concerns only; business logic lives in services; all SQL is in repositories.
"""
