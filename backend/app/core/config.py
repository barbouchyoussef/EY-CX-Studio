import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    # Keep it tolerant on Windows where .env is often saved as cp1252/latin-1.
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            load_dotenv(dotenv_path=env_path, encoding=encoding, override=True)
            return
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("env", b"", 0, 1, "Unable to decode .env with utf-8, cp1252, or latin-1")


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    database_url: str
    mistral_api_key: str | None
    mistral_model: str
    mistral_base_url: str
    moonshot_api_key: str | None
    moonshot_model: str
    moonshot_base_url: str
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str
    langsearch_api_key: str | None
    langsearch_base_url: str
    apify_api_token: str | None
    consultation_receiver_email: str | None
    metabase_site_url: str | None
    metabase_embed_secret: str | None
    metabase_dashboard_id: int | None
    llm_request_timeout_seconds: float
    llm_max_history_turns: int
    llm_max_history_chars: int
    llm_temperature: float
    llm_max_tokens: int | None
    scoring_default_confidence_if_covered: float
    scoring_default_confidence_if_not_covered: float
    scoring_min_confidence_to_score: float
    scoring_max_capabilities_per_answer: int
    scoring_min_evidence_text_len: int
    scoring_min_rationale_text_len: int
    chat_max_extra_questions_per_axis: int
    chat_max_clarifications_per_focus: int
    chat_max_insufficient_evidence_retries: int
    recommendation_max_actions_per_capability: int
    recommendation_max_words_per_capability: int
    recommendation_min_confidence: float
    recommendation_medium_evidence_min_chars: int
    recommendation_strong_evidence_min_chars: int
    report_medium_confidence_threshold: float
    report_high_confidence_threshold: float
    report_medium_evidence_min_chars: int
    report_high_evidence_min_chars: int
    maturity_average_basic_threshold: float
    maturity_average_established_threshold: float
    maturity_score_basic_threshold: float
    maturity_score_established_threshold: float
    benchmark_langsearch_max_requests_per_second: int
    benchmark_langsearch_max_requests_per_minute: int
    benchmark_langsearch_max_requests_per_day: int
    benchmark_mistral_max_requests_per_second: int
    benchmark_mistral_max_requests_per_minute: int
    benchmark_mistral_max_requests_per_day: int
    benchmark_max_candidates_initial: int
    benchmark_max_candidates_refresh: int
    benchmark_max_langsearch_docs_per_candidate: int
    benchmark_max_mistral_calls_per_assessment: int
    benchmark_provider_cooldown_seconds: float
    benchmark_max_concurrent_jobs: int
    # --- Auth / identity ---
    jwt_secret: str
    access_token_minutes: int
    refresh_token_days: int
    invite_expire_hours: int
    cookie_secure: bool
    cookie_samesite: str
    cookie_domain: str | None
    password_reset_expire_hours: int
    # --- Email (transactional: invites, password reset) ---
    app_base_url: str
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_use_tls: bool
    email_from: str | None
    email_from_name: str

    @property
    def LLM_REQUEST_TIMEOUT_SECONDS(self) -> float:
        return self.llm_request_timeout_seconds

    @property
    def LLM_MAX_HISTORY_TURNS(self) -> int:
        return self.llm_max_history_turns

    @property
    def LLM_MAX_HISTORY_CHARS(self) -> int:
        return self.llm_max_history_chars

    @property
    def LLM_TEMPERATURE(self) -> float:
        return self.llm_temperature

    @property
    def LLM_MAX_TOKENS(self) -> int | None:
        return self.llm_max_tokens

    @property
    def SCORING_MIN_CONFIDENCE_TO_SCORE(self) -> float:
        return self.scoring_min_confidence_to_score

    @property
    def SCORING_MAX_CAPABILITIES_PER_ANSWER(self) -> int:
        return self.scoring_max_capabilities_per_answer

    @property
    def SCORING_MIN_EVIDENCE_TEXT_LEN(self) -> int:
        return self.scoring_min_evidence_text_len

    @property
    def CHAT_MAX_EXTRA_QUESTIONS_PER_AXIS(self) -> int:
        return self.chat_max_extra_questions_per_axis

    @property
    def CHAT_MAX_CLARIFICATIONS_PER_FOCUS(self) -> int:
        return self.chat_max_clarifications_per_focus

    @property
    def MAX_ACTIONS_PER_CAPABILITY(self) -> int:
        return self.recommendation_max_actions_per_capability

    @property
    def MAX_WORDS_PER_CAPABILITY(self) -> int:
        return self.recommendation_max_words_per_capability

    @property
    def RECOMMENDATION_MIN_CONFIDENCE(self) -> float:
        return self.recommendation_min_confidence

    @property
    def REPORT_MEDIUM_CONFIDENCE_THRESHOLD(self) -> float:
        return self.report_medium_confidence_threshold

    @property
    def REPORT_HIGH_CONFIDENCE_THRESHOLD(self) -> float:
        return self.report_high_confidence_threshold


