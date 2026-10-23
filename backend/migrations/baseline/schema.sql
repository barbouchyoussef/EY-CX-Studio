-- CX Studio schema baseline -- GENERATED FILE, do not hand-edit.
-- Equivalent to replaying every migration in ../ in order; verified by schema diff,
-- reference-data checksum, and constraint-behaviour test. Rebuild instructions are in
-- backend/migrations_baseline.py.
-- migration_history is deliberately excluded: seed.py owns that table and creates it
-- before this file runs.
-- Generated from 59 migrations, through 056_issue_log_jobs.sql.

--
-- PostgreSQL database dump
--

\restrict 04kbDW05A08nd6E9kDLIhenxt26BP48E1tnpx4anvuSvqRIq8YT7BWC8eCzU9aF

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg13+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: analysis_shares; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.analysis_shares (
    id integer NOT NULL,
    kind character varying(40) NOT NULL,
    ref_id character varying(255) NOT NULL,
    shared_by integer NOT NULL,
    shared_with integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: analysis_shares_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.analysis_shares_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: analysis_shares_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.analysis_shares_id_seq OWNED BY public.analysis_shares.id;


--
-- Name: assessment_answers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_answers (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    capability_id bigint,
    question text NOT NULL,
    answer text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: assessment_answers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_answers_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_answers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_answers_id_seq OWNED BY public.assessment_answers.id;


--
-- Name: assessment_axis_memory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_axis_memory (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    axis character varying(50) NOT NULL,
    summary text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: assessment_axis_memory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_axis_memory_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_axis_memory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_axis_memory_id_seq OWNED BY public.assessment_axis_memory.id;


--
-- Name: assessment_idempotency; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_idempotency (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    response_payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: assessment_idempotency_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_idempotency_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_idempotency_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_idempotency_id_seq OWNED BY public.assessment_idempotency.id;


--
-- Name: assessment_insights; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_insights (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    capability_id bigint,
    insight_text text NOT NULL,
    maturity_level_id bigint,
    confidence numeric(4,3),
    justification text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    evidence_text text,
    CONSTRAINT assessment_insights_confidence_check CHECK (((confidence IS NULL) OR ((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))))
);


--
-- Name: assessment_insights_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_insights_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_insights_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_insights_id_seq OWNED BY public.assessment_insights.id;


--
-- Name: assessment_recipients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_recipients (
    id integer NOT NULL,
    assessment_id integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    client_name character varying(200),
    client_role character varying(200),
    created_by integer,
    status character varying(20) DEFAULT 'sent'::character varying NOT NULL,
    expires_at timestamp with time zone,
    opened_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: assessment_recipients_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_recipients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_recipients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_recipients_id_seq OWNED BY public.assessment_recipients.id;


--
-- Name: assessment_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_scores (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    capability_id bigint NOT NULL,
    maturity_level_id bigint,
    confidence numeric(4,3),
    justification text,
    overridden boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    assessment_status character varying(30) DEFAULT 'not_assessed'::character varying NOT NULL,
    last_assessed_at timestamp with time zone,
    CONSTRAINT assessment_scores_confidence_check CHECK (((confidence IS NULL) OR ((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))))
);


--
-- Name: assessment_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_scores_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_scores_id_seq OWNED BY public.assessment_scores.id;


--
-- Name: assessment_website_audits; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessment_website_audits (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    website_url character varying(500) NOT NULL,
    status character varying(30) DEFAULT 'pending'::character varying NOT NULL,
    payload jsonb,
    error_message text,
    report_path character varying(1000),
    desktop_screenshot_path character varying(1000),
    mobile_screenshot_path character varying(1000),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT assessment_website_audits_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying])::text[])))
);


--
-- Name: assessment_website_audits_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_website_audits_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_website_audits_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_website_audits_id_seq OWNED BY public.assessment_website_audits.id;


--
-- Name: assessments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.assessments (
    id bigint NOT NULL,
    company_id bigint,
    current_axis_id bigint,
    overall_maturity_level_id bigint,
    overall_maturity_band character varying(40),
    status character varying(30) DEFAULT 'active'::character varying NOT NULL,
    state_version integer DEFAULT 1 NOT NULL,
    current_axis_question_count integer DEFAULT 0 NOT NULL,
    current_axis_low_quality_count integer DEFAULT 0 NOT NULL,
    pending_followup_hint character varying(255),
    pending_question character varying(1000),
    conversation_stage character varying(30) DEFAULT 'intro'::character varying NOT NULL,
    clarification_count integer DEFAULT 0 NOT NULL,
    prompt_profile character varying(40) DEFAULT 'consultant_guided'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    executive_summary_text text,
    priority_message_text text,
    leaders_snapshot_payload jsonb,
    leaders_snapshot_status character varying(20),
    leaders_snapshot_generated_at timestamp with time zone,
    leaders_snapshot_error text,
    pending_focus_capability_id integer,
    pending_options jsonb,
    language character varying(10) DEFAULT 'fr'::character varying NOT NULL,
    owner_id integer,
    CONSTRAINT assessments_status_check CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'completed'::character varying, 'paused'::character varying, 'archived'::character varying])::text[])))
);


--
-- Name: assessments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessments_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessments_id_seq OWNED BY public.assessments.id;


--
-- Name: axes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.axes (
    id bigint NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    sort_order integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    description text,
    question_guidelines text
);


--
-- Name: axes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.axes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: axes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.axes_id_seq OWNED BY public.axes.id;


