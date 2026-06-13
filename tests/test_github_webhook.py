import hashlib
import hmac
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.github_webhook import handle_github_webhook, verify_signature


def _sign(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_verify_signature_ok():
    secret = "test-secret"
    body = b'{"ok":true}'
    assert verify_signature(body, _sign(body, secret), secret)


def test_verify_signature_fail():
    assert not verify_signature(b"{}", "sha256=bad", "secret")


def test_workflow_failure_notifies(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_ENABLED", "1")
    notified = []

    monkeypatch.setattr(
        "services.github_webhook._notify_telegram",
        lambda msg: notified.append(msg) or True,
    )
    payload = {
        "action": "completed",
        "repository": {"full_name": "user/repo"},
        "workflow_run": {
            "conclusion": "failure",
            "name": "test",
            "head_branch": "main",
            "html_url": "https://github.com/user/repo/actions/1",
            "actor": {"login": "dev"},
        },
    }
    result = handle_github_webhook("workflow_run", payload)
    assert result["notified"] is True
    assert notified and "user/repo" in notified[0]


def test_workflow_success_skips(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_ENABLED", "1")
    payload = {
        "action": "completed",
        "workflow_run": {"conclusion": "success"},
    }
    result = handle_github_webhook("workflow_run", payload)
    assert result["notified"] is False
