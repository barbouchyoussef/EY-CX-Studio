"""Reusable RAG engine: chunk -> embed -> store -> retrieve -> answer.

Module-agnostic. Each product module (Desk Research first) feeds chunks under its own namespace
and reuses the shared retrieval/answering, so only the *data source* differs -- not the chatbot.
"""
