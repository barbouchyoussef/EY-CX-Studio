"""Maps a free-text company name onto the sector and size options the assessment offers.
"""

from app.services.llm.classification.company_classification import (
    CompanyClassificationService,
    build_company_classification_service,
)

__all__ = ["CompanyClassificationService", "build_company_classification_service"]
