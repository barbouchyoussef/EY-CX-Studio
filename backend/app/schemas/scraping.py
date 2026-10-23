from pydantic import BaseModel, model_validator

from app.schemas.manual_analysis import ManualAnalysisWorkbook


class ScrapeRequest(BaseModel):
    brand_name: str
    # Country or city the brand operates in, e.g. "Tunisie". Without it a brand-name search
    # matches same-named businesses worldwide and blends them into one sentiment number --
    # a search for "Mytek" returned IT firms in Phoenix and wholesalers in Mexico.
    google_location: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    # Brand mention keywords to search public Facebook posts & comments by keyword (e.g. "tunisie telecom", "mytek tn")
    keywords: str | None = None
    # Trustpilot company domain, e.g. "orange.fr". Optional: skipped when not provided,
    # because resolving it from the brand name alone is unreliable.
    trustpilot_domain: str | None = None
    # Restrict Trustpilot reviews to a recent window so the scrape matches the reporting period.
    trustpilot_period: str | None = None  # "", last30days, last3months, last6months, last12months
    manual_analysis: ManualAnalysisWorkbook | None = None


class ReviewClassification(BaseModel):
    sentiment: str  # "positive", "neutral", "negative"
    confidence: float
    themes: list[str]
    complaint_category: str | None = None
    # True when the post is promotional/advertising (a product/offer announcement, giveaway,
    # affiliate spam) rather than genuine customer feedback. These are dropped from the analysis.
    is_advertisement: bool = False


class ScrapedReview(BaseModel):
    platform: str
    author: str | None = None
    text: str
    rating: float | None = None
    date: str | None = None
    url: str | None = None
    classification: ReviewClassification | None = None
    # Where a review came from within its platform. For Facebook: "page" (the brand's official
    # page/comments) vs "keyword" (a public keyword-search mention). None for platforms without
    # this distinction.
    source: str | None = None


class PlatformResult(BaseModel):
    platform: str
    status: str  # "success", "error", "empty"
    review_count: int = 0
    reviews: list[ScrapedReview] = []
    error_message: str | None = None
    # Optional platform-level headline stat, e.g. "TrustScore 1.6/5 · 12,665 reviews".
    summary_stat: str | None = None
    # Share of scraped reviews the brand publicly replied to (Trustpilot exposes this).
    reply_rate_pct: float | None = None
    # Which real-world places/pages the reviews came from, so a consultant can verify the
    # scrape hit the right company rather than a same-named business elsewhere.
    matched_places: list[str] = []
    # Places dropped because they sat outside the requested location.
    excluded_places: list[str] = []


class TopicCount(BaseModel):
    topic: str
    count: int


class AnalysisSummary(BaseModel):
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    top_themes: list[str]
    top_complaints: list[TopicCount]
    summary_text: str | None = None


class ChannelReportSection(BaseModel):
    channel: str
    summary: str
    strengths: list[str] = []
    friction_points: list[str] = []
    key_stats: list[str] = []  # short "label: value" style stat lines, e.g. "Engagement rate: 3.1%"


class FrictionPoint(BaseModel):
    theme: str
    source: str  # "scraped" | "consultant" | "both"
    description: str
    supporting_evidence: list[str] = []
    # The ranked label this point maps to, echoed back by the LLM from the list it was
    # given. Used to attach real volume in code -- so "billing errors" carries "34 mentions,
    # 28% of negative reviews" instead of an unquantified assertion.
    related_label: str | None = None
    mention_count: int | None = None
    share_pct: float | None = None


class SentimentBreakdown(BaseModel):
    """Deterministic sentiment split computed from the AI-classified scraped reviews
    (not produced by the report LLM, so the numbers are trustworthy)."""
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    classified_count: int


