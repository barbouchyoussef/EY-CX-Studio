"""FastAPI dependency providers.

`get_db` yields a request-scoped session; `get_current_user` turns a Bearer token into an active
User or raises 401. These two are what every protected route is built from.
"""
