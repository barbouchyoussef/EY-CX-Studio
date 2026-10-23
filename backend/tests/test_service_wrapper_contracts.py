import importlib


def test_llm_package_exports_match_canonical_modules():
    pkg = importlib.import_module("app.services.llm")
    facade = importlib.import_module("app.services.llm.core.facade_service")
    prompts = importlib.import_module("app.services.llm.prompts.templates")

    assert pkg.LLMService is facade.LLMService
    assert pkg.ChatTurn is facade.ChatTurn
    assert pkg.build_llm_service is facade.build_llm_service
    assert hasattr(prompts, "QUESTION_SYSTEM_PROMPT_GUIDED")


def test_analytics_package_exports_match_canonical_module():
    pkg = importlib.import_module("app.services.analytics")
    feature = importlib.import_module("app.services.analytics.admin_analytics_service")
    assert pkg.AdminAnalyticsService is feature.AdminAnalyticsService
