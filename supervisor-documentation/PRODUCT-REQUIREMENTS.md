# Product Requirements Document: EY CX Studio

## 1. Purpose

EY CX Studio is an internal consulting platform for customer experience engagements. It helps consultants assess CX maturity, generate stakeholder interview guides, analyze client documents, run social listening, and consolidate findings into a prioritized issue log.

The product exists to make CX diagnostic work faster, more consistent, easier to share, and more evidence-based across client projects.

## 2. Problem Statement

CX consulting work often depends on disconnected documents, manual interviews, ad hoc spreadsheets, and inconsistent report-writing practices. Consultants need a common workspace that can:

- Keep all analysis artifacts tied to one client project.
- Use structured frameworks for maturity scoring and recommendations.
- Support bilingual delivery in English and French.
- Generate reports and issue logs from multiple evidence sources.
- Protect client information through authenticated, role-aware access.

## 3. Target Users

| User | Need |
|---|---|
| EY consultant | Run assessments, upload evidence, generate reports, and manage engagement artifacts. |
| EY admin | Manage users, reference data, assessment framework content, and analytics. |
| Client respondent | Answer a maturity assessment through a secure passwordless link. |
| Engagement team member | Access shared projects and reuse deliverables created by colleagues. |

## 4. Goals

- Provide one workspace for CX engagement analysis.
- Reduce manual effort in research, assessment scoring, and report drafting.
- Standardize maturity scoring across Manage, Analyze, and Improve axes.
- Preserve traceability between generated recommendations and source evidence.
- Enable project-based collaboration and artifact sharing.
- Support bilingual output for French and English engagements.

## 5. Non-Goals

- Replace consultant judgment or final editorial review.
- Provide public self-service signup.
- Act as a general-purpose CRM or project management system.
- Store high-volume social data indefinitely outside the generated analysis artifacts.
- Guarantee model-generated narrative without human validation.

## 6. Core Features

### 6.1 Project Workspace

- Create and manage client projects.
- Attach module outputs to project pipeline steps.
- Add members so colleagues can access the same work.
- Track progress across assessment, interviews, desk research, social listening, and issue log.

### 6.2 Maturity Assessment

- Run a guided conversational assessment.
- Score CX maturity across Manage, Analyze, and Improve axes.
- Capture evidence against framework capabilities and rubrics.
- Generate a final report with maturity bands, quick wins, recommendations, and benchmark context.
- Send a secure respondent link to a client.

### 6.3 Interview Guide

- Generate stakeholder interview guides from an assessment or from scratch.
- Edit questions and record answers.
- Export guide content.
- Compare interview answers against assessment evidence.

### 6.4 Desk Research

- Upload PDF, DOCX, PPTX, XLSX, and image-based documents.
- Extract text and image context.
- Generate a structured executive report.
- Ask questions over uploaded documents and generated reports.

### 6.5 Social Listening

- Collect public reviews and social posts where supported.
- Classify sentiment, themes, and complaint categories.
- Compute aggregate metrics in Python.
- Generate a social listening report and export workbooks.
- Accept manual analysis inputs when scraping is unavailable.

### 6.6 Issue Log

- Consolidate findings from assessment, interviews, desk research, and social listening.
- Group related issues, flag conflicts between sources, and prioritize recommendations.
- Export the issue register to Excel.

### 6.7 Authentication and Administration

- Invite-only access for consultants.
- Admin-only routes for reference data, users, capability content, and analytics.
- Short-lived access tokens and rotating refresh cookies.

## 7. Success Metrics

| Metric | Target |
|---|---|
| Assessment completion | Consultants can complete a standard assessment and generate a report in one session. |
| Report consistency | Generated reports use framework-backed evidence and computed statistics. |
| Project traceability | Every final deliverable can be linked back to a project and source module. |
| Security | No unauthenticated access to consultant routes; respondent links are scoped to one assessment. |
| Reliability | Long-running scraping and issue-log jobs remain recoverable through polling. |
| Maintainability | Backend and frontend tests remain green before release. |

## 8. Key Risks

- LLM outputs may be incomplete or require consultant review.
- External providers can rate-limit or fail.
- Document extraction quality depends on source file quality.
- Social platform access may change.
- Local model dependencies can increase setup time and deployment size.

## 9. Open Questions

- Which deployment environment will be considered the production target?
- What retention policy should apply to uploaded client documents?
- Which social channels are contractually approved for real client use?
- What exact EY review process is required before client-facing delivery?
