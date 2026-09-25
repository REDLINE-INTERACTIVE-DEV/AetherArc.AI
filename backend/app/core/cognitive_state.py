"""Aether's provider-free cognitive state.

This is the state layer between raw messages and Aether's native reasoning kernel.
It stores short-term context, explicit user facts, active topic, and simple goals.
It does not call a model, network service, or external provider.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CognitiveState:
    turn_count: int = 0
    active_topic: Optional[str] = None
    facts: Dict[str, str] = field(default_factory=dict)
    goals: List[str] = field(default_factory=list)
    recent_user_messages: List[str] = field(default_factory=list)

    def observe(self, message: str, topic: Optional[str] = None) -> None:
        self.turn_count += 1
        text = message.strip()
        if text:
            self.recent_user_messages.append(text)
            self.recent_user_messages = self.recent_user_messages[-8:]
        if topic:
            self.active_topic = topic

    def remember(self, key: str, value: str) -> None:
        key = key.strip().lower()
        value = value.strip()
        if key and value:
            self.facts[key] = value

    def add_goal(self, goal: str) -> None:
        goal = goal.strip()
        if goal and goal not in self.goals:
            self.goals.append(goal)

    def snapshot(self) -> dict:
        return {
            "turn_count": self.turn_count,
            "active_topic": self.active_topic,
            "facts": dict(self.facts),
            "goals": list(self.goals),
            "recent_user_messages": list(self.recent_user_messages),
        }
