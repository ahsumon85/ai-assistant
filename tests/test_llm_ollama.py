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
def test_groq_used_when_api_key_set(mock_settings):
    settings = MagicMock()
    settings.llm_provider = "groq"
    settings.groq_api_key = "gsk_test_key"
    settings.groq_model = "llama-3.3-70b-versatile"
    mock_settings.return_value = settings

    with patch("openai.OpenAI") as mock_openai:
        client = LLMClient()
        assert client.enabled is True
        assert client.provider == "groq"
        mock_openai.assert_called_once_with(
            api_key="gsk_test_key",
            base_url="https://api.groq.com/openai/v1",
        )


@patch("jobflow.services.llm.get_settings")
def test_fallback_when_ollama_down(mock_settings):
    settings = MagicMock()
    settings.llm_provider = "ollama"
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_model = "qwen3:8b"
    settings.ollama_timeout = 30.0
    settings.llm_max_input_chars = 8000
    mock_settings.return_value = settings

    with patch.object(LLMClient, "_ollama_reachable", return_value=False):
        client = LLMClient()
        assert client.enabled is False
        result = client.complete_json("sys", "user", {"fallback": True})
        assert result == {"fallback": True}


@patch("jobflow.services.llm.httpx.post")
@patch("jobflow.services.llm.get_settings")
def test_ollama_disables_thinking(mock_settings, mock_post):
    settings = MagicMock()
    settings.llm_provider = "ollama"
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_model = "qwen3:8b"
    settings.ollama_timeout = 30.0
    settings.ollama_think = False
    settings.ollama_num_predict_json = 512
    settings.ollama_num_predict_text = 1024
    settings.llm_max_input_chars = 8000
    mock_settings.return_value = settings
    mock_post.return_value.json.return_value = {"message": {"content": '{"ok": true}'}}
    mock_post.return_value.raise_for_status = MagicMock()

    with patch.object(LLMClient, "_ollama_reachable", return_value=True):
        client = LLMClient()
        client.complete_json("sys", "user", {"fallback": True})

    payload = mock_post.call_args.kwargs["json"]
    assert payload["think"] is False
    assert payload["format"] == "json"