class PlatformSentiment(BaseModel):
    """Per-channel sentiment, so the report can name which channel is worst rather than
    averaging every channel into one meaningless number."""
    platform: str
    positive_pct: float
    neutral_pct: float
    negative_pct: float
    classified_count: int
    review_count: int
    avg_rating: float | None = None
    summary_stat: str | None = None
    reply_rate_pct: float | None = None


class RatingDistribution(BaseModel):
    """Star histogram across all rated reviews. A 1.8 average made of 1s and 5s is a very
    different problem from a 1.8 average made entirely of 2s."""
    one: int = 0
    two: int = 0
    three: int = 0
    four: int = 0
    five: int = 0
    total: int = 0
    average: float | None = None


class ThemeFrequency(BaseModel):
    """A theme or complaint category with the volume behind it."""
    label: str
    count: int
    share_pct: float
    negative_pct: float = 0.0
    # Which channels the mentions came from, e.g. {"Google Maps": 6, "Trustpilot": 2}.
    # A consultant needs to know where a complaint surfaces before they can act on it.
    by_platform: dict[str, int] = {}


class ThemeVerbatim(BaseModel):
    """A real customer quote backing a ranked theme, with its provenance intact."""
    label: str
    platform: str
    text: str
    rating: float | None = None
    date: str | None = None
    sentiment: str | None = None
    # Link to the original review, so a quote can be verified at source rather than trusted.
    url: str | None = None
    # For Facebook: "page" vs "keyword" (see ScrapedReview.source).
    source: str | None = None


class RatingSentimentCheck(BaseModel):
    """Where the star rating and what the customer wrote disagree.

    Computed only over reviews that carry both a rating and a classified comment. A high
    rating with a negative comment (or the reverse) is a known signal -- rating inflation,
    sarcasm, or review-gaming -- and the size of the gap is itself a CX finding.
    """

    both_count: int = 0  # reviews with a rating AND a classified comment
    high_rating_negative: int = 0  # rated >= 4 but the text reads negative
    low_rating_positive: int = 0  # rated <= 2 but the text reads positive
    mismatch_count: int = 0
    mismatch_pct: float = 0.0


class TrendPoint(BaseModel):
    """One period on the time axis.

    `negative_pct` and `avg_rating` are null when that period's sample is too small to state
    them -- a break in the line is honest, a plotted point on n=3 is not.
    """

    period: str  # "2026-07" or "2026-Q3"
    label: str  # "Jul 2026" / "Q3 2026"
    reviews: int = 0
    classified_count: int = 0
    negative_pct: float | None = None
    # Positive/neutral share of the period, for the sentiment-mix area (null on too-small samples).
    positive_pct: float | None = None
    neutral_pct: float | None = None
    avg_rating: float | None = None


class TrendSeries(BaseModel):
    """Present only when the collected reviews can support a time axis at all."""

    granularity: str  # "month" | "quarter"
    points: list[TrendPoint] = []
    # Which metric cleared the sample floor often enough to be worth plotting.
    has_sentiment: bool = False
    has_rating: bool = False
    min_sample: int = 10


class TopicMovement(BaseModel):
    """One complaint category's change in share between the earlier and recent windows.

    Shares are of all classified feedback in each window, so a rise means the category grew
    as a proportion of what customers talked about -- not merely that more reviews arrived.
    """

    label: str
    earlier_count: int
    recent_count: int
    earlier_share: float  # % of classified reviews in the earlier window
    recent_share: float
    delta: float  # recent_share - earlier_share, in percentage points
    direction: str  # "rising" | "falling" | "stable"


class TopicMomentum(BaseModel):
    """Which complaints are gaining or losing ground. Present only when each half of the
    history carries a real sample -- otherwise a movement would just be noise."""

    earlier_label: str  # e.g. "Aug 2025 – Jan 2026"
    recent_label: str
    earlier_total: int  # classified reviews in the earlier window
    recent_total: int
    items: list[TopicMovement] = []


