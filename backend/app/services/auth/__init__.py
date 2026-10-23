"""Identity and authorisation.

`security.py` holds password hashing and token minting; `access.py` is the single place that
decides whether a user may see a given record. Scattering that decision across routes is exactly
what this package exists to prevent.
"""
