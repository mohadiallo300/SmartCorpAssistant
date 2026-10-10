"""
LangGraph.py - Assistant SmartCorp (NVIDIA via ChatOpenAI)

"""

import os
import asyncio
from pathlib import Path
from typing import Annotated, List, Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
    ToolMessage,
    BaseMessage,
)
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from API_SmartCorp import ALL_TOOLS


# ============================================================================
# ===== CHARGEMENT ENV =====
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

if not os.getenv("NVIDIA_API_KEY"):
    raise ValueError(
        f"❌ NVIDIA_API_KEY manquante.\n"
        f"   Ajoute-la dans : {env_path}"
    )


# ============================================================================
# ===== CLASSE WRAPPER : NORMALISATION DES MESSAGES POUR NVIDIA =====
# ============================================================================

def _flatten_content(content: Any) -> str:
    """
    Aplatit un contenu en chaîne de caractères simple.

    Gère :
    - str  → renvoyé tel quel
    - list → concatène les blocs 'text'
    - dict → extrait 'text' si présent
    - None → ""
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if "text" in content:
            return str(content["text"])
        return str(content)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
        return "\n".join(parts)
    return str(content)


class NVIDIAChatWrapper(ChatOpenAI):
    """
    Wrapper qui corrige le format des messages pour NVIDIA NIM.

    NVIDIA NIM (gpt-oss-20b) attend :
    - content : string (jamais une liste de dicts)
    - tool_calls : format OpenAI standard

    LangChain envoie par défaut le content des ToolMessage sous forme
    de liste [{'type':'text','text':'...'}], ce qui provoque :
    Error 400 - "Input should be a valid dictionary or instance of Content"
    """

    def _prepare_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Normalise tous les messages avant envoi à l'API."""
        normalized: List[BaseMessage] = []

        for msg in messages:
            content_str = _flatten_content(msg.content)

            if isinstance(msg, ToolMessage):
                normalized.append(
                    ToolMessage(
                        content=content_str,
                        tool_call_id=msg.tool_call_id,
                    )
                )

            elif isinstance(msg, AIMessage):
                normalized.append(
                    AIMessage(
                        content=content_str,
                        tool_calls=getattr(msg, "tool_calls", None) or [],
                    )
                )

            elif isinstance(msg, HumanMessage):
                normalized.append(HumanMessage(content=content_str))

            elif isinstance(msg, SystemMessage):
                normalized.append(SystemMessage(content=content_str))

            else:
                normalized.append(msg)

        return normalized

    def _generate(
        self,
        messages: List[BaseMessage],
        stop=None,
        run_manager: CallbackManagerForLLMRun = None,
        **kwargs,
    ) -> ChatResult:
        messages = self._prepare_messages(messages)
        return super()._generate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop=None,
        run_manager: AsyncCallbackManagerForLLMRun = None,
        **kwargs,
    ) -> ChatResult:
        messages = self._prepare_messages(messages)
        return await super()._agenerate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )


# ============================================================================
# ===== LLM =====
# ============================================================================

llm = NVIDIAChatWrapper(
    model="openai/gpt-oss-20b",
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
    temperature=0.3,
    timeout=60,
    max_retries=3,
)

llm_with_tools = llm.bind_tools(ALL_TOOLS)


# ============================================================================
# ===== SYSTEM MESSAGE =====
# ============================================================================

prompt_path = BASE_DIR / "prompt.md"
if prompt_path.exists():
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()
else:
    system_prompt = (
        "Tu es l'assistant SmartCorp, spécialiste du catalogue de matériel "
        "informatique. Tu aides les utilisateurs à trouver des produits, "
        "vérifier les stocks, analyser le catalogue et suggérer des "
        "alternatives. Réponds en français, de manière concise. "
        "Les prix sont en FCFA."
    )

system_message = SystemMessage(content=system_prompt)


# ============================================================================
# ===== STATE =====
# ============================================================================

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ============================================================================
# ===== NODES =====
# ============================================================================

async def areason(state: State) -> dict:
    """Nœud de raisonnement : le LLM analyse et décide."""
    messages = [system_message] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


act = ToolNode(ALL_TOOLS)


# ============================================================================
# ===== GRAPHE =====
# ============================================================================

builder = StateGraph(State)
builder.add_node("reason", areason)
builder.add_node("act", act)

builder.add_edge(START, "reason")
builder.add_conditional_edges(
    "reason",
    tools_condition,
    {"tools": "act", END: END},
)
builder.add_edge("act", "reason")

smartcorp_assistant = builder.compile()