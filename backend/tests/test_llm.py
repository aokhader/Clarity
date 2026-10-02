from pathlib import Path

import pytest
from pydantic import BaseModel

from app.config import get_settings
from app.digest import llm


class _Out(BaseModel):
    value: int


def test_a_model_call_without_prices_is_refused(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("EXTRACT_MODEL", "test-model")
    for name in ("EXTRACT_PRICE_IN", "EXTRACT_PRICE_OUT"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    request = llm.ModelRequest(
        purpose="test",
        role="extract",
        prompt=llm.Prompt(name="test", version="1", text="Return a value."),
        user_text="input",
        output=_Out,
    )
    with pytest.raises(llm.ModelsNotConfigured, match="EXTRACT_PRICE_IN"):
        llm._send(request, None)
