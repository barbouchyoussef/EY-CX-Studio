"""Transactional mail -- invitations, password resets, client assessment links.

Degrades rather than fails: with SMTP unconfigured, callers fall back to showing the link on
screen instead of raising.
"""
