from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.agents.base import AgentSpec, make_agno_agent
from app.agents.data_analyst import DataAnalystAgent
from app.agents.data_engineer import DataEngineerAgent
from app.agents.report import ReportAgent
from app.services.llm_usage import extract_run_usage
from data_berge_core.contracts import get_flat_profile
from data_berge_core.memory import AgentMemory


logger = logging.getLogger(__name__)


AgentName = Literal["data_analyst", "data_engineer", "report_agent"]
AgentSkill = Literal[
    "intake",
    "profiling",
    "query",
    "visualization",
    "reporting",
    "engineering",
]


class AgentAssignment(BaseModel):
    agent: AgentName
    task: str = Field(min_length=1, max_length=2400)
    skill: AgentSkill

    @model_validator(mode="after")
    def validate_role_skill(self) -> "AgentAssignment":
        allowed = {
            "data_analyst": {"intake", "profiling", "query", "visualization"},
            "data_engineer": {"engineering"},
            "report_agent": {"reporting"},
        }
        if self.skill not in allowed[self.agent]:
            raise ValueError(f"{self.agent} cannot execute the {self.skill} skill")
        return self


class ManagerDecision(BaseModel):
    action: Literal["respond", "delegate"]
    response: str = ""
    intent: str = "general"
    focus: str = "conversation"
    assignments: list[AgentAssignment] = Field(default_factory=list, max_length=3)
    rationale: str = ""
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


@dataclass
class SharedConversationState:
    active_lead: str
    previous_lead: str | None
    handoff_reason: str | None
    user_intent: str
    conversation_focus: str
    agentic_mode: str = "manager"
    memory_context: str = ""
    tool_count: int = 0
    plan_steps: int = 0


