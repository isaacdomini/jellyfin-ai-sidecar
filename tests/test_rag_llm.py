import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import SearchResultItem
from app.services.llm import (
    format_seconds_to_hms,
    format_timestamp_range,
    seconds_to_jellyfin_ticks,
    generate_deep_link,
    format_context_chunks,
    llm_service,
    PROVIDERS_INFO
)


def test_timestamp_formatting_helpers():
    assert format_seconds_to_hms(0) == "00:00:00"
    assert format_seconds_to_hms(65.0) == "00:01:05"
    assert format_seconds_to_hms(3665.0) == "01:01:05"
    assert format_seconds_to_hms(6310.0) == "01:45:10"
    assert format_seconds_to_hms(6380.0) == "01:46:20"

    assert format_timestamp_range(6310.0, 6380.0) == "01:45:10 - 01:46:20"


def test_jellyfin_ticks_and_deep_link():
    ticks = seconds_to_jellyfin_ticks(6310.0)
    assert ticks == 63100000000  # 6310s * 10,000,000 ticks/sec

    # Deep link without server base URL
    link1 = generate_deep_link("movie-enigma-123", 6310.0)
    assert link1 == "/web/index.html#!/playback?itemId=movie-enigma-123&startPositionTicks=63100000000"

    # Deep link with server base URL
    link2 = generate_deep_link("movie-enigma-123", 6310.0, "http://localhost:8096")
    assert link2 == "http://localhost:8096/web/index.html#!/playback?itemId=movie-enigma-123&startPositionTicks=63100000000"


def test_format_context_chunks():
    chunks = [
        SearchResultItem(
            id=1,
            item_id="enigma-456",
            item_name="The Enigma",
            text="The combination is hidden in the painting's frame.",
            start_time=6310.0,
            end_time=6380.0,
            score=0.95
        )
    ]
    formatted = format_context_chunks(chunks)
    assert "Media: The Enigma" in formatted
    assert "Item ID: enigma-456" in formatted
    assert "Timestamp: 01:45:10 - 01:46:20" in formatted
    assert "The combination is hidden in the painting's frame." in formatted


def test_providers_info():
    providers = llm_service.get_providers_info()
    provider_ids = [p.id for p in providers]

    assert "openai" in provider_ids
    assert "gemini" in provider_ids
    assert "anthropic" in provider_ids
    assert "groq" in provider_ids
    assert "ollama" in provider_ids
    assert "custom" in provider_ids


@pytest.mark.asyncio
async def test_llm_rag_generation_mock_mode():
    sample_chunk = SearchResultItem(
        id=1,
        item_id="item-enigma-999",
        item_name="The Enigma",
        text="The combination is hidden in the painting's frame.",
        start_time=6310.0,
        end_time=6380.0,
        score=0.92
    )

    response = await llm_service.generate_rag_response(
        query="What was the final puzzle the villain left?",
        retrieved_chunks=[sample_chunk],
        provider="mock"
    )

    assert response.query == "What was the final puzzle the villain left?"
    assert "The Enigma" in response.answer
    assert "01:45:10 - 01:46:20" in response.answer
    assert "The combination is hidden in the painting's frame." in response.answer

    assert len(response.citations) == 1
    cit = response.citations[0]
    assert cit.item_id == "item-enigma-999"
    assert cit.item_name == "The Enigma"
    assert cit.timestamp_formatted == "01:45:10 - 01:46:20"
    assert cit.start_ticks == 63100000000
    assert "startPositionTicks=63100000000" in cit.deep_link


