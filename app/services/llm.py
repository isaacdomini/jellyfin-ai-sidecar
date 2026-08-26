from typing import List, Dict, Any, Optional, Tuple
import re
import logging
import httpx
from app.core.config import settings
from app.models.schemas import (
    RagCitation,
    RagQueryResponse,
    SearchResultItem,
    ProviderModelInfo
)

logger = logging.getLogger(__name__)

# Provider metadata and defaults
PROVIDERS_INFO: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "default_model": "gpt-4o-mini",
        "available_models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "o1", "o3-mini"],
        "requires_api_key": True,
        "supports_base_url": True,
        "default_base_url": "https://api.openai.com/v1"
    },
    "gemini": {
        "name": "Google Gemini",
        "default_model": "gemini-3.1-flash-lite",
        "available_models": [
            "gemini-3.1-flash-lite",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash-lite",
            "gemma-4-26b",
            "gemma-4-31b"
        ],
        "requires_api_key": True,
        "supports_base_url": False,
        "default_base_url": "https://generativelanguage.googleapis.com"
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "default_model": "claude-3-5-haiku-20241022",
        "available_models": ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229"],
        "requires_api_key": True,
        "supports_base_url": False,
        "default_base_url": "https://api.anthropic.com"
    },
    "groq": {
        "name": "Groq",
        "default_model": "llama-3.3-70b-versatile",
        "available_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "requires_api_key": True,
        "supports_base_url": True,
        "default_base_url": "https://api.groq.com/openai/v1"
    },
    "ollama": {
        "name": "Ollama (Local)",
        "default_model": "llama3.2",
        "available_models": ["llama3.2", "mistral", "deepseek-r1", "qwen2.5", "phi3"],
        "requires_api_key": False,
        "supports_base_url": True,
        "default_base_url": "http://localhost:11434/v1"
    },
    "custom": {
        "name": "Custom (OpenAI Compatible)",
        "default_model": "custom-model",
        "available_models": ["custom-model", "deepseek-chat", "mistral-large", "qwen-max"],
        "requires_api_key": False,
        "supports_base_url": True,
        "default_base_url": "http://localhost:8000/v1"
    }
}


def format_seconds_to_hms(seconds: float) -> str:
    """
    Formats seconds float into standard HH:MM:SS format.
    Example: 6310.5 -> "01:45:10"
    """
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_timestamp_range(start_sec: float, end_sec: float) -> str:
    """
    Formats start and end seconds into 'HH:MM:SS - HH:MM:SS'.
    """
    return f"{format_seconds_to_hms(start_sec)} - {format_seconds_to_hms(end_sec)}"


def seconds_to_jellyfin_ticks(seconds: float) -> int:
    """
    Converts seconds to Jellyfin playback ticks (10,000,000 ticks per second).
    """
    return int(round(max(0.0, seconds) * 10_000_000))


def generate_deep_link(item_id: str, start_seconds: float, server_url: Optional[str] = None) -> str:
    """
    Generates a Jellyfin web client deep-link to jump directly to playback at the specified timestamp.
    Example: /web/index.html#!/playback?itemId=8e3b...&startPositionTicks=63100000000
    """
    ticks = seconds_to_jellyfin_ticks(start_seconds)
    base = server_url.rstrip("/") if server_url else ""
    return f"{base}/web/index.html#!/playback?itemId={item_id}&startPositionTicks={ticks}"


def build_rag_system_prompt() -> str:
    return (
        "You are an intelligent media assistant for a Jellyfin Media Server.\n"
        "Your task is to answer the user's question accurately using ONLY the provided dialogue and subtitle context from movies/shows.\n\n"
        "Guidelines:\n"
        "1. Direct Answer: Provide a concise, clear answer addressing the question.\n"
        "2. Exact Citation: When citing scenes, quotes, or dialogue, ALWAYS mention the media title and cite the exact timestamp range in brackets, e.g. [Movie: The Enigma, Timestamp: 01:45:10 - 01:46:20] or [01:45:10].\n"
        "3. Faithfulness: Only make claims supported by the provided context. If the answer is not present in the context, clearly state that the media dialogue does not contain the answer."
    )


def format_context_chunks(chunks: List[SearchResultItem]) -> str:
    """
    Formats retrieved subtitle search chunks into human-readable, timestamp-annotated context blocks for the LLM.
    """
    if not chunks:
        return "No relevant dialogue chunks found in the media library."

    formatted_blocks = []
    for i, c in enumerate(chunks, 1):
        ts_range = format_timestamp_range(c.start_time, c.end_time)
        item_title = c.item_name or f"Item {c.item_id}"
        formatted_blocks.append(
            f"--- Context [{i}] ---\n"
            f"Media: {item_title}\n"
            f"Item ID: {c.item_id}\n"
            f"Timestamp: {ts_range} (Start: {format_seconds_to_hms(c.start_time)}, {int(c.start_time)}s)\n"
            f"Dialogue: \"{c.text.strip()}\"\n"
        )

    return "\n".join(formatted_blocks)


