"""Persistent memory for agents across conversations.

Stores user preferences, past analyses, learned patterns,
and conversation summaries that persist between sessions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MemoryEntry:
    """A single memory entry."""
    key: str
    value: Any
    category: str  # preference, analysis, pattern, summary
    timestamp: float = field(default_factory=time.time)
    ttl: float | None = None  # Time to live in seconds, None = forever
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentMemory:
    """Persistent memory store for agents.

    Categories:
    - preference: User preferences (e.g., "user prefers bar charts")
    - analysis: Past analysis results (e.g., "Income is right-skewed")
    - pattern: Learned patterns (e.g., "Credit_Score correlates with Income")
    - summary: Conversation summaries
    """

    def __init__(self, storage_path: str | None = None, max_entries: int = 500) -> None:
        self.storage_path = storage_path
        self.max_entries = max_entries
        self._store: dict[str, MemoryEntry] = {}
        self._load()

    def remember(
        self,
        key: str,
        value: Any,
        category: str = "analysis",
        ttl: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a piece of information in memory."""
        self._store[key] = MemoryEntry(
            key=key,
            value=value,
            category=category,
            ttl=ttl,
            metadata=metadata or {},
        )
        self._evict_if_needed()
        self._save()

    def recall(
        self,
        key: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Retrieve information from memory.

        If key is provided, returns that specific entry.
        If category is provided, returns all entries in that category.
        Otherwise returns all entries.
        """
        self._clean_expired()

        if key:
            entry = self._store.get(key)
            if entry:
                return {"key": entry.key, "value": entry.value, "category": entry.category}
            return {}

        if category:
            return [
                {"key": e.key, "value": e.value, "category": e.category}
                for e in self._store.values()
                if e.category == category
            ]

        return [
            {"key": e.key, "value": e.value, "category": e.category}
            for e in self._store.values()
        ]

    def forget(self, key: str) -> bool:
        """Remove a specific memory entry."""
        if key in self._store:
            del self._store[key]
            self._save()
            return True
        return False

    def clear_category(self, category: str) -> int:
        """Remove all entries in a category."""
        to_remove = [k for k, v in self._store.items() if v.category == category]
        for k in to_remove:
            del self._store[k]
        self._save()
        return len(to_remove)

    def get_context_summary(self, dataset_name: str | None = None) -> str:
        """Get a human-readable summary of what the agent remembers.

        This is injected into agent prompts to provide context.
        """
        self._clean_expired()

        if not self._store:
            return ""

        parts = ["## Agent Memory (what I remember from previous interactions)"]

        preferences = [e for e in self._store.values() if e.category == "preference"]
        if preferences:
            parts.append("\nUser preferences:")
            for entry in preferences[:10]:
                parts.append(f"- {entry.key}: {entry.value}")

        analysis_prefix = f"analysis:{dataset_name}:" if dataset_name else "analysis:"
        analyses = [
            e
            for e in self._store.values()
            if e.category == "analysis" and e.key.startswith(analysis_prefix)
        ]
        if analyses:
            parts.append("\nPast analyses:")
            for entry in analyses[:10]:
                parts.append(f"- {entry.key}: {entry.value}")

        pattern_prefix = f"pattern:{dataset_name}:" if dataset_name else "pattern:"
        patterns = [
            e
            for e in self._store.values()
            if e.category == "pattern" and e.key.startswith(pattern_prefix)
        ]
        if patterns:
            parts.append("\nDiscovered patterns:")
            for entry in patterns[:10]:
                parts.append(f"- {entry.key}: {entry.value}")

        return "\n".join(parts)

    def record_analysis(
        self,
        dataset_name: str,
        column_name: str,
        insight: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an analysis insight for future reference."""
        key = f"analysis:{dataset_name}:{column_name}:{int(time.time())}"
        self.remember(key, insight, category="analysis", metadata=metadata or {})

    def record_pattern(
        self,
        dataset_name: str,
        pattern: str,
        confidence: float = 0.8,
    ) -> None:
        """Record a discovered pattern."""
        key = f"pattern:{dataset_name}:{pattern[:50]}"
        self.remember(key, pattern, category="pattern", metadata={"confidence": confidence})

    def record_preference(self, preference: str, value: Any) -> None:
        """Record a user preference."""
        key = f"pref:{preference}"
        self.remember(key, value, category="preference")

    def get_column_history(self, dataset_name: str, column_name: str) -> list[dict[str, Any]]:
        """Get all analyses for a specific column."""
        self._clean_expired()
        prefix = f"analysis:{dataset_name}:{column_name}:"
        return [
            {"key": e.key, "value": e.value, "timestamp": e.timestamp}
            for e in self._store.values()
            if e.key.startswith(prefix)
        ]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load memory from disk."""
        if not self.storage_path:
            return
        path = Path(self.storage_path)
        if not path.exists():
            return
        try:
            with open(path) as f:
                data = json.load(f)
            for entry_data in data:
                entry = MemoryEntry(
                    key=entry_data["key"],
                    value=entry_data["value"],
                    category=entry_data["category"],
                    timestamp=entry_data.get("timestamp", time.time()),
                    ttl=entry_data.get("ttl"),
                    metadata=entry_data.get("metadata", {}),
                )
                self._store[entry.key] = entry
        except Exception:
            pass

    def _save(self) -> None:
        """Persist memory to disk."""
        if not self.storage_path:
            return
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "key": e.key,
                    "value": e.value,
                    "category": e.category,
                    "timestamp": e.timestamp,
                    "ttl": e.ttl,
                    "metadata": e.metadata,
                }
                for e in self._store.values()
            ]
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass

    def _clean_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [
            k for k, v in self._store.items()
            if v.ttl and (now - v.timestamp) > v.ttl
        ]
        for k in expired:
            del self._store[k]

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if store is full."""
        if len(self._store) <= self.max_entries:
            return
        # Sort by timestamp, remove oldest
        sorted_keys = sorted(self._store.keys(), key=lambda k: self._store[k].timestamp)
        to_remove = sorted_keys[:len(self._store) - self.max_entries]
        for k in to_remove:
            del self._store[k]