def _to_async_database_url(database_url: str) -> str:
    database_url = database_url.strip()
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql+psycopg2://"):
        return database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    raise ValueError("DATABASE_URL must use a PostgreSQL URL compatible with postgresql+asyncpg://")


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    load_env_file()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    database_url = _to_async_database_url(database_url)

    app_env = os.getenv("APP_ENV", "development")

    # Fail closed on the signing key: a missing secret is only tolerated in development
    # (with a clearly-insecure fallback so a fresh clone still boots). In any other
    # environment an unset JWT_SECRET is a hard error rather than a guessable key.
    jwt_secret = os.getenv("JWT_SECRET")
    if not jwt_secret:
        if app_env == "development":
            jwt_secret = "dev-insecure-secret-do-not-use-in-production"
        else:
            raise ValueError("JWT_SECRET is required when APP_ENV is not 'development'")

    return Settings(
        app_name=os.getenv("APP_NAME", "CX Assessment API"),
        app_env=app_env,
        database_url=database_url,
        mistral_api_key=os.getenv("MISTRAL_API_KEY"),
        mistral_model=os.getenv("MISTRAL_MODEL", "ministral-8b-latest"),
        mistral_base_url=os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1"),
        moonshot_api_key=os.getenv("MOONSHOT_API_KEY"),
        moonshot_model=os.getenv("MOONSHOT_MODEL", "moonshot-v1-8k"),
        moonshot_base_url=os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1"),
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        langfuse_host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        langsearch_api_key=os.getenv("LANGSEARCH_API_KEY"),
        langsearch_base_url=os.getenv("LANGSEARCH_BASE_URL", "https://api.langsearch.com/v1"),
        apify_api_token=os.getenv("APIFY_API_TOKEN"),
        consultation_receiver_email=os.getenv("CONSULTATION_RECEIVER_EMAIL"),
        metabase_site_url=os.getenv("METABASE_SITE_URL"),
        metabase_embed_secret=os.getenv("METABASE_EMBED_SECRET"),
        metabase_dashboard_id=int(os.getenv("METABASE_DASHBOARD_ID")) if os.getenv("METABASE_DASHBOARD_ID") else None,
        llm_request_timeout_seconds=_get_float("LLM_REQUEST_TIMEOUT_SECONDS", 300.0),
        llm_max_history_turns=_get_int("LLM_MAX_HISTORY_TURNS", 12),
        llm_max_history_chars=_get_int("LLM_MAX_HISTORY_CHARS", 6000),
        llm_temperature=_get_float("LLM_TEMPERATURE", 0.2),
        llm_max_tokens=_get_int("LLM_MAX_TOKENS", 0) or None,
        scoring_default_confidence_if_covered=_get_float("SCORING_DEFAULT_CONFIDENCE_IF_COVERED", 0.8),
        scoring_default_confidence_if_not_covered=_get_float("SCORING_DEFAULT_CONFIDENCE_IF_NOT_COVERED", 0.0),
        scoring_min_confidence_to_score=_get_float("SCORING_MIN_CONFIDENCE_TO_SCORE", 0.75),
        scoring_max_capabilities_per_answer=_get_int("SCORING_MAX_CAPABILITIES_PER_ANSWER", 2),
        scoring_min_evidence_text_len=_get_int("SCORING_MIN_EVIDENCE_TEXT_LEN", 4),
        scoring_min_rationale_text_len=_get_int("SCORING_MIN_RATIONALE_TEXT_LEN", 42),
        chat_max_extra_questions_per_axis=_get_int("CHAT_MAX_EXTRA_QUESTIONS_PER_AXIS", 1),
        chat_max_clarifications_per_focus=_get_int("CHAT_MAX_CLARIFICATIONS_PER_FOCUS", 2),
        chat_max_insufficient_evidence_retries=_get_int("CHAT_MAX_INSUFFICIENT_EVIDENCE_RETRIES", 1),
        recommendation_max_actions_per_capability=_get_int("MAX_ACTIONS_PER_CAPABILITY", 2),
        recommendation_max_words_per_capability=_get_int("MAX_WORDS_PER_CAPABILITY", 120),
        recommendation_min_confidence=_get_float("RECOMMENDATION_MIN_CONFIDENCE", 0.80),
        recommendation_medium_evidence_min_chars=_get_int("RECOMMENDATION_MEDIUM_EVIDENCE_MIN_CHARS", 30),
        recommendation_strong_evidence_min_chars=_get_int("RECOMMENDATION_STRONG_EVIDENCE_MIN_CHARS", 40),
        report_medium_confidence_threshold=_get_float("REPORT_MEDIUM_CONFIDENCE_THRESHOLD", 0.70),
        report_high_confidence_threshold=_get_float("REPORT_HIGH_CONFIDENCE_THRESHOLD", 0.85),
        report_medium_evidence_min_chars=_get_int("REPORT_MEDIUM_EVIDENCE_MIN_CHARS", 70),
        report_high_evidence_min_chars=_get_int("REPORT_HIGH_EVIDENCE_MIN_CHARS", 110),
        maturity_average_basic_threshold=_get_float("MATURITY_AVERAGE_BASIC_THRESHOLD", 1.67),
        maturity_average_established_threshold=_get_float("MATURITY_AVERAGE_ESTABLISHED_THRESHOLD", 2.34),
        maturity_score_basic_threshold=_get_float("MATURITY_SCORE_BASIC_THRESHOLD", 40.0),
        maturity_score_established_threshold=_get_float("MATURITY_SCORE_ESTABLISHED_THRESHOLD", 75.0),
        benchmark_langsearch_max_requests_per_second=_get_int("BENCHMARK_LANGSEARCH_MAX_REQUESTS_PER_SECOND", 1),
        benchmark_langsearch_max_requests_per_minute=_get_int("BENCHMARK_LANGSEARCH_MAX_REQUESTS_PER_MINUTE", 20),
        benchmark_langsearch_max_requests_per_day=_get_int("BENCHMARK_LANGSEARCH_MAX_REQUESTS_PER_DAY", 2000),
        benchmark_mistral_max_requests_per_second=_get_int("BENCHMARK_MISTRAL_MAX_REQUESTS_PER_SECOND", 1),
        benchmark_mistral_max_requests_per_minute=_get_int("BENCHMARK_MISTRAL_MAX_REQUESTS_PER_MINUTE", 12),
        benchmark_mistral_max_requests_per_day=_get_int("BENCHMARK_MISTRAL_MAX_REQUESTS_PER_DAY", 1200),
        benchmark_max_candidates_initial=_get_int("BENCHMARK_MAX_CANDIDATES_INITIAL", 4),
        benchmark_max_candidates_refresh=_get_int("BENCHMARK_MAX_CANDIDATES_REFRESH", 6),
        benchmark_max_langsearch_docs_per_candidate=_get_int("BENCHMARK_MAX_LANGSEARCH_DOCS_PER_CANDIDATE", 8),
        benchmark_max_mistral_calls_per_assessment=_get_int("BENCHMARK_MAX_MISTRAL_CALLS_PER_ASSESSMENT", 4),
        benchmark_provider_cooldown_seconds=_get_float("BENCHMARK_PROVIDER_COOLDOWN_SECONDS", 120.0),
        benchmark_max_concurrent_jobs=_get_int("BENCHMARK_MAX_CONCURRENT_JOBS", 1),
        jwt_secret=jwt_secret,
        access_token_minutes=_get_int("ACCESS_TOKEN_MINUTES", 45),
        refresh_token_days=_get_int("REFRESH_TOKEN_DAYS", 14),
        invite_expire_hours=_get_int("INVITE_EXPIRE_HOURS", 168),
        cookie_secure=_get_bool("COOKIE_SECURE", app_env != "development"),
        cookie_samesite=os.getenv("COOKIE_SAMESITE", "strict"),
        cookie_domain=os.getenv("COOKIE_DOMAIN") or None,
        password_reset_expire_hours=_get_int("PASSWORD_RESET_EXPIRE_HOURS", 2),
        # Render injects RENDER_EXTERNAL_URL (e.g. https://ey-internship.onrender.com) automatically,
        # so invite/reset links point at the live site with no manual config; falls back to
        # APP_BASE_URL, then localhost for dev.
        app_base_url=(os.getenv("RENDER_EXTERNAL_URL") or os.getenv("APP_BASE_URL", "http://localhost:5173")).rstrip("/"),
        smtp_host=os.getenv("SMTP_HOST") or None,
        smtp_port=_get_int("SMTP_PORT", 587),
        smtp_username=os.getenv("SMTP_USERNAME") or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        smtp_use_tls=_get_bool("SMTP_USE_TLS", True),
        email_from=os.getenv("EMAIL_FROM") or None,
        email_from_name=os.getenv("EMAIL_FROM_NAME", "EY CX Studio"),
    )
