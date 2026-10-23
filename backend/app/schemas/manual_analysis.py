"""Schemas for the consultant-filled 'Social Media & Website Analysis' Excel template."""

from pydantic import BaseModel


class ChannelPost(BaseModel):
    date: str | None = None
    post: str | None = None
    likes: float | None = None
    comments: float | None = None
    shares: float | None = None
    total_engagement: float | None = None
    notes: str | None = None


class ChannelAnalysis(BaseModel):
    channel: str
    account_handle: str | None = None

    followers_growth: str | None = None
    page_verification: str | None = None
    engagement_rate: str | None = None
    post_interaction_rate: str | None = None
    response_time_to_comments: str | None = None
    response_quality: str | None = None
    posting_frequency: str | None = None
    content_format_variety: str | None = None
    campaign: str | None = None
    complaints_handling: str | None = None
    resolution_effectiveness: str | None = None
    sentiment_analysis: str | None = None

    posts: list[ChannelPost] = []
    avg_likes: float | None = None
    avg_comments: float | None = None
    avg_shares: float | None = None
    avg_engagement: float | None = None

    notes: str | None = None

    def has_any_data(self) -> bool:
        metric_fields = (
            self.account_handle,
            self.followers_growth,
            self.page_verification,
            self.engagement_rate,
            self.post_interaction_rate,
            self.response_time_to_comments,
            self.response_quality,
            self.posting_frequency,
            self.content_format_variety,
            self.campaign,
            self.complaints_handling,
            self.resolution_effectiveness,
            self.sentiment_analysis,
            self.notes,
        )
        return any(f for f in metric_fields) or len(self.posts) > 0


class WebsiteTraffic(BaseModel):
    total_visits: str | None = None
    desktop_share: str | None = None
    mobile_share: str | None = None
    pages_per_visit: str | None = None
    bounce_rate: str | None = None
    avg_visit_duration: str | None = None

    def has_any_data(self) -> bool:
        return any(
            (
                self.total_visits,
                self.desktop_share,
                self.mobile_share,
                self.pages_per_visit,
                self.bounce_rate,
                self.avg_visit_duration,
            )
        )


class WebsiteAnalysis(BaseModel):
    url: str | None = None
    sections: list[str] = []
    traffic: WebsiteTraffic = WebsiteTraffic()

    def has_any_data(self) -> bool:
        return bool(self.url) or bool(self.sections) or self.traffic.has_any_data()


class ThemeInsight(BaseModel):
    theme: str
    type: str | None = None  # "Friction point" | "Like"
    source: str | None = None  # channel name
    description: str | None = None
    opinions_count: int | None = None
    share_of_mentions: float | None = None  # stored as a 0-1 fraction
    examples: str | None = None
    interpretation: str | None = None


class ManualAnalysisWorkbook(BaseModel):
    company_name: str | None = None
    reporting_period: str | None = None
    analyst: str | None = None

    channels: list[ChannelAnalysis] = []
    website: WebsiteAnalysis | None = None
    themes: list[ThemeInsight] = []


class ManualAnalysisParseResponse(BaseModel):
    workbook: ManualAnalysisWorkbook
    warnings: list[str] = []