--
-- Name: axis_maturity_content; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.axis_maturity_content (
    id integer NOT NULL,
    axis_id integer NOT NULL,
    maturity_level_id integer NOT NULL,
    axis_description text,
    axis_panel_copy text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: axis_maturity_content_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.axis_maturity_content_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: axis_maturity_content_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.axis_maturity_content_id_seq OWNED BY public.axis_maturity_content.id;


--
-- Name: capabilities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.capabilities (
    id bigint NOT NULL,
    axis_id bigint NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(150) NOT NULL,
    description text,
    evidence_required text,
    question_guidelines text,
    sort_order integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: capabilities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.capabilities_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: capabilities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.capabilities_id_seq OWNED BY public.capabilities.id;


--
-- Name: capability_maturity_rubrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.capability_maturity_rubrics (
    id bigint NOT NULL,
    capability_id bigint NOT NULL,
    maturity_level_id bigint NOT NULL,
    description text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    card_summary text
);


--
-- Name: capability_maturity_rubrics_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.capability_maturity_rubrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: capability_maturity_rubrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.capability_maturity_rubrics_id_seq OWNED BY public.capability_maturity_rubrics.id;


--
-- Name: capability_quick_win_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.capability_quick_win_templates (
    id integer NOT NULL,
    capability_id integer NOT NULL,
    maturity_level_id integer NOT NULL,
    quick_win_guideline text NOT NULL,
    owner_hint text,
    timeline_hint text,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    after_text text
);


--
-- Name: capability_quick_win_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.capability_quick_win_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: capability_quick_win_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.capability_quick_win_templates_id_seq OWNED BY public.capability_quick_win_templates.id;


--
-- Name: capability_recommendations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.capability_recommendations (
    id bigint NOT NULL,
    capability_id bigint NOT NULL,
    maturity_level_id bigint NOT NULL,
    recommendation_guideline text NOT NULL,
    priority_hint character varying(40),
    consultant_note text,
    evidence_to_cite text,
    initiative_suggestions text,
    business_impact text,
    tone_hint character varying(40),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: capability_recommendations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.capability_recommendations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: capability_recommendations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.capability_recommendations_id_seq OWNED BY public.capability_recommendations.id;


--
-- Name: companies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.companies (
    id bigint NOT NULL,
    name character varying(255),
    sector_id bigint NOT NULL,
    size_id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    region_id bigint
);


--
-- Name: companies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.companies_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: companies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.companies_id_seq OWNED BY public.companies.id;


--
-- Name: company_sector_detections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.company_sector_detections (
    id integer NOT NULL,
    company_id integer NOT NULL,
    sector_id integer,
    raw_label text NOT NULL,
    confidence double precision NOT NULL,
    source text DEFAULT 'llm'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: company_sector_detections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.company_sector_detections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: company_sector_detections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.company_sector_detections_id_seq OWNED BY public.company_sector_detections.id;


--
-- Name: company_size_detections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.company_size_detections (
    id integer NOT NULL,
    company_id integer NOT NULL,
    size_id integer,
    raw_label text NOT NULL,
    confidence double precision NOT NULL,
    source text DEFAULT 'llm'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: company_size_detections_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.company_size_detections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: company_size_detections_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.company_size_detections_id_seq OWNED BY public.company_size_detections.id;


--
-- Name: company_sizes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.company_sizes (
    id bigint NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL
);


--
-- Name: company_sizes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.company_sizes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: company_sizes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.company_sizes_id_seq OWNED BY public.company_sizes.id;


--
-- Name: interview_guides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.interview_guides (
    id integer NOT NULL,
    assessment_id integer,
    company_name character varying(255) NOT NULL,
    profile character varying(100) NOT NULL,
    language character varying(10) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    owner_id integer,
    insights jsonb,
    cx_findings jsonb
);


--
-- Name: interview_guides_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.interview_guides_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: interview_guides_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.interview_guides_id_seq OWNED BY public.interview_guides.id;


--
-- Name: invites; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invites (
    token character varying(64) NOT NULL,
    email character varying(320) NOT NULL,
    role character varying(20) DEFAULT 'consultant'::character varying NOT NULL,
    invited_by integer,
    expires_at timestamp with time zone NOT NULL,
    accepted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: issue_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.issue_logs (
    id integer NOT NULL,
    owner_id integer,
    project_id integer,
    name character varying(255) NOT NULL,
    findings jsonb DEFAULT '[]'::jsonb NOT NULL,
    kpis jsonb DEFAULT '{}'::jsonb NOT NULL,
    sources jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    status character varying(20) DEFAULT 'completed'::character varying NOT NULL,
    progress character varying(255),
    error text,
    request jsonb DEFAULT '{}'::jsonb NOT NULL,
    recommendations jsonb DEFAULT '[]'::jsonb NOT NULL,
    run jsonb DEFAULT '{}'::jsonb NOT NULL,
    finished_at timestamp with time zone
);


--
-- Name: issue_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.issue_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: issue_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.issue_logs_id_seq OWNED BY public.issue_logs.id;


--
-- Name: llm_calls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_calls (
    id bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    feature character varying(60) DEFAULT 'unknown'::character varying NOT NULL,
    provider character varying(30) DEFAULT 'mistral'::character varying NOT NULL,
    model character varying(80),
    ok boolean DEFAULT true NOT NULL,
    error character varying(300),
    latency_ms integer,
    prompt_tokens integer,
    completion_tokens integer,
    total_tokens integer,
    cost_usd numeric(12,6),
    owner_id integer,
    ref_kind character varying(30),
    ref_id character varying(64),
    request_id character varying(40),
    kind character varying(20)
);


--
-- Name: llm_calls_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_calls_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_calls_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_calls_id_seq OWNED BY public.llm_calls.id;


--
-- Name: maturity_levels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maturity_levels (
    id bigint NOT NULL,
    level_number smallint NOT NULL,
    label character varying(50) NOT NULL,
    description text,
    CONSTRAINT maturity_levels_level_number_check CHECK ((level_number >= 1))
);


--
-- Name: maturity_levels_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maturity_levels_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maturity_levels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maturity_levels_id_seq OWNED BY public.maturity_levels.id;


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    token_hash character varying(64) NOT NULL,
    user_id integer NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: project_artifacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_artifacts (
    id integer NOT NULL,
    project_id integer NOT NULL,
    step_key character varying(40) NOT NULL,
    kind character varying(40) NOT NULL,
    ref_id character varying(255) NOT NULL,
    title character varying(255),
    created_by integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: project_artifacts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.project_artifacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: project_artifacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.project_artifacts_id_seq OWNED BY public.project_artifacts.id;


--
-- Name: project_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_members (
    project_id integer NOT NULL,
    user_id integer NOT NULL,
    role character varying(20) DEFAULT 'collaborator'::character varying NOT NULL,
    added_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: project_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_steps (
    project_id integer NOT NULL,
    step_key character varying(40) NOT NULL,
    status character varying(20) DEFAULT 'todo'::character varying NOT NULL
);


--
-- Name: projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.projects (
    id integer NOT NULL,
    owner_id integer NOT NULL,
    name character varying(255) NOT NULL,
    company_id integer,
    company_name character varying(255),
    sector character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: projects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.projects_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.projects_id_seq OWNED BY public.projects.id;


--
-- Name: recommendation_outputs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recommendation_outputs (
    id bigint NOT NULL,
    assessment_id bigint NOT NULL,
    capability_id bigint,
    maturity_level_id bigint,
    generated_text text NOT NULL,
    priority character varying(40),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: recommendation_outputs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recommendation_outputs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recommendation_outputs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recommendation_outputs_id_seq OWNED BY public.recommendation_outputs.id;


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.refresh_tokens (
    jti character varying(64) NOT NULL,
    user_id integer NOT NULL,
    family_id character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: regions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.regions (
    id bigint NOT NULL,
    name character varying(120) NOT NULL
);


--
-- Name: regions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.regions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: regions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.regions_id_seq OWNED BY public.regions.id;


--
-- Name: scraping_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.scraping_jobs (
    id integer NOT NULL,
    brand_name character varying(255) NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    progress character varying(255),
    request jsonb NOT NULL,
    result jsonb,
    error text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    owner_id integer
);


--
-- Name: scraping_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.scraping_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: scraping_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.scraping_jobs_id_seq OWNED BY public.scraping_jobs.id;


--
-- Name: sectors; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sectors (
    id bigint NOT NULL,
    code character varying(50) NOT NULL,
    name character varying(100) NOT NULL
);


--
-- Name: sectors_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sectors_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: sectors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sectors_id_seq OWNED BY public.sectors.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(320) NOT NULL,
    full_name character varying(200) NOT NULL,
    password_hash character varying(255),
    role character varying(20) DEFAULT 'consultant'::character varying NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: analysis_shares id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analysis_shares ALTER COLUMN id SET DEFAULT nextval('public.analysis_shares_id_seq'::regclass);


--
-- Name: assessment_answers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_answers ALTER COLUMN id SET DEFAULT nextval('public.assessment_answers_id_seq'::regclass);


--
-- Name: assessment_axis_memory id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_axis_memory ALTER COLUMN id SET DEFAULT nextval('public.assessment_axis_memory_id_seq'::regclass);


--
-- Name: assessment_idempotency id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_idempotency ALTER COLUMN id SET DEFAULT nextval('public.assessment_idempotency_id_seq'::regclass);


--
-- Name: assessment_insights id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_insights ALTER COLUMN id SET DEFAULT nextval('public.assessment_insights_id_seq'::regclass);


--
-- Name: assessment_recipients id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_recipients ALTER COLUMN id SET DEFAULT nextval('public.assessment_recipients_id_seq'::regclass);


--
-- Name: assessment_scores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_scores ALTER COLUMN id SET DEFAULT nextval('public.assessment_scores_id_seq'::regclass);


--
-- Name: assessment_website_audits id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_website_audits ALTER COLUMN id SET DEFAULT nextval('public.assessment_website_audits_id_seq'::regclass);


--
-- Name: assessments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments ALTER COLUMN id SET DEFAULT nextval('public.assessments_id_seq'::regclass);


--
-- Name: axes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axes ALTER COLUMN id SET DEFAULT nextval('public.axes_id_seq'::regclass);


--
-- Name: axis_maturity_content id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axis_maturity_content ALTER COLUMN id SET DEFAULT nextval('public.axis_maturity_content_id_seq'::regclass);


--
-- Name: capabilities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capabilities ALTER COLUMN id SET DEFAULT nextval('public.capabilities_id_seq'::regclass);


--
-- Name: capability_maturity_rubrics id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_maturity_rubrics ALTER COLUMN id SET DEFAULT nextval('public.capability_maturity_rubrics_id_seq'::regclass);


--
-- Name: capability_quick_win_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_quick_win_templates ALTER COLUMN id SET DEFAULT nextval('public.capability_quick_win_templates_id_seq'::regclass);


--
-- Name: capability_recommendations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_recommendations ALTER COLUMN id SET DEFAULT nextval('public.capability_recommendations_id_seq'::regclass);


--
-- Name: companies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies ALTER COLUMN id SET DEFAULT nextval('public.companies_id_seq'::regclass);


--
-- Name: company_sector_detections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_sector_detections ALTER COLUMN id SET DEFAULT nextval('public.company_sector_detections_id_seq'::regclass);


--
-- Name: company_size_detections id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_size_detections ALTER COLUMN id SET DEFAULT nextval('public.company_size_detections_id_seq'::regclass);


--
-- Name: company_sizes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_sizes ALTER COLUMN id SET DEFAULT nextval('public.company_sizes_id_seq'::regclass);


--
-- Name: interview_guides id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview_guides ALTER COLUMN id SET DEFAULT nextval('public.interview_guides_id_seq'::regclass);


--
-- Name: issue_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_logs ALTER COLUMN id SET DEFAULT nextval('public.issue_logs_id_seq'::regclass);


--
-- Name: llm_calls id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_calls ALTER COLUMN id SET DEFAULT nextval('public.llm_calls_id_seq'::regclass);


--
-- Name: maturity_levels id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maturity_levels ALTER COLUMN id SET DEFAULT nextval('public.maturity_levels_id_seq'::regclass);


--
-- Name: project_artifacts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_artifacts ALTER COLUMN id SET DEFAULT nextval('public.project_artifacts_id_seq'::regclass);


--
-- Name: projects id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects ALTER COLUMN id SET DEFAULT nextval('public.projects_id_seq'::regclass);


--
-- Name: recommendation_outputs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendation_outputs ALTER COLUMN id SET DEFAULT nextval('public.recommendation_outputs_id_seq'::regclass);


--
-- Name: regions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions ALTER COLUMN id SET DEFAULT nextval('public.regions_id_seq'::regclass);


--
-- Name: scraping_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scraping_jobs ALTER COLUMN id SET DEFAULT nextval('public.scraping_jobs_id_seq'::regclass);


--
-- Name: sectors id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors ALTER COLUMN id SET DEFAULT nextval('public.sectors_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: analysis_shares analysis_shares_kind_ref_id_shared_with_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analysis_shares
    ADD CONSTRAINT analysis_shares_kind_ref_id_shared_with_key UNIQUE (kind, ref_id, shared_with);


--
-- Name: analysis_shares analysis_shares_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analysis_shares
    ADD CONSTRAINT analysis_shares_pkey PRIMARY KEY (id);


--
-- Name: assessment_answers assessment_answers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_pkey PRIMARY KEY (id);


--
-- Name: assessment_axis_memory assessment_axis_memory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_axis_memory
    ADD CONSTRAINT assessment_axis_memory_pkey PRIMARY KEY (id);


--
-- Name: assessment_idempotency assessment_idempotency_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_idempotency
    ADD CONSTRAINT assessment_idempotency_pkey PRIMARY KEY (id);


--
-- Name: assessment_insights assessment_insights_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_insights
    ADD CONSTRAINT assessment_insights_pkey PRIMARY KEY (id);


--
-- Name: assessment_recipients assessment_recipients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_recipients
    ADD CONSTRAINT assessment_recipients_pkey PRIMARY KEY (id);


--
-- Name: assessment_recipients assessment_recipients_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_recipients
    ADD CONSTRAINT assessment_recipients_token_hash_key UNIQUE (token_hash);


--
-- Name: assessment_scores assessment_scores_assessment_id_capability_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_scores
    ADD CONSTRAINT assessment_scores_assessment_id_capability_id_key UNIQUE (assessment_id, capability_id);


--
-- Name: assessment_scores assessment_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_scores
    ADD CONSTRAINT assessment_scores_pkey PRIMARY KEY (id);


--
-- Name: assessment_website_audits assessment_website_audits_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_website_audits
    ADD CONSTRAINT assessment_website_audits_pkey PRIMARY KEY (id);


--
-- Name: assessments assessments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT assessments_pkey PRIMARY KEY (id);


--
-- Name: axes axes_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axes
    ADD CONSTRAINT axes_code_key UNIQUE (code);


--
-- Name: axes axes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axes
    ADD CONSTRAINT axes_pkey PRIMARY KEY (id);


--
-- Name: axes axes_sort_order_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axes
    ADD CONSTRAINT axes_sort_order_key UNIQUE (sort_order);


--
-- Name: axis_maturity_content axis_maturity_content_axis_level_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axis_maturity_content
    ADD CONSTRAINT axis_maturity_content_axis_level_key UNIQUE (axis_id, maturity_level_id);


--
-- Name: axis_maturity_content axis_maturity_content_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axis_maturity_content
    ADD CONSTRAINT axis_maturity_content_pkey PRIMARY KEY (id);


--
-- Name: capabilities capabilities_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capabilities
    ADD CONSTRAINT capabilities_code_key UNIQUE (code);


--
-- Name: capabilities capabilities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capabilities
    ADD CONSTRAINT capabilities_pkey PRIMARY KEY (id);


--
-- Name: capability_maturity_rubrics capability_maturity_rubrics_capability_id_maturity_level_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_maturity_rubrics
    ADD CONSTRAINT capability_maturity_rubrics_capability_id_maturity_level_id_key UNIQUE (capability_id, maturity_level_id);


--
-- Name: capability_maturity_rubrics capability_maturity_rubrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_maturity_rubrics
    ADD CONSTRAINT capability_maturity_rubrics_pkey PRIMARY KEY (id);


--
-- Name: capability_quick_win_templates capability_quick_win_templates_capability_id_maturity_level_id_; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_quick_win_templates
    ADD CONSTRAINT capability_quick_win_templates_capability_id_maturity_level_id_ UNIQUE (capability_id, maturity_level_id);


--
-- Name: capability_quick_win_templates capability_quick_win_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_quick_win_templates
    ADD CONSTRAINT capability_quick_win_templates_pkey PRIMARY KEY (id);


--
-- Name: capability_recommendations capability_recommendations_capability_id_maturity_level_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_recommendations
    ADD CONSTRAINT capability_recommendations_capability_id_maturity_level_id_key UNIQUE (capability_id, maturity_level_id);


--
-- Name: capability_recommendations capability_recommendations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_recommendations
    ADD CONSTRAINT capability_recommendations_pkey PRIMARY KEY (id);


--
-- Name: companies companies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_pkey PRIMARY KEY (id);


--
-- Name: company_sector_detections company_sector_detections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_sector_detections
    ADD CONSTRAINT company_sector_detections_pkey PRIMARY KEY (id);


--
-- Name: company_size_detections company_size_detections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_size_detections
    ADD CONSTRAINT company_size_detections_pkey PRIMARY KEY (id);


--
-- Name: company_sizes company_sizes_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_sizes
    ADD CONSTRAINT company_sizes_code_key UNIQUE (code);


--
-- Name: company_sizes company_sizes_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_sizes
    ADD CONSTRAINT company_sizes_name_key UNIQUE (name);


--
-- Name: company_sizes company_sizes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_sizes
    ADD CONSTRAINT company_sizes_pkey PRIMARY KEY (id);


--
-- Name: interview_guides interview_guides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview_guides
    ADD CONSTRAINT interview_guides_pkey PRIMARY KEY (id);


--
-- Name: invites invites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invites
    ADD CONSTRAINT invites_pkey PRIMARY KEY (token);


--
-- Name: issue_logs issue_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_logs
    ADD CONSTRAINT issue_logs_pkey PRIMARY KEY (id);


--
-- Name: llm_calls llm_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_calls
    ADD CONSTRAINT llm_calls_pkey PRIMARY KEY (id);


--
-- Name: maturity_levels maturity_levels_level_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maturity_levels
    ADD CONSTRAINT maturity_levels_level_number_key UNIQUE (level_number);


--
-- Name: maturity_levels maturity_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maturity_levels
    ADD CONSTRAINT maturity_levels_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (token_hash);


--
-- Name: project_artifacts project_artifacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_artifacts
    ADD CONSTRAINT project_artifacts_pkey PRIMARY KEY (id);


--
-- Name: project_members project_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_pkey PRIMARY KEY (project_id, user_id);


--
-- Name: project_steps project_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_steps
    ADD CONSTRAINT project_steps_pkey PRIMARY KEY (project_id, step_key);


--
-- Name: projects projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_pkey PRIMARY KEY (id);


--
-- Name: recommendation_outputs recommendation_outputs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendation_outputs
    ADD CONSTRAINT recommendation_outputs_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (jti);


--
-- Name: regions regions_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions
    ADD CONSTRAINT regions_name_key UNIQUE (name);


--
-- Name: regions regions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.regions
    ADD CONSTRAINT regions_pkey PRIMARY KEY (id);


--
-- Name: scraping_jobs scraping_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scraping_jobs
    ADD CONSTRAINT scraping_jobs_pkey PRIMARY KEY (id);


--
-- Name: sectors sectors_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT sectors_code_key UNIQUE (code);


--
-- Name: sectors sectors_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT sectors_name_key UNIQUE (name);


--
-- Name: sectors sectors_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sectors
    ADD CONSTRAINT sectors_pkey PRIMARY KEY (id);


--
-- Name: assessment_axis_memory uq_assessment_axis_memory; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_axis_memory
    ADD CONSTRAINT uq_assessment_axis_memory UNIQUE (assessment_id, axis);


--
-- Name: assessment_idempotency uq_assessment_idempotency; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_idempotency
    ADD CONSTRAINT uq_assessment_idempotency UNIQUE (assessment_id, idempotency_key);


--
-- Name: assessment_website_audits uq_assessment_website_audits_assessment_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_website_audits
    ADD CONSTRAINT uq_assessment_website_audits_assessment_id UNIQUE (assessment_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_analysis_shares_shared_with; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analysis_shares_shared_with ON public.analysis_shares USING btree (shared_with);


--
-- Name: idx_assessment_idempotency_assessment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assessment_idempotency_assessment_id ON public.assessment_idempotency USING btree (assessment_id);


--
-- Name: idx_assessment_insights_assessment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assessment_insights_assessment_id ON public.assessment_insights USING btree (assessment_id);


--
-- Name: idx_assessment_insights_capability_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assessment_insights_capability_id ON public.assessment_insights USING btree (capability_id);


--
-- Name: idx_assessment_recipients_assessment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assessment_recipients_assessment ON public.assessment_recipients USING btree (assessment_id);


--
-- Name: idx_assessments_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assessments_owner_id ON public.assessments USING btree (owner_id);


--
-- Name: idx_axis_maturity_content_axis_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_axis_maturity_content_axis_id ON public.axis_maturity_content USING btree (axis_id);


--
-- Name: idx_axis_maturity_content_maturity_level_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_axis_maturity_content_maturity_level_id ON public.axis_maturity_content USING btree (maturity_level_id);


--
-- Name: idx_capability_quick_win_templates_capability_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_capability_quick_win_templates_capability_id ON public.capability_quick_win_templates USING btree (capability_id);


--
-- Name: idx_capability_quick_win_templates_maturity_level_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_capability_quick_win_templates_maturity_level_id ON public.capability_quick_win_templates USING btree (maturity_level_id);


--
-- Name: idx_interview_guides_assessment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interview_guides_assessment_id ON public.interview_guides USING btree (assessment_id);


--
-- Name: idx_interview_guides_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_interview_guides_owner_id ON public.interview_guides USING btree (owner_id);


--
-- Name: idx_invites_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_invites_email ON public.invites USING btree (email);


--
-- Name: idx_issue_logs_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_issue_logs_owner ON public.issue_logs USING btree (owner_id);


--
-- Name: idx_issue_logs_owner_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_issue_logs_owner_updated ON public.issue_logs USING btree (owner_id, updated_at DESC);


--
-- Name: idx_issue_logs_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_issue_logs_project ON public.issue_logs USING btree (project_id);


--
-- Name: idx_issue_logs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_issue_logs_status ON public.issue_logs USING btree (status);


--
-- Name: idx_llm_calls_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_created_at ON public.llm_calls USING btree (created_at);


--
-- Name: idx_llm_calls_feature; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_feature ON public.llm_calls USING btree (feature);


--
-- Name: idx_llm_calls_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_kind ON public.llm_calls USING btree (kind);


--
-- Name: idx_llm_calls_owner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_calls_owner ON public.llm_calls USING btree (owner_id);


--
-- Name: idx_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: idx_project_artifacts_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_artifacts_project_id ON public.project_artifacts USING btree (project_id);


--
-- Name: idx_project_artifacts_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_artifacts_ref ON public.project_artifacts USING btree (kind, ref_id);


--
-- Name: idx_project_members_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_project_members_user_id ON public.project_members USING btree (user_id);


--
-- Name: idx_projects_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_projects_owner_id ON public.projects USING btree (owner_id);


--
-- Name: idx_recommendation_outputs_assessment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_recommendation_outputs_assessment_id ON public.recommendation_outputs USING btree (assessment_id);


--
-- Name: idx_recommendation_outputs_capability_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_recommendation_outputs_capability_id ON public.recommendation_outputs USING btree (capability_id);


--
-- Name: idx_refresh_tokens_family_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refresh_tokens_family_id ON public.refresh_tokens USING btree (family_id);


--
-- Name: idx_refresh_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: idx_scraping_jobs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scraping_jobs_created_at ON public.scraping_jobs USING btree (created_at DESC);


--
-- Name: idx_scraping_jobs_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scraping_jobs_owner_id ON public.scraping_jobs USING btree (owner_id);


--
-- Name: idx_scraping_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_scraping_jobs_status ON public.scraping_jobs USING btree (status);


--
-- Name: ix_assessment_answers_assessment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_answers_assessment_id ON public.assessment_answers USING btree (assessment_id);


--
-- Name: ix_assessment_answers_capability_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_answers_capability_id ON public.assessment_answers USING btree (capability_id);


--
-- Name: ix_assessment_axis_memory_assessment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_axis_memory_assessment_id ON public.assessment_axis_memory USING btree (assessment_id);


--
-- Name: ix_assessment_axis_memory_axis; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_axis_memory_axis ON public.assessment_axis_memory USING btree (axis);


--
-- Name: ix_assessment_scores_assessment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_scores_assessment_id ON public.assessment_scores USING btree (assessment_id);


--
-- Name: ix_assessment_scores_assessment_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_scores_assessment_status ON public.assessment_scores USING btree (assessment_status);


--
-- Name: ix_assessment_scores_capability_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_scores_capability_id ON public.assessment_scores USING btree (capability_id);


--
-- Name: ix_assessment_scores_maturity_level_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_scores_maturity_level_id ON public.assessment_scores USING btree (maturity_level_id);


--
-- Name: ix_assessment_website_audits_assessment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_website_audits_assessment_id ON public.assessment_website_audits USING btree (assessment_id);


--
-- Name: ix_assessment_website_audits_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_website_audits_status ON public.assessment_website_audits USING btree (status);


--
-- Name: ix_assessments_company_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessments_company_id ON public.assessments USING btree (company_id);


--
-- Name: ix_assessments_current_axis_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessments_current_axis_id ON public.assessments USING btree (current_axis_id);


--
-- Name: ix_assessments_overall_maturity_level_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessments_overall_maturity_level_id ON public.assessments USING btree (overall_maturity_level_id);


--
-- Name: ix_capabilities_axis_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_capabilities_axis_id ON public.capabilities USING btree (axis_id);


--
-- Name: ix_capability_recommendations_capability_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_capability_recommendations_capability_id ON public.capability_recommendations USING btree (capability_id);


--
-- Name: ix_capability_recommendations_maturity_level_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_capability_recommendations_maturity_level_id ON public.capability_recommendations USING btree (maturity_level_id);


--
-- Name: ix_companies_region_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_companies_region_id ON public.companies USING btree (region_id);


--
-- Name: ix_companies_sector_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_companies_sector_id ON public.companies USING btree (sector_id);


--
-- Name: ix_companies_size_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_companies_size_id ON public.companies USING btree (size_id);


--
-- Name: ix_company_sector_detections_company_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_company_sector_detections_company_id ON public.company_sector_detections USING btree (company_id);


--
-- Name: ix_company_size_detections_company_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_company_size_detections_company_id ON public.company_size_detections USING btree (company_id);


--
-- Name: analysis_shares analysis_shares_shared_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analysis_shares
    ADD CONSTRAINT analysis_shares_shared_by_fkey FOREIGN KEY (shared_by) REFERENCES public.users(id);


--
-- Name: analysis_shares analysis_shares_shared_with_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analysis_shares
    ADD CONSTRAINT analysis_shares_shared_with_fkey FOREIGN KEY (shared_with) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: assessment_answers assessment_answers_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE CASCADE;


--
-- Name: assessment_answers assessment_answers_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_answers
    ADD CONSTRAINT assessment_answers_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.capabilities(id);


--
-- Name: assessment_axis_memory assessment_axis_memory_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_axis_memory
    ADD CONSTRAINT assessment_axis_memory_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE CASCADE;


--
-- Name: assessment_idempotency assessment_idempotency_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_idempotency
    ADD CONSTRAINT assessment_idempotency_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE CASCADE;


--
-- Name: assessment_insights assessment_insights_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_insights
    ADD CONSTRAINT assessment_insights_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE CASCADE;


--
-- Name: assessment_insights assessment_insights_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_insights
    ADD CONSTRAINT assessment_insights_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.capabilities(id);


--
-- Name: assessment_insights assessment_insights_maturity_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_insights
    ADD CONSTRAINT assessment_insights_maturity_level_id_fkey FOREIGN KEY (maturity_level_id) REFERENCES public.maturity_levels(id);


--
-- Name: assessment_recipients assessment_recipients_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_recipients
    ADD CONSTRAINT assessment_recipients_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE CASCADE;


--
-- Name: assessment_recipients assessment_recipients_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_recipients
    ADD CONSTRAINT assessment_recipients_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: assessment_scores assessment_scores_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_scores
    ADD CONSTRAINT assessment_scores_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE CASCADE;


--
-- Name: assessment_scores assessment_scores_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_scores
    ADD CONSTRAINT assessment_scores_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.capabilities(id);


--
-- Name: assessment_scores assessment_scores_maturity_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_scores
    ADD CONSTRAINT assessment_scores_maturity_level_id_fkey FOREIGN KEY (maturity_level_id) REFERENCES public.maturity_levels(id);


--
-- Name: assessment_website_audits assessment_website_audits_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_website_audits
    ADD CONSTRAINT assessment_website_audits_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE CASCADE;


--
-- Name: assessments assessments_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT assessments_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id);


--
-- Name: assessments assessments_current_axis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT assessments_current_axis_id_fkey FOREIGN KEY (current_axis_id) REFERENCES public.axes(id);


--
-- Name: assessments assessments_overall_maturity_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT assessments_overall_maturity_level_id_fkey FOREIGN KEY (overall_maturity_level_id) REFERENCES public.maturity_levels(id);


--
-- Name: assessments assessments_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT assessments_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: assessments assessments_pending_focus_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessments
    ADD CONSTRAINT assessments_pending_focus_capability_id_fkey FOREIGN KEY (pending_focus_capability_id) REFERENCES public.capabilities(id);


--
-- Name: axis_maturity_content axis_maturity_content_axis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axis_maturity_content
    ADD CONSTRAINT axis_maturity_content_axis_id_fkey FOREIGN KEY (axis_id) REFERENCES public.axes(id) ON DELETE CASCADE;


--
-- Name: axis_maturity_content axis_maturity_content_maturity_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.axis_maturity_content
    ADD CONSTRAINT axis_maturity_content_maturity_level_id_fkey FOREIGN KEY (maturity_level_id) REFERENCES public.maturity_levels(id) ON DELETE CASCADE;


--
-- Name: capabilities capabilities_axis_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capabilities
    ADD CONSTRAINT capabilities_axis_id_fkey FOREIGN KEY (axis_id) REFERENCES public.axes(id) ON DELETE CASCADE;


--
-- Name: capability_maturity_rubrics capability_maturity_rubrics_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_maturity_rubrics
    ADD CONSTRAINT capability_maturity_rubrics_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.capabilities(id) ON DELETE CASCADE;


--
-- Name: capability_maturity_rubrics capability_maturity_rubrics_maturity_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_maturity_rubrics
    ADD CONSTRAINT capability_maturity_rubrics_maturity_level_id_fkey FOREIGN KEY (maturity_level_id) REFERENCES public.maturity_levels(id) ON DELETE CASCADE;


--
-- Name: capability_quick_win_templates capability_quick_win_templates_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_quick_win_templates
    ADD CONSTRAINT capability_quick_win_templates_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.capabilities(id) ON DELETE CASCADE;


--
-- Name: capability_quick_win_templates capability_quick_win_templates_maturity_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_quick_win_templates
    ADD CONSTRAINT capability_quick_win_templates_maturity_level_id_fkey FOREIGN KEY (maturity_level_id) REFERENCES public.maturity_levels(id) ON DELETE CASCADE;


--
-- Name: capability_recommendations capability_recommendations_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_recommendations
    ADD CONSTRAINT capability_recommendations_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.capabilities(id) ON DELETE CASCADE;


--
-- Name: capability_recommendations capability_recommendations_maturity_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.capability_recommendations
    ADD CONSTRAINT capability_recommendations_maturity_level_id_fkey FOREIGN KEY (maturity_level_id) REFERENCES public.maturity_levels(id) ON DELETE CASCADE;


--
-- Name: companies companies_region_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_region_id_fkey FOREIGN KEY (region_id) REFERENCES public.regions(id);


--
-- Name: companies companies_sector_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_sector_id_fkey FOREIGN KEY (sector_id) REFERENCES public.sectors(id);


--
-- Name: companies companies_size_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.companies
    ADD CONSTRAINT companies_size_id_fkey FOREIGN KEY (size_id) REFERENCES public.company_sizes(id);


--
-- Name: company_sector_detections company_sector_detections_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_sector_detections
    ADD CONSTRAINT company_sector_detections_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: company_sector_detections company_sector_detections_sector_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_sector_detections
    ADD CONSTRAINT company_sector_detections_sector_id_fkey FOREIGN KEY (sector_id) REFERENCES public.sectors(id);


--
-- Name: company_size_detections company_size_detections_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_size_detections
    ADD CONSTRAINT company_size_detections_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id) ON DELETE CASCADE;


--
-- Name: company_size_detections company_size_detections_size_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_size_detections
    ADD CONSTRAINT company_size_detections_size_id_fkey FOREIGN KEY (size_id) REFERENCES public.company_sizes(id);


--
-- Name: interview_guides interview_guides_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview_guides
    ADD CONSTRAINT interview_guides_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE SET NULL;


--
-- Name: interview_guides interview_guides_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interview_guides
    ADD CONSTRAINT interview_guides_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: invites invites_invited_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invites
    ADD CONSTRAINT invites_invited_by_fkey FOREIGN KEY (invited_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: issue_logs issue_logs_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_logs
    ADD CONSTRAINT issue_logs_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: issue_logs issue_logs_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_logs
    ADD CONSTRAINT issue_logs_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE SET NULL;


--
-- Name: llm_calls llm_calls_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_calls
    ADD CONSTRAINT llm_calls_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_artifacts project_artifacts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_artifacts
    ADD CONSTRAINT project_artifacts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: project_artifacts project_artifacts_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_artifacts
    ADD CONSTRAINT project_artifacts_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_members project_members_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: project_members project_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_members
    ADD CONSTRAINT project_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_steps project_steps_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_steps
    ADD CONSTRAINT project_steps_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;


--
-- Name: projects projects_company_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id);


--
-- Name: projects projects_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.projects
    ADD CONSTRAINT projects_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: recommendation_outputs recommendation_outputs_assessment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendation_outputs
    ADD CONSTRAINT recommendation_outputs_assessment_id_fkey FOREIGN KEY (assessment_id) REFERENCES public.assessments(id) ON DELETE CASCADE;


--
-- Name: recommendation_outputs recommendation_outputs_capability_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendation_outputs
    ADD CONSTRAINT recommendation_outputs_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES public.capabilities(id);


--
-- Name: recommendation_outputs recommendation_outputs_maturity_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recommendation_outputs
    ADD CONSTRAINT recommendation_outputs_maturity_level_id_fkey FOREIGN KEY (maturity_level_id) REFERENCES public.maturity_levels(id);


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: scraping_jobs scraping_jobs_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.scraping_jobs
    ADD CONSTRAINT scraping_jobs_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict 04kbDW05A08nd6E9kDLIhenxt26BP48E1tnpx4anvuSvqRIq8YT7BWC8eCzU9aF


-- ── reference data (column-inserts so any driver can run this, not just psql) ──
--
-- PostgreSQL database dump
--

\restrict WaPqm9yKGNfy8RRaKcwc5gIJSakhcJF2iUm4gfrVhJNPcVVgLPrEOkETaCQI3gb

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg13+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: axes; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.axes (id, code, name, sort_order, created_at, updated_at, description, question_guidelines) VALUES (1, 'manage', 'Manage', 1, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.455009+00', 'Manage covers the organization mechanisms that make customer experience accountable: leadership attention, ownership, governance routines, decision rights, culture, and the way customer impact is reinforced in everyday management.', 'Use this axis to understand how CX is owned and governed. Ask about accountability, recurring management routines, decision influence, leadership follow-up, team reinforcement, and whether customer issues have visible owners rather than informal handling.');
INSERT INTO public.axes (id, code, name, sort_order, created_at, updated_at, description, question_guidelines) VALUES (2, 'analyze', 'Analyze', 2, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.455009+00', 'Analyze covers how the organization listens to customers and turns feedback into usable understanding: feedback capture, journey visibility, cross-channel consistency, pattern recognition, root-cause analysis, and prioritization of customer issues.', 'Use this axis to understand how customer signals become insight. Ask about feedback sources, logging practices, journey views, handoffs across channels, theme review, root-cause work, and how teams decide which issues matter most.');
INSERT INTO public.axes (id, code, name, sort_order, created_at, updated_at, description, question_guidelines) VALUES (3, 'improve', 'Improve', 3, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.455009+00', 'Improve covers how the organization acts on customer pain points and measures improvement over time: execution discipline, action ownership, metric review, follow-through, validation of fixes, and continuous improvement loops.', 'Use this axis to understand whether customer issues lead to measurable action. Ask about pain-point backlogs, owners, due dates, closure checks, CX metrics, review cadence, action triggers, validation, and learning loops.');


--
-- Data for Name: capabilities; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (1, 1, 'manage_cx_culture', 'CX culture', NULL, 'team ritual agenda, manager coaching note, CX playbook, service standard, recognition record, training attendance, QA scorecard, customer story shared in meeting', 'Goal: Understand whether customer-focused behaviour is reinforced in daily work. Ask for one recent example of coaching, recognition, or a team routine. If the user says "pass" or "don''t know", accept this as evidence that CX culture is informal and move on. DO NOT ask multiple questions.', 10, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.561077+00');
INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (3, 1, 'manage_decision_making', 'Decision-making', NULL, 'customer feedback example, decision note, leadership meeting minutes, prioritization record, roadmap change, policy update, budget decision, customer complaint summary', 'Goal: Identify if customer evidence impacts decisions. Start by asking for one recent example. If the user says "pass" or "don''t know", accept this as evidence of a reactive/internal culture and move on. DO NOT ask multiple questions.', 30, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.561077+00');
INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (4, 2, 'analyze_feedback_collection', 'Feedback collection', NULL, 'email inbox, Excel tracker, survey export, complaint log, call notes, shared mailbox owner, feedback tag, weekly review note, CRM case list', 'Goal: Map feedback channels. If the user gives a simple answer like "email", acknowledge it and ask who manages those emails. Do not repeat the channel question. DO NOT ask multiple questions.', 10, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.561077+00');
INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (2, 1, 'manage_ownership_governance', 'Ownership and governance', NULL, NULL, 'Goal: Identify the main owner for cross-functional issues. Ask one clear question about who takes the lead. If a leader is named (e.g., CX Lead), ACCEPT it as sufficient and move on. Do not force the search for sub-owners in other departments.', 20, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.569661+00');
INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (7, 2, 'analyze_journey_visibility', 'Journey visibility', NULL, 'journey map, service blueprint, touchpoint inventory, journey owner, journey KPI dashboard, regular review deck, cross-functional workshop notes, pain-point register', 'Goal: check visibility of the end-to-end customer journey. Ask for one key journey and how teams currently see or review it. If vague, probe only on the artifact or owner. DO NOT ask multiple questions.', 40, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.555756+00');
INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (9, 3, 'improve_acting_on_pain_points', 'Acting on pain points', NULL, 'pain-point backlog, Jira ticket, Trello card, named owner, due date, action status, closure evidence, customer complaint log, post-fix validation note', 'Goal: understand how the business acts on customer pain points. Ask for one recent pain point and what happened next. If vague, probe only on ownership or closure evidence. DO NOT ask multiple questions.', 20, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.555756+00');
INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (5, 2, 'analyze_use_of_insights', 'Use of insights', NULL, NULL, 'Assess how feedback is turned into insight and used to decide what matters most. Focus on whether teams only review or observe feedback informally, whether they group issues into themes or repeated patterns, whether they identify root causes, and whether they use explicit logic such as customer impact, frequency, severity, or business importance to decide which issues to act on first. Prefer this capability when the answer explains how the organization interprets feedback, identifies patterns, prioritizes issues, or chooses what to address first. Do not treat feedback being logged in one place, collected through several channels, routed to a shared tool, or reviewed on a regular cadence as sufficient evidence for this capability unless the answer also explains how issues are analyzed, compared, or prioritized.', 20, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.569661+00');
INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (6, 2, 'analyze_channel_consistency', 'Channel consistency', NULL, NULL, 'Goal: Understand how feedback leads to action. Ask for one recent example. If the user is vague, ask who reviewed the info. If they don''t know, mark as Level 1 and move on.', 30, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.569661+00');
INSERT INTO public.capabilities (id, axis_id, code, name, description, evidence_required, question_guidelines, sort_order, created_at, updated_at) VALUES (8, 3, 'improve_measurement_continuous_improvement', 'Measurement and continuous improvement', NULL, NULL, 'Goal: Map CX metrics. Ask what measures are followed. If the user lists even one (e.g., NPS, complaints), accept it. If they have none, mark as Level 1 and move on.', 10, '2026-08-28 15:55:19.455009+00', '2026-08-28 15:55:19.569661+00');


--
-- Data for Name: maturity_levels; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.maturity_levels (id, level_number, label, description) VALUES (1, 1, 'Basic / Reactive', 'Initial, ad-hoc practices with limited structure or consistency.');
INSERT INTO public.maturity_levels (id, level_number, label, description) VALUES (2, 2, 'Established', 'Defined practices with partial adoption and growing consistency.');
INSERT INTO public.maturity_levels (id, level_number, label, description) VALUES (3, 3, 'Advanced / Proactive', 'Systematic, embedded practices with clear ownership and continuous improvement.');


--
-- Data for Name: capability_maturity_rubrics; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (1, 8, 1, 'Measures are limited or disconnected from action, with little evidence of a regular improvement loop.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (2, 6, 1, 'Channels operate separately, with inconsistent standards, weak handoffs, and limited shared customer context.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (3, 5, 1, 'Feedback is observed informally, with little evidence of theme review, root-cause analysis, or explicit prioritization logic.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (4, 9, 1, 'Pain points are handled reactively with little backlog, ownership, closure discipline, or validation.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (5, 7, 1, 'Journey visibility is weak or absent; teams mainly see isolated touchpoints rather than the full customer path.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (6, 2, 1, 'Accountability is informal or fragmented, with no consistent owner, governance routine, or follow-up discipline for customer issues.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (7, 4, 1, 'Feedback is collected inconsistently or through a few isolated channels, with weak logging, ownership, and review rhythm.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (8, 3, 1, 'Customer evidence rarely changes decisions; priorities are mostly internal, reactive, or driven by individual judgement.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (9, 1, 1, 'Customer-focused behaviours are ad hoc, weakly reinforced, and largely dependent on individual managers or frontline goodwill.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (10, 8, 2, 'Measures are tracked and reviewed, but ownership, targets, and business linkage are incomplete.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (11, 6, 2, 'Some shared standards or handoff practices exist, but consistency is uneven across the experience.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (12, 5, 2, 'Some theme review or prioritization exists, but the process is inconsistent and not yet decision-ready.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (13, 9, 2, 'Some backlog or owner process exists, but prioritization and closure discipline are inconsistent.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (14, 7, 2, 'Some journeys are mapped or discussed, but ownership, updates, and pain-point tracking remain inconsistent.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (15, 2, 2, 'A named owner or central team exists, and some governance routines are in place, but coordination and follow-through are not yet fully reliable.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (16, 4, 2, 'Feedback is captured through some defined channels or tools, but coverage, ownership, tagging, and review cadence are inconsistent.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (17, 3, 2, 'Customer evidence influences some decisions, but the practice is partial, siloed, or inconsistent across teams.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (18, 1, 2, 'Some coaching, training, service standards, or recognition exist, but adoption is partial and not yet fully embedded in routines.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (19, 8, 3, 'Measures are tied to targets, owners, business outcomes, experiments, and systematic improvement loops.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (20, 6, 3, 'Channels are managed with shared context, consistent standards, and active monitoring for consistency issues.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (21, 5, 3, 'Feedback is translated into actionable insight through pattern analysis, root-cause work, and clear prioritization criteria.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (22, 9, 3, 'Pain points are managed through a repeatable improvement loop with prioritization, owners, closure checks, and validation.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (23, 7, 3, 'Key journeys are owned, documented, and reviewed cross-functionally to guide prioritization and improvements.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (24, 2, 3, 'Customer issues are managed through recurring governance, clear owners, escalation paths, action logs, and visible cross-functional accountability.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (25, 4, 3, 'Feedback is captured across key touchpoints through structured channels with clear ownership, tagging, and regular review.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (26, 3, 3, 'Customer evidence systematically shapes decisions through governance, named owners, documented trade-offs, and follow-up.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);
INSERT INTO public.capability_maturity_rubrics (id, capability_id, maturity_level_id, description, created_at, updated_at, card_summary) VALUES (27, 1, 3, 'Customer-focused behaviours are actively reinforced through leadership routines, coaching, recognition, practical standards, and quality feedback.', '2026-08-28 15:55:19.768499+00', '2026-08-28 15:55:19.768499+00', NULL);


--
-- Data for Name: company_sizes; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.company_sizes (id, code, name) VALUES (1, 'unknown', 'Unknown');
INSERT INTO public.company_sizes (id, code, name) VALUES (3, 'micro', 'Micro (1-10)');
INSERT INTO public.company_sizes (id, code, name) VALUES (4, 'small', 'Small (11-50)');
INSERT INTO public.company_sizes (id, code, name) VALUES (5, 'medium', 'Medium (51-250)');
INSERT INTO public.company_sizes (id, code, name) VALUES (6, 'large', 'Large (251-1000)');
INSERT INTO public.company_sizes (id, code, name) VALUES (7, 'enterprise', 'Enterprise (1000+)');


--
-- Data for Name: regions; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.regions (id, name) VALUES (1, 'Africa');
INSERT INTO public.regions (id, name) VALUES (2, 'Antarctica');
INSERT INTO public.regions (id, name) VALUES (3, 'Asia');
INSERT INTO public.regions (id, name) VALUES (4, 'Europe');
INSERT INTO public.regions (id, name) VALUES (5, 'North America');
INSERT INTO public.regions (id, name) VALUES (6, 'Oceania');
INSERT INTO public.regions (id, name) VALUES (7, 'South America');


--
-- Data for Name: sectors; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.sectors (id, code, name) VALUES (1, 'unknown', 'Unknown');
INSERT INTO public.sectors (id, code, name) VALUES (3, 'retail', 'Retail');
INSERT INTO public.sectors (id, code, name) VALUES (4, 'ecommerce', 'E-commerce');
INSERT INTO public.sectors (id, code, name) VALUES (5, 'banking', 'Banking');
INSERT INTO public.sectors (id, code, name) VALUES (6, 'insurance', 'Insurance');
INSERT INTO public.sectors (id, code, name) VALUES (7, 'telecom', 'Telecom');
INSERT INTO public.sectors (id, code, name) VALUES (8, 'healthcare', 'Healthcare');
INSERT INTO public.sectors (id, code, name) VALUES (9, 'travel', 'Travel & Hospitality');
INSERT INTO public.sectors (id, code, name) VALUES (10, 'saas', 'SaaS / Software');
INSERT INTO public.sectors (id, code, name) VALUES (11, 'manufacturing', 'Manufacturing');
INSERT INTO public.sectors (id, code, name) VALUES (12, 'logistics', 'Logistics');
INSERT INTO public.sectors (id, code, name) VALUES (13, 'public', 'Public Sector');


--
-- Name: axes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.axes_id_seq', 3, true);


--
-- Name: capabilities_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.capabilities_id_seq', 9, true);


--
-- Name: capability_maturity_rubrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.capability_maturity_rubrics_id_seq', 27, true);


--
-- Name: company_sizes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.company_sizes_id_seq', 7, true);


--
-- Name: maturity_levels_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maturity_levels_id_seq', 3, true);


--
-- Name: regions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.regions_id_seq', 7, true);


--
-- Name: sectors_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.sectors_id_seq', 13, true);


--
-- PostgreSQL database dump complete
--

\unrestrict WaPqm9yKGNfy8RRaKcwc5gIJSakhcJF2iUm4gfrVhJNPcVVgLPrEOkETaCQI3gb

