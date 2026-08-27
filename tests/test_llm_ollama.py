from unittest.mock import MagicMock, patch

from jobflow.services.llm import LLMClient, _parse_json_content


def test_parse_json_strips_fences():
    raw = '```json\n{"fit_score": 85}\n```'
    assert _parse_json_content(raw) == {"fit_score": 85}


def test_parse_json_strips_thinking():
    raw = 'reasoning here{"fit_score": 90}'
    assert _parse_json_content(raw) == {"fit_score": 90}


@patch("jobflow.services.llm.get_settings")
def test_ollama_used_when_reachable(mock_settings):
    settings = MagicMock()
    settings.llm_provider = "ollama"
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_model = "qwen3:8b"
    settings.ollama_timeout = 30.0
    mock_settings.return_value = settings

    with patch.object(LLMClient, "_ollama_reachable", return_value=True):
        client = LLMClient()
        assert client.enabled is True
        assert client.provider == "ollama"


@patch("jobflow.services.llm.get_settings")
def test_fallback_when_ollama_down(mock_settings):
    settings = MagicMock()
    settings.llm_provider = "ollama"
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_model = "qwen3:8b"
    settings.ollama_timeout = 30.0
    mock_settings.return_value = settings

    with patch.object(LLMClient, "_ollama_reachable", return_value=False):
        client = LLMClient()
        assert client.enabled is False
        result = client.complete_json("sys", "user", {"fallback": True})
        assert result == {"fallback": True}
