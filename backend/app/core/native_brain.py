"""Aether's provider-free native cognitive engine."""
from __future__ import annotations
import ast, operator, re
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
    emotion: str = "neutral"
    needs_clarification: bool = False

class AetherNativeBrain:
    """Aether's native perception -> memory -> reasoning -> response loop."""
    def __init__(self) -> None: self.state = CognitiveState()
    async def respond(self,message:str,history:Optional[List[AgentMessage]]=None)->Dict[str,Any]:
        text=message.strip()
        if not text:return self._package("conversation","Say something and I'm with you.",.99)
        thought=self._understand(text);self.state.observe(text,thought.topic,thought.intent,thought.emotion);self._learn_facts(text);self._learn_goal(text,thought)
        return self._package(thought.intent,self._compose(text,thought,history or []),thought.confidence,thought)
    def _package(self,intent:str,content:str,confidence:float,thought:Optional[NativeThought]=None)->Dict[str,Any]:
        return {"content":content,"intent":intent,"confidence":confidence,"topic":thought.topic if thought and thought.topic else self.state.active_topic,"tone":thought.tone if thought else "friendly","emotion":thought.emotion if thought else self.state.mood,"cognitive_state":self.state.snapshot()}
    def _understand(self,text:str)->NativeThought:
        lower=text.lower().strip();topic=self._topic(text);emotion=self._emotion(lower)
        if re.search(r"\b(hi|hello|hey|yo|sup|what's up|good morning|good evening)\b",lower): return NativeThought("greeting",.98,topic,"friendly",emotion)
        if re.search(r"\b(thanks|thank you|thx|ty|appreciate it)\b",lower): return NativeThought("thanks",.98,topic,"warm",emotion)
        if re.search(r"\b(bye|goodbye|see you|gotta go|talk later)\b",lower): return NativeThought("farewell",.98,topic,"warm",emotion)
        if re.search(r"\b(who are you|what are you|are you chatgpt|are you qwen|what model|what is aether|independent brain|your own brain|own brain)\b",lower): return NativeThought("identity",.99,"Aether","confident",emotion)
        if re.search(r"\b(what do you remember|what did i tell you|remember|memory|you remember)\b",lower): return NativeThought("memory",.94,self.state.active_topic,"attentive",emotion)
        if self.state.goals and re.search(r"^(yes|yeah|yep|yup)|\b(do it|continue|go ahead|exactly|that's right)\b",lower): return NativeThought("continue",.91,self.state.active_topic,"focused",emotion)
        if re.search(r"^(no|nope|nah)\b|\b(i mean|actually|not that|that's not what i meant)\b",lower): return NativeThought("correction",.90,topic or self.state.active_topic,"attentive",emotion)
        if re.search(r"\b(capable|capabilities|what can you do|what features|features)\b",lower): return NativeThought("capabilities",.95,topic,"helpful",emotion)
        if self._looks_like_math(text): return NativeThought("calculation",.99,"math","precise",emotion)
        if re.search(r"\b(build|make|create|develop|implement|fix|debug|code|design|plan|help me|i want to)\b",lower): return NativeThought("task",.88,topic,"focused",emotion,len(text.split())<=5 and topic is None)
        if re.search(r"\b(why|how|what|when|where|can you|could you|would you|explain|tell me|is it|does it)\b",lower): return NativeThought("question",.82,topic,"curious",emotion)
        if emotion!="neutral": return NativeThought("emotion",.84,topic,"supportive",emotion)
        return NativeThought("conversation",.68,topic,"casual",emotion)
    def _compose(self,text,thought,history):
        if thought.intent=="greeting": return ("Hey! I'm Aether. Good to see you.","Yo! Aether's here. What's up?","Hey — I'm here. What's up?")[(self.state.turn_count-1)%3]
        if thought.intent=="thanks": return ("Anytime.","Of course.","No problem.")[self.state.turn_count%3]
        if thought.intent=="farewell": return "Catch you later. I'll keep the current context in mind for this session."
        if thought.intent=="identity": return "I'm Aether — the native intelligence layer of AetherArc. My chat path runs through my own cognitive kernel rather than ChatGPT, Qwen, Claude, Llama, Hugging Face, or another hosted model as my brain."
        if thought.intent=="memory": return self._memory_reply()
        if thought.intent=="continue": return f"Yep. Let's keep going. The active goal is: {self.state.goals[-1]}"
        if thought.intent=="correction": return f"Got you — I'll correct course{(' on '+thought.topic) if thought.topic else ''}. Tell me what I got wrong and I'll use that as the new context."
        if thought.intent=="capabilities": return "My native core can infer conversational intent, track context, remember explicit facts, maintain goals, detect basic emotional cues, do safe arithmetic, and carry short follow-ups."
        if thought.intent=="calculation":
            result=self._calculate(text);return f"Yep — that's {result}." if result is not None else "I couldn't safely evaluate that locally, so I won't fake the result."
        if thought.intent=="task":
            if thought.needs_clarification:return "I'm ready. What exactly do you want me to build, fix, or change?"
            return f"Got it — you're working on {thought.topic or self.state.active_topic}. I've turned that into an active goal. Next I can break it into steps."
        if thought.intent=="question":
            return f"I follow the question about {thought.topic}. Give me a little more context and I'll reason from what you've told me instead of guessing." if thought.topic else "I follow the question. Give me one more detail and I'll work from what you've told me."
        if thought.intent=="emotion": return {"positive":"Nice — you sound pretty upbeat. I'm with you. What are we doing next?","frustrated":"Yeah, that sounds frustrating. Let's slow it down and tackle the actual problem.","confused":"I can see the confusion. Let's separate what we know from what we're still figuring out.","worried":"I hear the concern. Let's take it one piece at a time.","excited":"Haha, I can tell you're excited about this. Let's turn that energy into a solid next step."}.get(thought.emotion,"I'm following you. Let's work through it together.")
        return f"Yeah, I follow you. We're still on {self.state.active_topic}. What do you want to do with it?" if self.state.active_topic else "Yeah, I'm following. Keep going."
    def _memory_reply(self):
        parts=[f"{k.replace('_',' ')}: {v}" for k,v in list(self.state.facts.items())[-6:]]
        if self.state.goals:parts.append(f"active goal: {self.state.goals[-1]}")
        if self.state.active_topic:parts.append(f"current topic: {self.state.active_topic}")
        return "Here's what I currently remember: "+"; ".join(parts)+"." if parts else "I don't have a stored fact yet. Tell me something explicitly and I can remember it in this native session."
    def _learn_facts(self,text):
        patterns=[(r"\bmy name is\s+([A-Za-z0-9 _.-]{1,60})\s*[.!?]*$","name"),(r"\bcall me\s+([A-Za-z0-9 _.-]{1,60})\s*[.!?]*$","name"),(r"\bmy favorite ([A-Za-z][A-Za-z ]{0,30}) is ([A-Za-z0-9 _.-]{1,80})\s*[.!?]*$",None),(r"\bi (?:like|love) ([A-Za-z0-9 _.-]{1,80})\s*[.!?]*$","likes"),(r"\bi (?:dislike|hate) ([A-Za-z0-9 _.-]{1,80})\s*[.!?]*$","dislikes")]
        for pattern,key in patterns:
            m=re.search(pattern,text.strip(),re.I)
            if m:
                if key:self.state.remember(key,m.group(1).strip())
                else:self.state.remember("favorite_"+re.sub(r"\s+","_",m.group(1).strip().lower()),m.group(2).strip())
                break
    def _learn_goal(self,text,thought):
        if thought.intent=="task" and not thought.needs_clarification:
            goal=re.sub(r"^\s*(i want to|i need to|please|can you|could you)\s+","",text.strip(),flags=re.I)
            if goal:self.state.add_goal(goal)
    def _topic(self,text):
        lower=text.lower();known={"aether":("aether","aetherarc"),"android":("android","apk","gradle"),"github":("github","repo","repository","commit"),"robotics":("robot","robotics","gypsy","cherno"),"pc building":("pc","cpu","gpu","ram","ryzen","intel","rtx"),"coding":("code","coding","python","java","javascript","bug"),"gaming":("game","gaming","roblox","dbd")}
        for label,words in known.items():
            if any(re.search(r"\b"+re.escape(word)+r"\b",lower) for word in words):return label
        stop={"the","and","for","that","this","with","you","your","what","how","why","can","could","would","about","from","into","have","has","are","was","will","tell","please","want","need","help","does","did","is","it","me","my","to"}
        words=[w for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}",lower) if w not in stop];return words[0] if words else None
    def _emotion(self,lower):
        if re.search(r"\b(excited|awesome|amazing|let's go|hyped|love this)\b",lower):return "excited"
        if re.search(r"\b(frustrated|annoyed|angry|damn|ugh|wtf|broken again)\b",lower):return "frustrated"
        if re.search(r"\b(confused|confusing|don't understand|idk|lost)\b",lower):return "confused"
        if re.search(r"\b(worried|scared|afraid|concerned|nervous)\b",lower):return "worried"
        if re.search(r"\b(great|good|nice|cool|yay|happy)\b",lower):return "positive"
        return "neutral"
    def _looks_like_math(self,text):
        cleaned=re.sub(r"\b(what is|calculate|solve)\b","",text.lower()).strip();return bool(cleaned) and bool(re.fullmatch(r"[0-9+\-*/().%\s]+",cleaned))
    def _calculate(self,text):
        expression=re.sub(r"\b(what is|calculate|solve)\b","",text.lower()).strip()
        try:return self._eval_node(ast.parse(expression,mode="eval").body)
        except (SyntaxError,ValueError,TypeError,ZeroDivisionError,OverflowError):return None
    def _eval_node(self,node):
        ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Mod:operator.mod,ast.Pow:operator.pow}
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):return node.value
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=self._eval_node(node.operand);return value if isinstance(node.op,ast.UAdd) else -value
        if isinstance(node,ast.BinOp) and type(node.op) in ops:
            left,right=self._eval_node(node.left),self._eval_node(node.right)
            if isinstance(node.op,ast.Pow) and abs(right)>12:raise ValueError("power too large")
            if abs(left)>10**12 or abs(right)>10**12:raise ValueError("number too large")
            return ops[type(node.op)](left,right)
        raise ValueError("unsupported expression")
