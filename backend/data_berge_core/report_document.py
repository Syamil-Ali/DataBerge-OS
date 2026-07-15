from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


SectionKind = Literal[
    "summary",
    "narrative",
    "metrics",
    "findings",
    "chart",
    "actions",
    "comparison",
    "table",
    "key_value",
    "bullets",
    "references",
    "callout",
]
SectionVariant = Literal["hero", "feature", "standard", "compact"]
SectionWidth = Literal["full", "half", "third"]
SectionEmphasis = Literal["primary", "supporting", "context"]
ReportTheme = Literal["executive", "research", "technical", "brief", "custom"]


class SectionPresentation(BaseModel):
    kind: SectionKind
    variant: SectionVariant = "standard"
    width: SectionWidth = "full"
    emphasis: SectionEmphasis = "supporting"
    page_break_before: bool = False


class ReportSection(BaseModel):
    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1, max_length=120)
    content: Any
    presentation: SectionPresentation


class ReportDocument(BaseModel):
    version: Literal[2] = 2
    theme: ReportTheme = "custom"
    density: Literal["comfortable", "compact"] = "comfortable"
    sections: list[ReportSection]


KNOWN_SECTION_ORDER = [
    "central_theme",
    "summary",
    "overview",
    "executive_summary",
    "problem_statement",
    "key_metrics",
    "data_quality_assessment",
    "schema_analysis",
    "findings",
    "top_findings",
    "key_findings",
    "business_implications",
    "data_story",
    "methodology",
    "charts",
    "recommendations",
    "action_plan",
    "next_steps",
    "prognosis",
    "conclusions",
    "systems_detail",
    "references",
]

KIND_BY_KEY: dict[str, SectionKind] = {
    "central_theme": "callout",
    "executive_summary": "summary",
    "key_metrics": "metrics",
    "findings": "findings",
    "top_findings": "findings",
    "key_findings": "findings",
    "charts": "chart",
    "action_plan": "actions",
    "recommendations": "actions",
    "next_steps": "actions",
    "prognosis": "comparison",
    "references": "references",
    "data_quality_assessment": "key_value",
    "schema_analysis": "key_value",
    "systems_detail": "key_value",
    "business_implications": "bullets",
    "data_story": "narrative",
    "summary": "narrative",
    "overview": "narrative",
    "problem_statement": "narrative",
    "methodology": "narrative",
    "conclusions": "narrative",
}

ALLOWED_KINDS = {
    "summary",
    "narrative",
    "metrics",
    "findings",
    "chart",
    "actions",
    "comparison",
    "table",
    "key_value",
    "bullets",
    "references",
    "callout",
}
ALLOWED_VARIANTS = {"hero", "feature", "standard", "compact"}
ALLOWED_WIDTHS = {"full", "half", "third"}
ALLOWED_EMPHASIS = {"primary", "supporting", "context"}


def is_usable_chart(content: Any) -> bool:
    if not isinstance(content, dict):
        return False
    rows = content.get("data")
    if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
        return False
    if str(content.get("type") or "") == "table":
        return any(bool(row) for row in rows)
    x_key = str(content.get("x") or "").strip()
    y_value = content.get("y")
    y_keys = [str(item).strip() for item in y_value] if isinstance(y_value, list) else []
    y_keys = [item for item in y_keys if item]
    if not x_key or not y_keys:
        return False
    return any(x_key in row and any(key in row for key in y_keys) for row in rows)


