"""SQLAlchemy ORM models -- the shape of the 36 tables.

Schema changes are made by hand-written numbered SQL in `migrations/`, not generated from these
classes: a model edited without a matching migration will not exist in any real database.
"""

from app.db.models.assessment import Assessment
from app.db.models.assessment_answer import AssessmentAnswer
from app.db.models.assessment_axis_memory import AssessmentAxisMemory
from app.db.models.assessment_idempotency import AssessmentIdempotency
from app.db.models.assessment_insight import AssessmentInsight
from app.db.models.assessment_score import AssessmentScore
from app.db.models.axis import Axis
from app.db.models.axis_maturity_content import AxisMaturityContent
from app.db.models.capability import Capability
from app.db.models.capability_maturity_content import CapabilityMaturityContent
from app.db.models.capability_maturity_rubric import CapabilityMaturityRubric
from app.db.models.capability_quick_win_template import CapabilityQuickWinTemplate
from app.db.models.company_size import CompanySize
from app.db.models.company import Company
from app.db.models.maturity_level import MaturityLevel
from app.db.models.recommendation_output import RecommendationOutput
from app.db.models.region import Region
from app.db.models.sector import Sector
from app.db.models.interview_guide import InterviewGuide
from app.db.models.scraping_job import ScrapingJob
from app.db.models.user import Invite, PasswordResetToken, RefreshToken, User
from app.db.models.project import Project, ProjectArtifact, ProjectMember, ProjectStep
from app.db.models.project_interview_report import ProjectInterviewReport
from app.db.models.share import AnalysisShare
from app.db.models.assessment_recipient import AssessmentRecipient
from app.db.models.llm_call import LLMCall
from app.db.models.issue_log import IssueLog

__all__ = [
    "Assessment",
    "AssessmentAnswer",
    "AssessmentAxisMemory",
    "AssessmentIdempotency",
    "AssessmentInsight",
    "AssessmentScore",
    "Axis",
    "AxisMaturityContent",
    "Capability",
    "CapabilityMaturityContent",
    "CapabilityMaturityRubric",
    "CapabilityQuickWinTemplate",
    "CompanySize",
    "Company",
    "MaturityLevel",
    "RecommendationOutput",
    "Region",
    "Sector",
    "InterviewGuide",
    "ScrapingJob",
    "User",
    "Invite",
    "RefreshToken",
    "PasswordResetToken",
    "Project",
    "ProjectInterviewReport",
    "ProjectMember",
    "ProjectStep",
    "ProjectArtifact",
    "AnalysisShare",
    "AssessmentRecipient",
    "LLMCall",
    "IssueLog",
]
