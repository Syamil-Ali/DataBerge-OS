from __future__ import annotations

from typing import Any


BLOCK_SCHEMAS: dict[str, dict[str, Any]] = {
    "central_theme": {
        "description": "One powerful sentence summarizing the most important insight",
        "type": "string",
    },
    "executive_summary": {
        "description": "SBAR-structured executive summary",
        "type": "object",
        "properties": {
            "situation": {"type": "array", "items": {"type": "string"}},
            "background": {"type": "array", "items": {"type": "string"}},
            "assessment": {"type": "array", "items": {"type": "string"}},
            "recommendation": {"type": "array", "items": {"type": "string"}},
        },
    },
    "key_metrics": {
        "description": "Key performance metrics",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "string"},
                "health": {"type": "string", "enum": ["good", "concerning", "critical", "info"]},
                "trend": {"type": "string", "enum": ["improving", "declining", "stable"]},
                "score": {"type": "number"},
                "description": {"type": "string"},
            },
        },
    },
    "findings": {
        "description": "Key investigation findings with severity and evidence",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "severity": {"type": "string", "enum": ["critical", "concerning", "good", "info"]},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "evidence": {"type": "string"},
                "sql": {"type": "string"},
                "columns_used": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "data_story": {
        "description": "2-3 paragraphs explaining WHY these patterns exist, connecting findings to root causes",
        "type": "string",
    },
    "action_plan": {
        "description": "Phased action recommendations",
        "type": "object",
        "properties": {
            "immediate": {"type": "array", "items": {"type": "string"}},
            "short_term": {"type": "array", "items": {"type": "string"}},
            "long_term": {"type": "array", "items": {"type": "string"}},
        },
    },
    "prognosis": {
        "description": "Projected outcomes with and without recommendations",
        "type": "object",
        "properties": {
            "current_state": {"type": "string"},
            "with_recommendations": {"type": "string"},
        },
    },
    "charts": {
        "description": "Chart specifications from investigation findings",
        "type": "array",
    },
    "summary": {
        "description": "Brief summary of the analysis and key takeaways",
        "type": "string",
    },
    "problem_statement": {
        "description": "Clear statement of the problem or question being investigated",
        "type": "string",
    },
    "methodology": {
        "description": "Description of the analytical methods, data sources, and approach used",
        "type": "string",
    },
    "conclusions": {
        "description": "Evidence-based conclusions drawn from the findings",
        "type": "string",
    },
    "references": {
        "description": "Sources and references cited in the report",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "type": {"type": "string"},
                "description": {"type": "string"},
                "source": {"type": "string"},
            },
        },
    },
    "overview": {
        "description": "High-level overview of the dataset and analysis scope",
        "type": "string",
    },
    "data_quality_assessment": {
        "description": "Detailed assessment of data quality, completeness, and reliability",
        "type": "object",
        "properties": {
            "overall_score": {"type": "number"},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "weaknesses": {"type": "array", "items": {"type": "string"}},
            "recommendations": {"type": "array", "items": {"type": "string"}},
        },
    },
    "schema_analysis": {
        "description": "Analysis of the data schema, column types, and structural patterns",
        "type": "object",
        "properties": {
            "total_columns": {"type": "number"},
            "column_breakdown": {"type": "object"},
            "key_relationships": {"type": "array", "items": {"type": "string"}},
        },
    },
    "recommendations": {
        "description": "Actionable recommendations based on the analysis",
        "type": "array",
        "items": {"type": "string"},
    },
    "top_findings": {
        "description": "The most important findings from the analysis",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "severity": {"type": "string"},
                "evidence": {"type": "string"},
            },
        },
    },
}

REPORT_TEMPLATES: dict[str, dict[str, Any]] = {
    "executive": {
        "name": "Executive Report",
        "description": "SBAR-structured report for leadership stakeholders",
        "blocks": [
            {"key": "central_theme", "label": "Central Theme", "required": True},
            {"key": "executive_summary", "label": "Executive Summary (SBAR)", "required": True},
            {"key": "key_metrics", "label": "Key Metrics", "required": True},
            {"key": "findings", "label": "Findings", "required": True},
            {"key": "data_story", "label": "Data Story", "required": False},
            {"key": "action_plan", "label": "Action Plan", "required": False},
            {"key": "prognosis", "label": "Prognosis", "required": False},
            {"key": "charts", "label": "Charts", "required": False},
        ],
    },
    "research": {
        "name": "Research Report",
        "description": "Academic-style research structure with methodology and conclusions",
        "blocks": [
            {"key": "summary", "label": "Summary", "required": True},
            {"key": "problem_statement", "label": "Problem Statement", "required": True},
            {"key": "methodology", "label": "Methodology", "required": True},
            {"key": "findings", "label": "Findings", "required": True},
            {"key": "data_story", "label": "Data Story", "required": False},
            {"key": "conclusions", "label": "Conclusions", "required": True},
            {"key": "references", "label": "References", "required": False},
        ],
    },
    "technical": {
        "name": "Technical Report",
        "description": "Data-focused technical analysis with schema and quality assessment",
        "blocks": [
            {"key": "overview", "label": "Overview", "required": True},
            {"key": "data_quality_assessment", "label": "Data Quality Assessment", "required": True},
            {"key": "schema_analysis", "label": "Schema Analysis", "required": True},
            {"key": "key_metrics", "label": "Key Metrics", "required": True},
            {"key": "findings", "label": "Findings", "required": True},
            {"key": "recommendations", "label": "Recommendations", "required": True},
        ],
    },
    "quick_brief": {
        "name": "Quick Brief",
        "description": "Concise summary with key metrics and top findings",
        "blocks": [
            {"key": "central_theme", "label": "Central Theme", "required": True},
            {"key": "key_metrics", "label": "Key Metrics", "required": True},
            {"key": "top_findings", "label": "Top Findings", "required": True},
            {"key": "charts", "label": "Charts", "required": False},
        ],
    },
}


def get_template(name: str) -> dict[str, Any] | None:
    return REPORT_TEMPLATES.get(name)


def list_templates() -> list[dict[str, Any]]:
    return [
        {"key": key, "name": t["name"], "description": t["description"]}
        for key, t in REPORT_TEMPLATES.items()
    ]


def get_block_keys(template_name: str) -> list[str]:
    tmpl = get_template(template_name)
    if not tmpl:
        return []
    return [b["key"] for b in tmpl["blocks"]]


def build_block_schemas(template_name: str, active_blocks: list[str] | None = None) -> dict[str, Any]:
    tmpl = get_template(template_name)
    if not tmpl:
        return {}

    schemas: dict[str, Any] = {}
    for block in tmpl["blocks"]:
        key = block["key"]
        if active_blocks is not None and key not in active_blocks:
            continue
        if key in BLOCK_SCHEMAS:
            schemas[key] = BLOCK_SCHEMAS[key]
    return schemas