class TeamCoordinator:
    """Model-led manager that delegates work to bounded role agents."""

    manager_spec = AgentSpec(
        name="TeamManagerAgent",
        role="Manage the analytics conversation and assign work to specialist agents.",
        instructions=(
            "Decide autonomously whether to respond conversationally or delegate a concrete task. "
            "Delegate every claim about dataset contents to a specialist so it can use trusted tools. "
            "Use the DataAnalystAgent for all dataset facts, inventory, counts, calculations, "
            "interpretation, profiling, and charts. Use the DataEngineerAgent only when the user asks "
            "to assess or change schema relationships, joins, typing, quality, cleaning, or readiness; and "
            "the ReportAgent for report planning, drafting, revision, layout, and execution. "
            "Assign multiple agents only when their expertise is independently necessary. "
            "Do not create reflection, debate, retry, or planning modes. Do not expose orchestration jargon."
        ),
    )

    def __init__(
        self,
        data_analyst: DataAnalystAgent,
        data_engineer: DataEngineerAgent,
        report_agent: ReportAgent,
        memory_path: str | None = None,
        manager_agent: Any | None = None,
    ) -> None:
        self.data_analyst = data_analyst
        self.data_engineer = data_engineer
        self.report_agent = report_agent
        self.memory = AgentMemory(
            storage_path=memory_path
            or os.path.join(os.path.dirname(__file__), "..", "..", "data", "agent_memory.json")
        )
        self.manager_agent = manager_agent or make_agno_agent(
            self.manager_spec,
            model_options={"temperature": 0.0},
        )

    def respond(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        history = history or []
        self._manager_usage: dict[str, Any] = {}
        self._manager_fallback_reason: dict[str, str] | None = None
        previous_lead = self._last_lead_from_history(history)
        memory_context = self.memory.get_context_summary(dataset.get("name"))
        decision = self._decide(message, dataset, history, memory_context)

        if decision.action == "respond":
            assignments: list[AgentAssignment] = []
            response = self._manager_response(decision)
            lead = "team_manager"
        else:
            if not decision.assignments:
                decision = self._fallback_decision(message, dataset, history)
            assignments = decision.assignments
            lead = assignments[0].agent
            state = self._build_state(decision, lead, previous_lead, memory_context, assignments)
            completed = [
                (
                    assignment,
                    self._execute_assignment(
                        assignment,
                        message,
                        dataset,
                        history,
                        state,
                    ),
                )
                for assignment in assignments
            ]
            response = self._combine_assignments(completed)

        state = self._build_state(decision, lead, previous_lead, memory_context, assignments)
        response.setdefault("handled_by", lead)
        response.setdefault("lead_agent", lead)
        response["shared_state"] = asdict(state)
        response["orchestration"] = {
            "manager": "team_manager",
            "action": decision.action,
            "intent": decision.intent,
            "assignments": [assignment.model_dump() for assignment in assignments],
            "rationale": decision.rationale,
        }
        if self._manager_fallback_reason:
            response["orchestration"]["fallback"] = self._manager_fallback_reason

        if previous_lead and previous_lead != lead:
            response["handoff"] = {
                "from": previous_lead,
                "to": lead,
                "reason": decision.rationale or "The manager assigned the next turn to a different specialist.",
            }

        self._record_to_memory(response, dataset)
        if self._manager_usage:
            response["_manager_token_usage"] = self._manager_usage
        return response

    def _decide(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
        memory_context: str,
    ) -> ManagerDecision:
        normalized = re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()
        report_explanation_check = getattr(self.data_analyst, "_looks_like_existing_report_explanation", None)
        if callable(report_explanation_check) and report_explanation_check(normalized, history):
            return ManagerDecision(
                action="delegate",
                intent="report_explanation",
                focus="existing_report",
                assignments=[AgentAssignment(agent="data_analyst", task=message, skill="query")],
                rationale="The user is asking about an existing report, so the Analyst should explain it rather than create another report.",
                confidence=0.98,
            )
        if not hasattr(self.manager_agent, "run"):
            self._manager_fallback_reason = {
                "stage": "manager_initialization",
                "error_type": "ManagerAgentUnavailable",
            }
            return self._fallback_decision(message, dataset, history)

        try:
            run_output = self.manager_agent.run(
                self._manager_prompt(message, dataset, history, memory_context),
                stream=False,
            )
            self._manager_usage = extract_run_usage(run_output)
            decision = self._parse_decision(getattr(run_output, "content", None))
            if decision and (decision.action == "respond" or decision.assignments):
                return decision
            self._manager_fallback_reason = {
                "stage": "manager_response_validation",
                "error_type": "InvalidManagerDecision",
            }
        except Exception as exc:
            self._manager_fallback_reason = {
                "stage": "manager_provider_call",
                "error_type": type(exc).__name__,
            }
            logger.warning("Team manager model call failed: %s", type(exc).__name__, exc_info=True)
        return self._fallback_decision(message, dataset, history)

    def _manager_prompt(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
        memory_context: str,
    ) -> str:
        recent_history = [
            {
                "role": str(item.get("role") or ""),
                "content": str(item.get("content") or "")[:600],
            }
            for item in history[-8:]
            if str(item.get("content") or "").strip()
        ]
        context = self._dataset_routing_context(dataset)
        return (
            "Manage this turn for the Data-Berge analytics team.\n\n"
            "Decision rules:\n"
            "- Use action=respond only for greetings, social replies, frustration, off-topic messages, "
            "or a clarification question that does not require inspecting data.\n"
            "- Use action=delegate for every factual statement, calculation, explanation, chart, "
            "engineering task, or report involving the dataset.\n"
            "- Put the primary agent first. Give each assignment a self-contained task and its exact skill.\n"
            "- DataAnalystAgent skills: intake, profiling, query, visualization. It owns every direct "
            "dataset fact, including row counts, column/field counts, field names, values, summaries, "
            "statistics, and calculations.\n"
            "- Use Analyst/query for row, column, or field counts and every specific calculation. "
            "Use Analyst/profiling for broad structure, column meaning, relationship, or overview requests.\n"
            "- DataEngineerAgent skill: engineering. Use it only when the user asks to assess, fix, or "
            "explain data quality, missingness, duplicates, type corrections, joins, keys, schema trust, "
            "cleaning, preparation, or readiness. A simple inventory question is never engineering.\n"
            "- ReportAgent skill: reporting.\n"
            "- A request to create, revise, approve, save, or run a report belongs to ReportAgent.\n"
            "- Confirming or revising an existing report plan always belongs to ReportAgent.\n"
            "- If the user asks to explain, interpret, or clarify an already generated report, delegate to DataAnalystAgent with query; do not create a new report plan unless they explicitly ask for a new report.\n"
            "- Do not answer dataset questions from the routing context yourself.\n"
            "- Keep a direct conversational response concise and natural.\n\n"
            "Examples:\n"
            "- 'How many fields are there?' -> delegate DataAnalystAgent with query.\n"
            "- 'What are the column names?' -> delegate DataAnalystAgent with query.\n"
            "- 'Are the column types trustworthy?' -> delegate DataEngineerAgent with engineering.\n"
            "- 'Create an executive report' -> delegate ReportAgent with reporting.\n\n"
            f"Dataset routing context: {json.dumps(context, ensure_ascii=False)}\n"
            f"Relevant team memory: {memory_context[:1200] or 'None'}\n"
            f"Recent conversation: {json.dumps(recent_history, ensure_ascii=False)}\n"
            f"User message: {message}\n\n"
            "Return exactly one JSON object and no markdown. Use this shape:\n"
            '{"action":"respond|delegate","response":"direct reply when action is respond",'
            '"intent":"short intent","focus":"short focus","assignments":['
            '{"agent":"data_analyst|data_engineer|report_agent","task":"specific task",'
            '"skill":"intake|profiling|query|visualization|reporting|engineering"}],'
            '"rationale":"brief routing reason","confidence":0.0}\n'
            "For action=respond, assignments must be empty. For action=delegate, response should be empty.\n"
        )

    def _dataset_routing_context(self, dataset: dict[str, Any]) -> dict[str, Any]:
        profile = dataset.get("profile", {}) or {}
        flat = get_flat_profile(profile)
        relational = profile.get("relational_schema", {}) or {}
        return {
            "name": dataset.get("name"),
            "row_count": dataset.get("row_count") or flat.get("row_count"),
            "column_count": dataset.get("column_count") or flat.get("column_count"),
            "columns": [
                {
                    "name": column.get("name"),
                    "semantic_type": column.get("semantic_type"),
                }
                for column in flat.get("columns", [])[:40]
            ],
            "relational_model": {
                "table_count": relational.get("table_count"),
                "table_names": relational.get("table_names", [])[:20],
                "relationship_count": relational.get("relationship_count"),
            }
            if relational
            else None,
        }

    def _parse_decision(self, content: Any) -> ManagerDecision | None:
        if isinstance(content, ManagerDecision):
            return content
        if isinstance(content, BaseModel):
            content = content.model_dump()
        if isinstance(content, dict):
            try:
                return ManagerDecision.model_validate(content)
            except ValidationError:
                return None
        if not isinstance(content, str):
            return None

        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            return ManagerDecision.model_validate_json(text[start : end + 1])
        except (ValidationError, ValueError):
            return None

    def _fallback_decision(
        self,
        message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> ManagerDecision:
        conversational_response = self._fallback_conversation_response(message)
        if conversational_response:
            return ManagerDecision(
                action="respond",
                response=conversational_response,
                intent="conversation",
                focus="greeting",
                assignments=[],
                rationale="The manager safety fallback handled a conversational message without invoking a dataset specialist.",
                confidence=0.9,
            )
        query_skill = getattr(self.data_analyst, "query_skill", None)
        can_answer_directly = getattr(query_skill, "can_answer_without_model", None)
        skill = self.data_analyst._select_skill(message, dataset, history)
        if callable(can_answer_directly) and can_answer_directly(message, dataset):
            assignment = AgentAssignment(agent="data_analyst", task=message, skill="query")
        elif skill == "reporting":
            assignment = AgentAssignment(agent="report_agent", task=message, skill="reporting")
        elif self.data_engineer.should_lead(message, dataset, history=history):
            assignment = AgentAssignment(agent="data_engineer", task=message, skill="engineering")
        else:
            assignment = AgentAssignment(agent="data_analyst", task=message, skill=skill)
        return ManagerDecision(
            action="delegate",
            intent=skill,
            focus=skill,
            assignments=[assignment],
            rationale="The manager safety fallback selected the closest role agent.",
            confidence=0.5,
        )

    @staticmethod
    def _fallback_conversation_response(message: str) -> str | None:
        """Keep obvious social turns out of specialist agents if manager inference fails."""
        normalized = re.sub(r"[^a-z0-9]+", " ", message.casefold()).strip()
        if not normalized:
            return "Hi! What would you like to explore in this dataset?"
        if re.fullmatch(r"(?:hey+|hi+|hello|helo|salam|assalamualaikum)(?: there)?", normalized):
            return "Hi! What would you like to explore in this dataset?"
        if re.search(r"\b(?:say|speak|reply|respond)\s+(?:hi+|hello|hey+)\b", normalized):
            return "Hi!"
        if re.fullmatch(r"(?:thanks|thank you|thankyou|tq|terima kasih)(?: so much)?", normalized):
            return "You're welcome. What would you like to explore next?"
        return None

    def _execute_assignment(
        self,
        assignment: AgentAssignment,
        original_message: str,
        dataset: dict[str, Any],
        history: list[dict[str, Any]],
        state: SharedConversationState,
    ) -> dict[str, Any]:
        task = assignment.task.strip()
        if task.casefold() == original_message.strip().casefold():
            agent_message = original_message
        else:
            agent_message = f"{task}\n\nOriginal user request: {original_message}"

        if assignment.agent == "report_agent":
            return self.report_agent.answer(dataset, agent_message, history)
        if assignment.agent == "data_engineer":
            return self.data_engineer.answer(
                agent_message,
                dataset,
                history,
                shared_state=asdict(state),
            )
        analyst_skill = assignment.skill if assignment.skill in {
            "intake",
            "profiling",
            "query",
            "visualization",
        } else None
        return self.data_analyst.answer(
            agent_message,
            dataset,
            history,
            data_engineer=self.data_engineer,
            assigned_skill=analyst_skill,
        )

    def _combine_assignments(
        self,
        completed: list[tuple[AgentAssignment, dict[str, Any]]],
    ) -> dict[str, Any]:
        primary_assignment, primary_result = completed[0]
        response = dict(primary_result)
        if len(completed) == 1:
            return response

        labels = {
            "data_analyst": "Analyst",
            "data_engineer": "Engineer",
            "report_agent": "Reporter",
        }
        answer_parts: list[str] = []
        evidence: list[str] = []
        confidences: list[float] = []
        for assignment, result in completed:
            answer = str(result.get("answer") or "").strip()
            if answer:
                answer_parts.append(f"**{labels[assignment.agent]}**\n{answer}")
            evidence.extend(str(item) for item in result.get("evidence", []))
            confidences.append(float(result.get("confidence", 0.5)))
            for key in ("sql", "data", "chart", "report_plan", "report_draft", "report_request", "artifact", "action"):
                if not response.get(key) and result.get(key):
                    response[key] = result[key]

        response["answer"] = "\n\n".join(answer_parts)
        response["evidence"] = list(dict.fromkeys(evidence))[:12]
        response["confidence"] = sum(confidences) / len(confidences)
        response["collaborators"] = [assignment.agent for assignment, _ in completed[1:]]
        response.setdefault("active_skill", primary_assignment.skill)
        return response

    def _manager_response(self, decision: ManagerDecision) -> dict[str, Any]:
        return {
            "answer": decision.response.strip() or "What would you like the analytics team to help with?",
            "evidence": [],
            "sql": None,
            "data": [],
            "chart": None,
            "confidence": decision.confidence,
            "mode": "conversation",
            "handled_by": "team_manager",
            "lead_agent": "team_manager",
        }

    def _build_state(
        self,
        decision: ManagerDecision,
        lead: str,
        previous_lead: str | None,
        memory_context: str,
        assignments: list[AgentAssignment],
    ) -> SharedConversationState:
        return SharedConversationState(
            active_lead=lead,
            previous_lead=previous_lead,
            handoff_reason=(
                decision.rationale if previous_lead and previous_lead != lead else None
            ),
            user_intent=decision.intent,
            conversation_focus=decision.focus,
            memory_context=memory_context,
            tool_count=len(getattr(self.data_analyst, "skill_names", [])) + 2,
            plan_steps=len(assignments),
        )

    def _last_lead_from_history(self, history: list[dict[str, Any]]) -> str | None:
        for item in reversed(history):
            if str(item.get("role")) != "assistant":
                continue
            payload = item.get("payload", {}) or {}
            lead = payload.get("lead_agent") or payload.get("handled_by")
            if isinstance(lead, str) and lead:
                return lead
        return None

    def _record_to_memory(self, response: dict[str, Any], dataset: dict[str, Any]) -> None:
        answer = str(response.get("answer", ""))
        confidence = float(response.get("confidence", 0))
        dataset_name = str(dataset.get("name", "unknown"))
        if (
            response.get("lead_agent") != "team_manager"
            and confidence >= 0.7
            and len(answer) > 50
        ):
            self.memory.record_analysis(
                dataset_name=dataset_name,
                column_name="general",
                insight=answer[:200],
                metadata={"confidence": confidence, "mode": response.get("mode", "agentic")},
            )
        for evidence in response.get("evidence", []):
            if "correlation" in str(evidence).lower() or "pattern" in str(evidence).lower():
                self.memory.record_pattern(dataset_name, str(evidence), confidence)