class ReportEvidence(BaseModel):
    """The quantitative backbone of the report. Every field is computed in Python from the
    classified reviews -- the LLM writes the narrative around these numbers, never them."""
    reviews_collected: int = 0
    # Reviews carrying an actual comment. The rest are star-only ratings, which count toward
    # the distribution but have nothing to classify.
    reviews_with_text: int = 0
    reviews_classified: int = 0
    overall_sentiment: SentimentBreakdown | None = None
    platform_sentiment: list[PlatformSentiment] = []
    rating_distribution: RatingDistribution | None = None
    top_themes: list[ThemeFrequency] = []
    top_complaints: list[ThemeFrequency] = []
    verbatims: list[ThemeVerbatim] = []
    # Null whenever review volume per period is too thin to plot -- the report then simply
    # has no trend section rather than showing sampling noise as a trend.
    trend: TrendSeries | None = None
    # Which complaint categories are gaining or losing share over the collected history.
    # Null when each half of the history is too thin for the comparison to mean anything.
    momentum: TopicMomentum | None = None
    # Reviews-weighted share of reviews the brand publicly replied to, across the channels
    # that expose it (Trustpilot). None when no channel reports it.
    reply_rate_pct: float | None = None
    # How many reviews that rate rests on -- a 0% on 8 reviews must not read as covering 200.
    reply_rate_base: int = 0
    # Disagreement between star rating and comment sentiment; None when too few reviews carry
    # both to say anything.
    rating_sentiment: RatingSentimentCheck | None = None


class _CoercibleFromString(BaseModel):
    """Accepts either the structured object or the bare string it used to be.

    Both `top_strengths` and `recommendations` shipped as `list[str]`. Reports already on
    disk still hold strings, and a model that ignores the schema will send them too, so the
    plain form has to keep validating rather than raising.
    """

    text: str

    @model_validator(mode="before")
    @classmethod
    def _accept_plain_string(cls, value: object) -> object:
        if isinstance(value, str):
            return {"text": value}
        return value


class Strength(_CoercibleFromString):
    """A cross-channel strength, carrying the same evidence a friction point does.

    Left unquantified, a positive sitting beside a friction point badged '47 mentions · 16%'
    reads as opinion next to fact.
    """

    related_label: str | None = None
    mention_count: int | None = None
    share_pct: float | None = None


class Recommendation(_CoercibleFromString):
    """An action, tied to the friction point it resolves.

    A recommendation the reader cannot trace back to a measured problem is the least
    defensible thing in a client deliverable, and it is the section they act on.
    """

    # Theme of the friction point this addresses; matched against the report's own points.
    addresses: str | None = None
    mention_count: int | None = None
    share_pct: float | None = None


class DetailedSocialReport(BaseModel):
    executive_summary: str
    overall_sentiment: SentimentBreakdown | None = None  # populated in code from scraped reviews
    evidence: ReportEvidence | None = None  # populated in code; never generated by the LLM
    channel_breakdown: list[ChannelReportSection] = []
    top_strengths: list[Strength] = []
    top_friction_points: list[FrictionPoint] = []
    website_assessment: str | None = None
    recommendations: list[Recommendation] = []
    methodology_note: str


class ScrapingResponse(BaseModel):
    brand_name: str
    scraped_at: str
    platforms: list[PlatformResult]
    total_reviews: int
    analysis: AnalysisSummary | None = None
    detailed_report: DetailedSocialReport | None = None
    # The consultant's raw workbook is echoed back and saved with the report. Filling it in
    # is an hour of work, and without this it survived only in browser storage: a cleared
    # browser lost it, past reports could not be regenerated against an improved prompt,
    # and there was no record of where a figure in the report came from.
    manual_analysis: ManualAnalysisWorkbook | None = None
    # The saved report's filename (set at archive time). Lets the UI address this report --
    # e.g. to open the report chatbot against it -- for both fresh runs and reloaded archives.
    report_filename: str | None = None


class CompanyOption(BaseModel):
    id: int
    name: str
