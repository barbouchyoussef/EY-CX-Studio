from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.assessments import router as assessments_router
from app.api.routes.reference import router as reference_router
from app.api.routes.consultations import router as consultations_router
from app.api.routes.admin_reference import router as admin_reference_router
from app.api.routes.admin_capability import router as admin_capability_router
from app.api.routes.admin_analytics import router as admin_analytics_router
from app.api.routes.scraping import router as scraping_router
from app.api.routes.desk_research import router as desk_research_router
from app.api.routes.projects import router as projects_router, shares_router
from app.api.routes.respondent import router as respondent_router
from app.api.routes.issue_log import router as issue_log_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(assessments_router, tags=["assessments"])
api_router.include_router(reference_router, tags=["reference"])
# There is deliberately no /client router. A legacy /client/turn endpoint used to take an
# assessment_id straight from the request body with no credential, so anyone could drive any
# assessment by guessing an integer. The passwordless client path is /respondent/*, which
# resolves an X-Respondent-Token to exactly one assessment.
# test_admin_authorization.py asserts /client/turn stays unroutable.
api_router.include_router(consultations_router, tags=["consultations"])
api_router.include_router(admin_reference_router, tags=["admin-reference"])
api_router.include_router(admin_capability_router, tags=["admin-capability"])
api_router.include_router(admin_analytics_router, tags=["admin-analytics"])
api_router.include_router(scraping_router, tags=["scraping"])
api_router.include_router(desk_research_router, tags=["desk-research"])
api_router.include_router(projects_router, tags=["projects"])
api_router.include_router(respondent_router)
api_router.include_router(shares_router, tags=["shares"])
api_router.include_router(issue_log_router, tags=["issue-log"])

