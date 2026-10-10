"""
smartcorp_assistant.py - Assistant conversationnel SmartCorp

"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

# Import des 13 tools SmartCorp
from API_SmartCorp import ALL_TOOLS


# ============================================================================
# ===== CHARGEMENT ENV =====
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


# ============================================================================
# ===== CONFIG LLM (auto-détection OpenAI / NVIDIA) =====
# ============================================================================

_openai_key = os.getenv("OPENAI_API_KEY", "")
_nvidia_key = os.getenv("NVIDIA_API_KEY", "")


def _build_llm(model: str = None, temperature: float = 0) -> ChatOpenAI:
    """
    Construit un ChatOpenAI en fonction de la clé disponible.

    - Clé `sk-...`      → OpenAI standard
    - Clé `nvapi-...`   → NVIDIA NIM (compatible OpenAI)
    """
    # --- Priorité : vraie clé OpenAI ---
    if _openai_key.startswith("sk-"):
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            api_key=_openai_key,
            temperature=temperature,
            timeout=60,
            max_retries=3,
        )

    # --- Sinon : NVIDIA NIM ---
    if _nvidia_key.startswith("nvapi-"):
        return ChatOpenAI(
            model=model or "meta/llama-3.3-70b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=_nvidia_key,
            temperature=temperature,
            timeout=60,
            max_retries=3,
        )

    # --- Clé OpenAI au mauvais format (ex: nvapi- mise dans OPENAI_API_KEY) ---
    if _openai_key.startswith("nvapi-"):
        raise ValueError(
            f"❌ Ta clé dans OPENAI_API_KEY commence par 'nvapi-'\n"
            f"   → C'est une clé NVIDIA, pas OpenAI !\n"
            f"   → Renomme la variable : NVIDIA_API_KEY={_openai_key}\n"
            f"   → Ou crée une vraie clé OpenAI (commence par 'sk-')"
        )

    if _openai_key:
        raise ValueError(
            f"❌ OPENAI_API_KEY invalide : '{_openai_key[:10]}...'\n"
            f"   Une clé OpenAI doit commencer par 'sk-'"
        )

    raise ValueError(
        "❌ Aucune clé API trouvée dans .env\n"
        "   Ajoute : OPENAI_API_KEY=sk-proj-...\n"
        "   OU     : NVIDIA_API_KEY=nvapi-..."
    )


# ============================================================================
# ===== TOOLS REGISTRY =====
# ============================================================================

CUSTOM_TOOLS = ALL_TOOLS
SELF_MANAGED_TOOLS = {t.name for t in CUSTOM_TOOLS}


# ============================================================================
# ===== CLASSE ASSISTANT =====
# ============================================================================

class SmartCorpAssistant:
    """
    Assistant conversationnel pour SmartCorp (version OpenAI).

    Utilise :
    - 13 tools SmartCorp (recherche, filtres, stock, stats...)
    - Compatible OpenAI (`sk-...`) et NVIDIA NIM (`nvapi-...`)
    """

    def __init__(
        self,
        prompt_file: str = "prompt.md",
        model: str = None,
        temperature: float = 0,
    ):
        # ===== LLM =====
        self.llm = _build_llm(model=model, temperature=temperature)

        # ===== TOOLS =====
        self.tools = {t.name: t for t in CUSTOM_TOOLS}
        self.llm_with_tools = self.llm.bind_tools(CUSTOM_TOOLS)

        # ===== ÉTAT CONVERSATION =====
        self.messages = []
        self.system_message = self._get_system_message(prompt_file)
        self.messages.append(self.system_message)

        self.tool_sequence = []

    # ------------------------------------------------------------------
    # SYSTÈME
    # ------------------------------------------------------------------
    def _get_system_message(self, prompt_file: str) -> SystemMessage:
        """Charge le prompt système depuis un fichier markdown."""
        path = BASE_DIR / prompt_file
        try:
            with open(path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        except FileNotFoundError:
            system_prompt = (
                "Tu es l'assistant SmartCorp, spécialiste du catalogue "
                "de produits informatiques. Tu aides les utilisateurs à "
                "trouver des produits, vérifier les stocks, analyser le "
                "catalogue et suggérer des alternatives. "
                "Réponds en français, de manière concise. "
                "Les prix sont en FCFA."
            )
        return SystemMessage(content=system_prompt)

    # ------------------------------------------------------------------
    # CHAT
    # ------------------------------------------------------------------
    async def achat(self, message: str) -> str:
        """Version async du chat. Retourne la réponse texte finale."""
        self.tool_sequence = []

        # Ajouter le message utilisateur
        self.messages.append(HumanMessage(content=message))

        # Boucle ReAct : LLM → tools → LLM → ...
        while True:
            response = await self.llm_with_tools.ainvoke(self.messages)
            self.messages.append(response)

            # Plus aucun tool à appeler → réponse finale
            if not response.tool_calls:
                break

            # Exécuter chaque tool call
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                self.tool_sequence.append(tool_name)

                if tool_name in SELF_MANAGED_TOOLS:
                    tool = self.tools[tool_name]
                    try:
                        tool_result = await tool.ainvoke(tool_call)
                    except Exception as e:
                        tool_result = f"❌ Erreur tool '{tool_name}': {e}"

                    self.messages.append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call["id"],
                        )
                    )
                else:
                    self.messages.append(
                        ToolMessage(
                            content=f"❌ Tool inconnu : {tool_name}",
                            tool_call_id=tool_call["id"],
                        )
                    )

        return self._extract_text(response.content)

    def chat(self, message: str) -> str:
        """Version synchrone (wrapper autour de achat)."""
        return asyncio.run(self.achat(message))

    # ------------------------------------------------------------------
    # UTILITAIRES
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_text(content) -> str:
        """Extrait le texte d'un contenu (str OU list de blocs)."""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(parts)

        return str(content)

    def reset(self):
        """Réinitialise la conversation (garde le system message)."""
        self.messages = [self.system_message]
        self.tool_sequence = []

    def get_history(self) -> list:
        """Retourne l'historique des messages."""
        return self.messages

    def get_last_tool_sequence(self) -> list:
        """Retourne la séquence des tools appelés lors du dernier chat."""
        return self.tool_sequence