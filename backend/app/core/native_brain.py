"""Aether's provider-free native cognitive kernel.

This module is intentionally independent of external language-model providers.
It is a small deterministic cognitive core, not a disguised API wrapper.
A future trained Aether neural model can implement the same interface without
changing the Aether front door.
"""
from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.agents.base import AgentMessage


@dataclass
class NativeThought:
    intent: str
    confidence: float
    topic: Optional[str] = None
    tone: str = "neutral"


class AetherNativeBrain:
    """Small local reasoning kernel used by Aether itself."""

    def __init__(self) -> None:
        self.turns = 0
        self.last_topic: Optional[str] = None
        self.facts: Dict[str, str] = {}

    async def respond(
        self,
        message: str,
        history: Optional[List[AgentMessage]] = None,
    ) -> Dict[str, Any]:
        text = message.strip()
        self.turns += 1
        thought = self._understand(text)
        if thought.topic:
            self.last_topic = thought.topic

        answer = self._compose(text, thought, history or [])
        return {
            "content": answer,
            "intent": thought.intent,
            "confidence": thought.confidence,
            "topic": thought.topic or self.last_topic,
            "tone": thought.tone,
        }

    def _understand(self, text: str) -> NativeThought:
        lower = text.lower()

        if re.search(r"\b(hi|hello|hey|yo|sup|good morning|good evening)\b", lower):
            return NativeThought("greeting", 0.98, tone="friendly")
        if re.search(r"\b(thanks|thank you|thx|ty)\b", lower):
            return NativeThought("thanks", 0.98, tone="friendly")
        if re.search(r"\b(bye|goodbye|see you|gotta go)\b", lower):
            return NativeThought("farewell", 0.98)
        if re.search(r"\b(who are you|what are you|are you chatgpt|are you qwen|are you claude|what model)\b", lower):
            return NativeThought("identity", 0.99, topic="Aether")
        if self._looks_like_math(text):
            return NativeThought("calculation", 0.96, topic="math")
        if re.search(r"\b(remember|memory|earlier|last time|we talked)\b", lower):
            return NativeThought("memory", 0.82, topic=self.last_topic)
        if re.search(r"\b(why|how|what|when|where|can you|could you|explain|tell me)\b", lower):
            return NativeThought("question", 0.72, topic=self._topic(text))
        return NativeThought("conversation", 0.60, topic=self._topic(text))

    def _compose(self, text: str, thought: NativeThought, history: List[AgentMessage]) -> str:
        if thought.intent == "greeting":
            return "Hey! I'm Aether. I'm running through my own native cognitive core here."
        if thought.intent == "thanks":
            return "You're welcome."
        if thought.intent == "farewell":
            return "See you later."
        if thought.intent == "identity":
            return (
                "I'm Aether, the intelligence layer built by AetherArc. "
                "This chat path is running my native provider-free cognitive core; "
                "it is not routing your message through ChatGPT, Qwen, Claude, or another hosted model."
            )
        if thought.intent == "calculation":
            result = self._calculate(text)
            if result is not None:
                return f"The answer is {result}."
            return "I can handle straightforward arithmetic locally, but I couldn't safely evaluate that expression."
        if thought.intent == "memory":
            if self.last_topic:
                return f"The local working state currently has our last detected topic as {self.last_topic}."
            return "I don't have a stored topic in my current local working state yet."
        if thought.intent == "question":
            return (
                "I understand the question, but my current native kernel is deliberately small. "
                "I won't pretend to know an answer that hasn't been encoded or learned by Aether yet. "
                "This is the foundation we can train and expand into Aether's own neural intelligence."
            )
        return (
            "I understand what you said. My native cognitive core is active, but it is still a "
            "small foundation rather than a fully trained general-purpose neural model."
        )

    def _topic(self, text: str) -> Optional[str]:
        words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", text.lower())
        stop = {
            "the", "and", "for", "that", "this", "with", "you", "are", "was",
            "what", "how", "why", "can", "could", "tell", "about", "from",
        }
        for word in words:
            if word not in stop:
                return word
        return None

    def _looks_like_math(self, text: str) -> bool:
        cleaned = text.lower().replace("what is", "").replace("calculate", "").strip()
        return bool(cleaned) and bool(re.fullmatch(r"[0-9+\-*/().%\s]+", cleaned))

    def _calculate(self, text: str) -> Optional[float | int]:
        expression = text.lower().replace("what is", "").replace("calculate", "").strip()
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
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("power too large")
            return ops[type(node.op)](left, right)
        raise ValueError("unsupported expression")
