import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.git_tools import format_git_context, git_branch, git_status_short


def test_git_status_short():
    status = git_status_short()
    assert isinstance(status, str)
    assert status  # repo should have git status


def test_git_branch():
    branch = git_branch()
    assert branch in ("master", "main") or branch  # any branch name


def test_format_git_context():
    ctx = format_git_context()
    assert "GIT" in ctx
    assert "branch" in ctx.lower() or "##" in ctx