def test_fastapi_rag_endpoints():
    client = TestClient(app)

    # 1. Test GET /rag/providers
    resp = client.get("/rag/providers")
    assert resp.status_code == 200
    providers = resp.json()
    assert len(providers) >= 5
    assert any(p["id"] == "openai" for p in providers)
    assert any(p["id"] == "gemini" for p in providers)

    # 2. Test empty query validation
    bad_resp = client.post("/rag/query", json={"query": "   "})
    assert bad_resp.status_code == 400

    # 3. Test mock RAG query via POST /rag/query
    sample_chunk_dict = [{
        "id": 1,
        "item_id": "enigma-id",
        "item_name": "The Enigma",
        "text": "The combination is hidden in the painting's frame.",
        "start_time": 6310.0,
        "end_time": 6380.0,
        "score": 0.94
    }]

    with patch("app.api.rag.search_similar_chunks", return_value=sample_chunk_dict):
        query_payload = {
            "query": "What was the final puzzle the villain left?",
            "provider": "mock",
            "top_k": 3
        }
        res = client.post("/rag/query", json=query_payload)
        assert res.status_code == 200
        data = res.json()

        assert data["query"] == "What was the final puzzle the villain left?"
        assert "answer" in data
        assert "01:45:10 - 01:46:20" in data["answer"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["item_name"] == "The Enigma"
        assert data["citations"][0]["timestamp_formatted"] == "01:45:10 - 01:46:20"
        assert data["citations"][0]["start_ticks"] == 63100000000
        assert "startPositionTicks=63100000000" in data["citations"][0]["deep_link"]

        # Also test /rag/ask endpoint alias
        alias_res = client.post("/rag/ask", json=query_payload)
        assert alias_res.status_code == 200
        alias_data = alias_res.json()
        assert alias_data["query"] == query_payload["query"]


@pytest.mark.asyncio
async def test_openai_compatible_call():
    chunk = SearchResultItem(
        id=1,
        item_id="item-1",
        item_name="The Enigma",
        text="The combination is hidden in the painting's frame.",
        start_time=6310.0,
        end_time=6380.0,
        score=0.9
    )

    mock_openai_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "The puzzle reveals the combination is in the painting's frame [The Enigma, 01:45:10 - 01:46:20]."
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = lambda: mock_openai_response
        mock_post.return_value = mock_response

        res = await llm_service.generate_rag_response(
            query="What was the final puzzle?",
            retrieved_chunks=[chunk],
            provider="openai",
            api_key="sk-test-key",
            model="gpt-4o-mini"
        )

        assert res.provider_used == "openai"
        assert res.model_used == "gpt-4o-mini"
        assert "painting's frame" in res.answer
        assert len(res.citations) == 1
        assert res.citations[0].start_ticks == 63100000000


@pytest.mark.asyncio
async def test_gemini_call():
    chunk = SearchResultItem(
        id=1,
        item_id="item-2",
        item_name="The Enigma",
        text="The combination is hidden in the painting's frame.",
        start_time=6310.0,
        end_time=6380.0,
        score=0.9
    )

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Gemini answer: Clue is in the frame [01:45:10 - 01:46:20]."}]
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = lambda: mock_gemini_response
        mock_post.return_value = mock_response

        res = await llm_service.generate_rag_response(
            query="What was the final puzzle?",
            retrieved_chunks=[chunk],
            provider="gemini",
            api_key="AIzaSyTestKey",
            model="gemini-2.0-flash"
        )

        assert res.provider_used == "gemini"
        assert "Gemini answer" in res.answer


@pytest.mark.asyncio
async def test_anthropic_call():
    chunk = SearchResultItem(
        id=1,
        item_id="item-3",
        item_name="The Enigma",
        text="The combination is hidden in the painting's frame.",
        start_time=6310.0,
        end_time=6380.0,
        score=0.9
    )

    mock_claude_response = {
        "content": [
            {
                "type": "text",
                "text": "Claude answer: The combination is hidden in the frame [The Enigma, 01:45:10]."
            }
        ]
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json = lambda: mock_claude_response
        mock_post.return_value = mock_response

        res = await llm_service.generate_rag_response(
            query="What was the final puzzle?",
            retrieved_chunks=[chunk],
            provider="anthropic",
            api_key="sk-ant-test-key",
            model="claude-3-5-haiku-20241022"
        )

        assert res.provider_used == "anthropic"
        assert "Claude answer" in res.answer


@pytest.mark.asyncio
async def test_single_english_subtitle_selection():
    from app.services.extractor import (
        is_english_identifier,
        extract_best_single_subtitle
    )

    assert is_english_identifier("eng") is True
    assert is_english_identifier("English (SDH)") is True
    assert is_english_identifier("en") is True
    assert is_english_identifier("spa") is False
    assert is_english_identifier("French") is False

    mock_streams = [
        {"stream_index": 2, "relative_index": 0, "language": "spa", "title": "Spanish", "is_english": False, "is_forced": False, "is_sdh": False},
        {"stream_index": 3, "relative_index": 1, "language": "eng", "title": "English", "is_english": True, "is_forced": False, "is_sdh": False},
        {"stream_index": 4, "relative_index": 2, "language": "eng", "title": "English Commentary", "is_english": True, "is_forced": False, "is_sdh": False},
    ]

    with patch("os.path.exists", return_value=True), \
         patch("app.services.extractor.find_external_subtitles_classified", return_value=[]), \
         patch("app.services.extractor.probe_subtitle_streams", return_value=mock_streams), \
         patch("app.services.extractor.extract_embedded_stream_to_srt", return_value="1\n00:00:01,000 --> 00:00:03,000\nHello World\n"):

        content, lang, is_eng = extract_best_single_subtitle("/media/movie.mkv")
        # Ensure it selects the first standard English stream and identifies as English
        assert is_eng is True
        assert lang == "eng"
        assert "Hello World" in content


@pytest.mark.asyncio
async def test_translate_foreign_subtitles():
    from app.services.llm import llm_service

    foreign_chunks = [
        {
            "text": "La combinación está escondida en el marco de la pintura.",
            "start_time": 6310.0,
            "end_time": 6380.0,
            "start_time_ms": 6310000,
            "end_time_ms": 6380000,
            "item_count": 1
        }
    ]

    # Test translating chunk
    with patch.object(
        llm_service,
        "translate_text_to_english",
        return_value="The combination is hidden in the painting's frame."
    ):
        translated = await llm_service.translate_chunks_to_english(foreign_chunks, source_language="spa")
        assert len(translated) == 1
        assert translated[0]["text"] == "The combination is hidden in the painting's frame."
        assert translated[0]["start_time"] == 6310.0
        assert translated[0]["end_time"] == 6380.0


