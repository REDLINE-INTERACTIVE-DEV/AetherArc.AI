"""Aether's provider-free native cognitive engine.

This module is deliberately independent of hosted language-model providers.
It is a deterministic cognitive kernel, not a disguised API wrapper.
The next neural stage can replace the reasoning implementation while keeping
the same state/brain contract.
"""
from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.agents.base import AgentMessage
from app.core.cognitive_state import CognitiveState


@dataclass
class NativeThought:
    intent: str
    confidence: float
    topic: Optional[str] = None
    tone: str = "neutral"


class AetherNativeBrain:
    """Aether's own local cognitive kernel."""

    def __init__(self) -> None:
        self.state = CognitiveState()

    async def respond(
        self,
        message: str,
        history: Optional[List[AgentMessage]] = None,
    ) -> Dict[str, Any]:
        text = message.strip()
        self.state.observe(text)
        thought = self._understand(text)
        if thought.topic:
            self.state.active_topic = thought.topic
        self._learn_explicit_fact(text)
        answer = self._compose(text, thought, history or [])
        return {
            "content": answer,
            "intent": thought.intent,
            "confidence": thought.confidence,
            "topic": thought.topic or self.state.active_topic,
            "tone": thought.tone,
            "cognitive_state": self.state.snapshot(),
        }

    def _understand(self, text: str) -> NativeThought:
        lower = text.lower()

        if re.search(r"\b(hi|hello|hey|yo|sup|good morning|good evening)\b", lower):
            return NativeThought("greeting", 0.98, tone="friendly")
        if re.search(r"\b(thanks|thank you|thx|ty)\b", lower):
            return NativeThought("thanks", 0.98, tone="friendly")
        if re.search(r"\b(bye|goodbye|see you|gotta go)\b", lower):
            return NativeThought("farewell", 0.98)
        if re.search(r"\b(who are you|what are you|are you chatgpt|are you qwen|what model)\b", lower):
            return NativeThought("identity", 0.99, "Aether")
        if self._looks_like_math(text):
            return NativeThought("calculation", 0.97, "math")
        if re.search(r"\b(remember|memory|earlier|last time|we talked)\b", lower):
            return NativeThought("memory", 0.88, self.state.active_topic)
        if re.search(r"\b(build|make|create|develop|implement|fix|code|project)\b", lower):
            return NativeThought("task", 0.84, self._topic(text), "focused")
        if re.search(r"\b(why|how|what|when|where|can you|could you|explain|tell me)\b", lower):
            return NativeThought("question", 0.74, self._topic(text))
        return NativeThought("conversation", 0.62, self._topic(text))

    def _compose(
        self,
        text: str,
        thought: NativeThought,
        history: List[AgentMessage],
    ) -> str:
        if thought.intent == "greeting":
            return "Hey! I'm Aether. My native cognitive core is active."
        if thought.intent == "thanks":
            return "You're welcome."
        if thought.intent == "farewell":
            return "See you later."
        if thought.intent == "identity":
            return (
                "I'm Aether, the intelligence layer built by AetherArc. "
                "This front door is running my native provider-free cognitive core, "
                "not ChatGPT, Qwen, Claude, Llama, or another hosted model."
            )
        if thought.intent == "calculation":
            result = self._calculate(text)
            if result is not None:
                return f"The answer is {result}."
            return "I can evaluate straightforward arithmetic locally, but I won't pretend I can solve an expression my current kernel cannot safely evaluate."
        if thought.intent == "memory":
            if self.state.facts:
                facts = "; ".join(f"{k}={v}" for k, v in list(self.state.facts.items())[-4:])
                return f"My current native memory state contains: {facts}."
            if self.state.active_topic:
                return f"My current working context is the topic '{self.state.active_topic}'."
            return "I don't have a stored fact for that yet."
        if thought.intent == "task":
            topic = thought.topic or self.state.active_topic
            if topic:
                self.state.add_goal(text)
                return f"I understand this as a task about {topic}. I can keep it as an active goal while we build out Aether's native reasoning."
            return "I understand this as a task. I can track it as an active goal while we expand Aether's native reasoning."
        if thought.intent == "question":
            topic = thought.topic
            if topic:
                return f"I understand the question as being about {topic}. My native kernel is still small, so I won't invent knowledge it hasn't learned yet."
            return "I understand the question, but my current native kernel is still small and I won't invent an answer it doesn't know."
        return "I understand you. My native cognitive core is active, and I'm still being expanded into Aether's own trained intelligence."

    def _learn_explicit_fact(self, text: str) -> None:
        patterns = [
            (r"\bmy name is ([A-Za-z0-9 _.-]{1,60})\b", "name"),
            (r"\bcall me ([A-Za-z0-9 _.-]{1,60})\b", "name"),
            (r"\bmy favorite ([A-Za-z ]{1,30}) is ([A-Za-z0-9 _.-]{1,80})\b", None),
        ]
        lower = text.lower()
        for pattern, key in patterns:
            match = re.search(pattern, lower)
            if not match:
                continue
            if key:
                self.state.remember(key, match.group(1).strip())
            else:
                self.state.remember(f"favorite_{match.group(1).strip()}", match.group(2).strip())

    def _topic(self, text: str) -> Optional[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
        stop = {
            "the", "and", "for", "that", "this", "with", "you", "your",
            "what", "how", "why", "can", "could", "would", "about", "from",
            "into", "have", "has", "are", "was", "will", "tell", "please",
        }
        for word in words:
            if word not in stop:
                return word
        return None

    def _looks_like_math(self, text: str) -> bool:
        cleaned = re.sub(r"\b(what is|calculate|solve)\b", "", text.lower()).strip()
        return bool(cleaned) and bool(re.fullmatch(r"[0-9+\-*/().%\s]+", cleaned))

    def _calculate(self, text: str) -> Optional[float | int]:
        expression = re.sub(r"\b(what is|calculate|solve)\b", "", text.lower()).strip()
        try:
            tree = ast.parse(expression, mode="eval")
            return self._eval_node(tree.body)
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError):
            return None

    def _eval_node(self, node: ast.AST) -> float | int:
        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._eval_node(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise ValueError("power too large")
            return ops[type(node.op)](left, right)
        raise ValueError("unsupported expression")
