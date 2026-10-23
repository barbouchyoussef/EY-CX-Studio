"""Aggregate queries behind the admin dashboard. Read-only reporting over existing tables.
"""

from app.services.analytics.admin_analytics_service import AdminAnalyticsService

__all__ = ["AdminAnalyticsService"]
