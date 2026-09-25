"""Aether's native working and long-term conversational state."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class CognitiveState:
    turn_count: int = 0
    active_topic: Optional[str] = None
    last_intent: Optional[str] = None
    mood: str = "neutral"
    facts: Dict[str, str] = field(default_factory=dict)
    goals: List[str] = field(default_factory=list)
    recent_user_messages: List[str] = field(default_factory=list)

    def observe(self, message: str, topic: Optional[str] = None, intent: Optional[str] = None, emotion: str = "neutral") -> None:
        self.turn_count += 1
        if message.strip():
            self.recent_user_messages = (self.recent_user_messages + [message.strip()])[-12:]
        if topic: self.active_topic = topic
        if intent: self.last_intent = intent
        if emotion != "neutral": self.mood = emotion

    def remember(self, key: str, value: str) -> None:
        key, value = key.strip().lower(), value.strip()
        if key and value: self.facts[key] = value

    def add_goal(self, goal: str) -> None:
        goal = goal.strip()
        if goal and goal not in self.goals: self.goals = (self.goals + [goal])[-12:]

    def snapshot(self) -> dict:
        return {"turn_count": self.turn_count, "active_topic": self.active_topic, "last_intent": self.last_intent, "mood": self.mood, "facts": dict(self.facts), "goals": list(self.goals), "recent_user_messages": list(self.recent_user_messages)}