class LLMService:
    """
    Multi-provider LLM service supporting OpenAI, Gemini, Claude, Groq, Ollama, and custom endpoints.
    """

    def __init__(self, timeout: float = 45.0):
        self.timeout = timeout

    @staticmethod
    def get_providers_info() -> List[ProviderModelInfo]:
        """
        Returns list of supported provider information for plugin UI settings.
        """
        return [
            ProviderModelInfo(
                id=pid,
                name=p["name"],
                default_model=p["default_model"],
                available_models=p["available_models"],
                requires_api_key=p["requires_api_key"],
                supports_base_url=p["supports_base_url"]
            )
            for pid, p in PROVIDERS_INFO.items()
        ]

    def resolve_provider_config(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, Optional[str], str, Optional[str], float]:
        """
        Resolves provider, API key, model, base URL, and temperature from request overrides or settings.
        """
        prov = (provider or settings.LLM_PROVIDER or "openai").lower().strip()
        if prov not in PROVIDERS_INFO and prov not in ["mock", "none"]:
            prov = "custom"

        prov_meta = PROVIDERS_INFO.get(prov, {})

        key = api_key if api_key is not None else settings.LLM_API_KEY
        m = model if model else (settings.LLM_MODEL or prov_meta.get("default_model", "default-model"))
        b_url = base_url if base_url else (settings.LLM_BASE_URL or prov_meta.get("default_base_url"))
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE

        return prov, key, m, b_url, temp

    async def generate_rag_response(
        self,
        query: str,
        retrieved_chunks: List[SearchResultItem],
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> RagQueryResponse:
        """
        Runs RAG generation: formats context, prompts LLM, and formats citations with timestamp deep-links.
        """
        prov, key, m, b_url, temp = self.resolve_provider_config(
            provider, api_key, model, base_url, temperature
        )

        context_str = format_context_chunks(retrieved_chunks)
        system_prompt = build_rag_system_prompt()
        user_prompt = (
            f"Context from Media Library Subtitles:\n{context_str}\n\n"
            f"User Question: {query}\n\n"
            f"Please answer the user's question and cite the exact timestamp range [Movie: <Title>, Timestamp: HH:MM:SS - HH:MM:SS]."
        )

        # Call the selected provider
        answer = ""
        try:
            if prov == "gemini":
                answer = await self._call_gemini(system_prompt, user_prompt, key, m, temp)
            elif prov == "anthropic":
                answer = await self._call_anthropic(system_prompt, user_prompt, key, m, temp)
            elif prov in ["openai", "groq", "ollama", "custom"]:
                answer = await self._call_openai_compatible(
                    system_prompt, user_prompt, key, m, b_url, temp, prov
                )
            else:
                # Mock / Offline fallback
                answer = self._generate_mock_rag_answer(query, retrieved_chunks)
        except Exception as exc:
            logger.error(f"Error calling LLM provider '{prov}' ({m}): {exc}", exc_info=True)
            # Fallback to intelligent local summary if provider call fails or has no key
            answer = (
                f"(Notice: LLM API call to {prov} encountered an issue: {exc}. Displaying retrieved dialogue evidence below:)\n\n"
                + self._generate_mock_rag_answer(query, retrieved_chunks)
            )

        # Build structured citations with Jellyfin deep-links
        citations: List[RagCitation] = []
        for chunk in retrieved_chunks:
            ts_formatted = format_timestamp_range(chunk.start_time, chunk.end_time)
            ticks = seconds_to_jellyfin_ticks(chunk.start_time)
            deep_link = generate_deep_link(chunk.item_id, chunk.start_time, settings.JELLYFIN_SERVER_URL)

            citations.append(
                RagCitation(
                    item_id=chunk.item_id,
                    item_name=chunk.item_name,
                    start_time=chunk.start_time,
                    end_time=chunk.end_time,
                    timestamp_formatted=ts_formatted,
                    start_ticks=ticks,
                    deep_link=deep_link,
                    text=chunk.text,
                    score=chunk.score
                )
            )

        return RagQueryResponse(
            query=query,
            answer=answer,
            provider_used=prov,
            model_used=m,
            citations=citations,
            sources=retrieved_chunks
        )

    async def _call_openai_compatible(
        self,
        system_prompt: str,
        user_prompt: str,
        api_key: Optional[str],
        model: str,
        base_url: Optional[str],
        temperature: float,
        provider_name: str
    ) -> str:
        """
        Handles OpenAI, Groq, Ollama /v1, and any OpenAI-compatible completions API.
        """
        if not api_key and provider_name not in ["ollama", "custom", "mock"]:
            return self._generate_mock_rag_answer(user_prompt, [])

        endpoint = f"{base_url.rstrip('/')}/chat/completions" if base_url else "https://api.openai.com/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": settings.LLM_MAX_TOKENS
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _call_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        api_key: Optional[str],
        model: str,
        temperature: float
    ) -> str:
        """
        Calls Google Gemini generateContent REST API.
        """
        if not api_key:
            raise ValueError("Gemini API key is required. Please set LLM_API_KEY or configure it in the plugin settings.")

        target_model = (model or "gemini-3.7-flash").strip()

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        }

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent"
        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": settings.LLM_MAX_TOKENS
            }
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        return "No response generated by Gemini."
                    parts = candidates[0].get("content", {}).get("parts", [])
                    return "".join(p.get("text", "") for p in parts).strip()
            except httpx.HTTPStatusError as e:
                # If rate limited (429) or temporary server overload (503), retry once after a polite pause
                if e.response.status_code in [503, 429] and attempt == 0:
                    import asyncio
                    logger.warning(f"Gemini returned {e.response.status_code}. Waiting 2s before retry...")
                    await asyncio.sleep(2.0)
                    continue
                raise e
            except Exception as e:
                raise e

        return "No response received from Gemini."

    async def _call_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        api_key: Optional[str],
        model: str,
        temperature: float
    ) -> str:
        """
        Calls Anthropic Claude messages API.
        """
        if not api_key:
            raise ValueError("Anthropic API key is required. Please set LLM_API_KEY or configure it in the plugin settings.")

        endpoint = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": model,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": settings.LLM_MAX_TOKENS
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data.get("content", [])
            return "".join(c.get("text", "") for c in content if c.get("type") == "text").strip()

    async def translate_text_to_english(
        self,
        text: str,
        source_language: str = "auto",
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Translates subtitle text or movie dialogue from a foreign language into English.
        Automatically uses 'gemini-3.5-live-translate' for Gemini to prevent consuming Q&A search quotas.
        """
        if not text.strip():
            return ""

        prov, key, m, b_url, temp = self.resolve_provider_config(provider, api_key, model)
        # Use dedicated live translation model for Gemini by default
        if prov == "gemini" and not model:
            m = "gemini-3.5-live-translate"

        sys_prompt = (
            "You are a professional film and television subtitle translator.\n"
            f"Translate the provided movie dialogue from {source_language} into clear, natural English.\n"
            "Maintain exact dialogue meaning, names, and emotional tone. "
            "If input contains numbered items like [1], [2], preserve the exact numbered format. "
            "Output ONLY the translated English text, without commentary or introductory remarks."
        )

        try:
            if prov == "gemini":
                return await self._call_gemini(sys_prompt, text, key, m, 0.1)
            elif prov == "anthropic":
                return await self._call_anthropic(sys_prompt, text, key, m, 0.1)
            elif prov in ["openai", "groq", "ollama", "custom"]:
                return await self._call_openai_compatible(sys_prompt, text, key, m, b_url, 0.1, prov)
            else:
                return f"[Translated from {source_language}]: {text}"
        except Exception as exc:
            logger.warning(f"Subtitle translation via {prov} failed ({exc}). Using original text.")
            return text

    async def translate_chunks_to_english(
        self,
        chunks: List[Dict[str, Any]],
        source_language: str = "auto",
        batch_size: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Translates a list of subtitle chunks from a foreign language into English in efficient batches
        while preserving exact timestamp intervals.
        """
        if not chunks:
            return []

        logger.info(f"Translating {len(chunks)} subtitle chunks from {source_language} to English...")
        translated_chunks = []

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            if len(batch) == 1:
                translated_text = await self.translate_text_to_english(
                    batch[0]["text"],
                    source_language=source_language
                )
                new_chunk = dict(batch[0])
                new_chunk["text"] = translated_text
                translated_chunks.append(new_chunk)
            else:
                # Format batch into numbered text block
                prompt_lines = [f"[{idx + 1}] {c['text']}" for idx, c in enumerate(batch)]
                batch_text = "\n".join(prompt_lines)
                translated_batch_text = await self.translate_text_to_english(
                    batch_text,
                    source_language=source_language
                )

                # Parse numbered translations
                parsed = {}
                for line in translated_batch_text.splitlines():
                    line = line.strip()
                    match = re.match(r"^\[(\d+)\]\s*(.+)$", line)
                    if match:
                        idx = int(match.group(1)) - 1
                        parsed[idx] = match.group(2).strip()

                for idx, c in enumerate(batch):
                    new_chunk = dict(c)
                    new_chunk["text"] = parsed.get(idx, c["text"])
                    translated_chunks.append(new_chunk)

        return translated_chunks

    def _generate_mock_rag_answer(self, query: str, chunks: List[SearchResultItem]) -> str:
        """
        Generates a synthetic citation-rich answer when in mock/offline mode or testing.
        """
        if not chunks:
            return f"I couldn't find any dialogue in your media library relating to \"{query}\"."

        top = chunks[0]
        title = top.item_name or f"Item {top.item_id}"
        ts_range = format_timestamp_range(top.start_time, top.end_time)

        return (
            f"Based on the dialogue in **{title}**, at timestamp **[{ts_range}]**, "
            f"the scene states:\n\n> \"{top.text.strip()}\"\n\n"
            f"You can jump straight to this scene in your player using the cited timestamp."
        )


llm_service = LLMService()
