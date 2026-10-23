"""The package's re-exports must be the real implementations, not copies of them.

`app.services.assessment` exposes a flat surface over several submodules, resolved lazily in
__getattr__. The risk that guards against is a second definition drifting behind the name -- so
these assert identity, not just presence.

Builders come from `factory`, which is what assembles a service out of its repositories; the
classes come from the modules that define them. That split is the contract.
"""

import importlib


def test_assessment_feature_exports_match_canonical_modules():
    pkg = importlib.import_module("app.services.assessment")
    scoring = importlib.import_module("app.services.assessment.scoring.scoring_service")
    reporting = importlib.import_module("app.services.assessment.reporting.reporting_service")
    state = importlib.import_module("app.services.assessment.state.state_service")
    conversation = importlib.import_module("app.services.assessment.conversation.answer_flow_service")
    lifecycle = importlib.import_module("app.services.assessment.lifecycle_service")
    factory = importlib.import_module("app.services.assessment.factory")

    assert pkg.AssessmentScoringService is scoring.AssessmentScoringService
    assert pkg.build_assessment_scoring_service is scoring.build_assessment_scoring_service
    assert pkg.AssessmentReportingService is reporting.AssessmentReportingService
    assert pkg.build_assessment_reporting_service is reporting.build_assessment_reporting_service
    assert pkg.AssessmentStateService is state.AssessmentStateService
    assert pkg.AnswerFlowService is conversation.AnswerFlowService
    assert pkg.build_answer_flow_service is conversation.build_answer_flow_service
    assert pkg.AssessmentService is lifecycle.AssessmentService
    assert pkg.build_assessment_service is factory.build_assessment_service


def test_assessment_package_lazy_exports_core_symbols():
    pkg = importlib.import_module("app.services.assessment")
    assert hasattr(pkg, "AssessmentService")
    assert hasattr(pkg, "AssessmentConversationService")
    assert hasattr(pkg, "AssessmentReportingService")
    assert hasattr(pkg, "AssessmentScoringService")
    assert hasattr(pkg, "AssessmentStateService")
    assert hasattr(pkg, "build_assessment_service")
