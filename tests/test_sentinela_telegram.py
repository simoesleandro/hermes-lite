import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.sentinela_telegram import (
    build_alerts_keyboard,
    cache_key,
    format_alerts_message,
    get_cached_alert,
    load_alerts,
)


def test_build_alerts_keyboard():
    alerts = [{"fornecedor": "Empresa X", "tipo": "duplicidade", "severidade": "alta"}]
    kb = build_alerts_keyboard(alerts)
    assert kb is not None
    assert kb["inline_keyboard"][0][0]["callback_data"] == "inv:0"
    assert kb["inline_keyboard"][0][1]["callback_data"] == "par:0"


def test_alert_cache(monkeypatch):
    from services import sentinela_telegram as st

    st._alert_cache.clear()
    monkeypatch.setattr(
        st,
        "SentinelaClient",
        lambda: type("C", (), {"get_alertas": lambda self, **kw: [{"fornecedor": "ACME"}]})(),
    )
    alerts = load_alerts(12345)
    assert len(alerts) == 1
    assert get_cached_alert(12345, 0)["fornecedor"] == "ACME"
    assert cache_key(12345) == "12345"


def test_format_alerts_message_empty():
    msg = format_alerts_message([], {"alertas_abertos": 0})
    assert "Nenhum alerta" in msg