def has_usable_section_content(kind: Any, content: Any) -> bool:
    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind == "chart":
        charts = content if isinstance(content, list) else []
        return bool(charts) and all(is_usable_chart(chart) for chart in charts)
    if normalized_kind in {"metrics", "findings", "table"}:
        return isinstance(content, list) and bool(content) and all(isinstance(item, dict) and bool(item) for item in content)
    if normalized_kind in {"bullets", "references"}:
        return isinstance(content, list) and bool(content) and all(_has_content(item) for item in content)
    if normalized_kind == "actions":
        if isinstance(content, list):
            return bool(content) and all(_has_content(item) for item in content)
        if isinstance(content, dict):
            return any(_has_content(value) for value in content.values())
        return False
    if normalized_kind in {"comparison", "key_value", "summary"}:
        if isinstance(content, dict):
            return bool(content) and any(_has_content(value) for value in content.values())
        if normalized_kind == "summary":
            return isinstance(content, str) and len(content.strip()) > 10
        return False
    if normalized_kind in {"narrative", "callout"}:
        return isinstance(content, str) and len(content.strip()) > 10
    return _has_content(content)


def compose_report_document(
    report: dict[str, Any],
    template: str | None = None,
    block_definitions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize generated report content into a validated presentation contract."""
    result = dict(report)
    definitions = block_definitions or _as_dict_list(result.get("custom_blocks"))
    definition_by_key = {
        _safe_key(item.get("key")): item
        for item in definitions
        if _safe_key(item.get("key"))
    }

    raw_sections = _source_sections(result, definitions)
    sections: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_sections):
        if not isinstance(raw, dict):
            continue
        key = _safe_key(raw.get("key") or f"section_{index + 1}")
        if not key:
            continue
        definition = definition_by_key.get(key, {})
        label = str(
            raw.get("label")
            or definition.get("label")
            or result.get("block_labels", {}).get(key)
            or key.replace("_", " ").title()
        ).strip()[:120]
        content = unwrap_schema_content(raw.get("content"))
        presentation_source = raw.get("presentation")
        if not isinstance(presentation_source, dict):
            presentation_source = definition.get("presentation")
        kind_hint = raw.get("kind") or definition.get("kind")
        presentation = _presentation_for(
            key,
            content,
            index,
            kind_hint=kind_hint,
            raw=presentation_source if isinstance(presentation_source, dict) else {},
        )
        validated = ReportSection(
            key=key,
            label=label or f"Section {index + 1}",
            content=content,
            presentation=SectionPresentation(**presentation),
        )
        sections.append(validated.model_dump(mode="json"))
        result[key] = content

    theme = _theme_for(template or str(result.get("template") or "custom"))
    density = "compact" if theme == "brief" else "comfortable"
    document = ReportDocument(
        theme=theme,
        density=density,
        sections=[ReportSection.model_validate(section) for section in sections],
    ).model_dump(mode="json")

    result["sections"] = sections
    result["document"] = document
    result["design"] = {
        "version": document["version"],
        "theme": document["theme"],
        "density": document["density"],
    }

    if definitions:
        result["custom_blocks"] = [
            {
                **definition,
                "key": key,
                "kind": next(
                    (section["presentation"]["kind"] for section in sections if section["key"] == key),
                    definition.get("kind"),
                ),
                "presentation": next(
                    (section["presentation"] for section in sections if section["key"] == key),
                    definition.get("presentation"),
                ),
            }
            for definition in definitions
            if (key := _safe_key(definition.get("key")))
        ]
    return result


def unwrap_schema_content(content: Any) -> Any:
    """Recover content when an LLM copied JSON-schema descriptors into its answer."""
    if not isinstance(content, dict):
        return content
    content_type = content.get("type")
    if content_type not in {"array", "string", "object", "number", "boolean"}:
        return content
    if "items" in content and isinstance(content.get("items"), list):
        return content["items"]
    if "value" in content:
        return content["value"]
    if "content" in content:
        return content["content"]
    return content


def _source_sections(
    report: dict[str, Any],
    definitions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    document = report.get("document")
    if isinstance(document, dict) and isinstance(document.get("sections"), list):
        return [item for item in document["sections"] if isinstance(item, dict)]
    if isinstance(report.get("sections"), list) and report["sections"]:
        return [item for item in report["sections"] if isinstance(item, dict)]

    order = report.get("block_order") if isinstance(report.get("block_order"), list) else []
    if not order and definitions:
        order = [item.get("key") for item in definitions]
    if not order:
        order = KNOWN_SECTION_ORDER

    labels = report.get("block_labels") if isinstance(report.get("block_labels"), dict) else {}
    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_key in order:
        key = _safe_key(raw_key)
        if not key or key in seen or key not in report or not _has_content(report.get(key)):
            continue
        seen.add(key)
        sections.append({
            "key": key,
            "label": labels.get(key) or key.replace("_", " ").title(),
            "content": report.get(key),
        })
    return sections


def _presentation_for(
    key: str,
    content: Any,
    index: int,
    kind_hint: Any = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = raw or {}
    hinted_kind = str(kind_hint or raw.get("kind") or "").strip().lower()
    kind: SectionKind = hinted_kind if hinted_kind in ALLOWED_KINDS else _infer_kind(key, content)  # type: ignore[assignment]

    variant: SectionVariant = "standard"
    width: SectionWidth = "full"
    emphasis: SectionEmphasis = "supporting"
    page_break_before = bool(raw.get("page_break_before", False))

    if kind == "callout":
        variant, emphasis = "hero", "primary"
    elif kind in {"summary", "metrics", "findings", "actions"}:
        variant, emphasis = ("feature" if kind == "summary" else "standard"), "primary"
    elif kind in {"narrative", "bullets", "key_value"}:
        width = "full" if index == 0 or _content_weight(content) > 420 else "half"
        variant = "feature" if index == 0 else "standard"
    elif kind in {"references", "table"}:
        variant = "compact"

    raw_variant = str(raw.get("variant") or "").lower()
    raw_width = str(raw.get("width") or "").lower()
    raw_emphasis = str(raw.get("emphasis") or "").lower()
    if raw_variant in ALLOWED_VARIANTS:
        variant = raw_variant  # type: ignore[assignment]
    if raw_width in ALLOWED_WIDTHS:
        width = raw_width  # type: ignore[assignment]
    if raw_emphasis in ALLOWED_EMPHASIS:
        emphasis = raw_emphasis  # type: ignore[assignment]

    if kind in {"summary", "metrics", "findings", "chart", "actions", "comparison", "table", "references", "callout"}:
        width = "full"

    return {
        "kind": kind,
        "variant": variant,
        "width": width,
        "emphasis": emphasis,
        "page_break_before": page_break_before,
    }


def _infer_kind(key: str, content: Any) -> SectionKind:
    if key in KIND_BY_KEY:
        return KIND_BY_KEY[key]
    if isinstance(content, str):
        return "narrative"
    if isinstance(content, list):
        if not content or all(isinstance(item, str) for item in content):
            return "bullets"
        rows = [item for item in content if isinstance(item, dict)]
        if rows and all("name" in item and "value" in item for item in rows):
            return "metrics"
        if rows and all(any(field in item for field in ("finding", "title", "evidence")) for item in rows):
            return "findings"
        if rows and all(any(field in item for field in ("x", "y", "type")) for item in rows):
            return "chart"
        if rows:
            return "table"
        return "bullets"
    if isinstance(content, dict):
        keys = set(content)
        if keys & {"situation", "background", "assessment", "recommendation"}:
            return "summary"
        if keys & {"immediate", "short_term", "long_term"}:
            return "actions"
        if keys & {"current_state", "with_recommendations"}:
            return "comparison"
        return "key_value"
    return "narrative"


def _content_weight(content: Any) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(_content_weight(item) for item in content)
    if isinstance(content, dict):
        return sum(len(str(key)) + _content_weight(value) for key, value in content.items())
    return len(str(content or ""))


def _theme_for(template: str) -> ReportTheme:
    value = template.strip().lower()
    if value == "quick_brief":
        return "brief"
    if value in {"executive", "research", "technical", "custom"}:
        return value  # type: ignore[return-value]
    return "custom"


def _safe_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")[:64]


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True
