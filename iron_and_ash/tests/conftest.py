"""Shared test fixtures, including a scripted UI that needs no real terminal."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# make the package importable when tests run from the repo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ScriptedUI:
    """A UI stand-in that answers prompts from pre-loaded queues.

    Feed it lists of answers keyed by prompt kind; the game code calls the same
    method names as the real :class:`UI`, so creation flows can run headless.
    """

    def __init__(self, *, menu=None, ask=None, ask_int=None, confirm=None):
        self.menu_answers = list(menu or [])
        self.ask_answers = list(ask or [])
        self.ask_int_answers = list(ask_int or [])
        self.confirm_answers = list(confirm or [])
        self.output = []

    # output sinks - just capture text
    def print(self, text="", style=None):
        self.output.append(str(text))

    def rule(self, title=""):
        self.output.append(f"--{title}--")

    def panel(self, body, title="", style="cyan"):
        self.output.append(f"[{title}] {body}")

    def narrate(self, text):
        self.output.append(text)

    def heading(self, text):
        self.output.append(text)

    def table(self, columns, rows, title=""):
        self.output.append(title)

    # inputs - pop from the scripted queues
    def menu(self, title, options, allow_back=False):
        return self.menu_answers.pop(0)

    def ask(self, prompt, default=None, choices=None):
        return self.ask_answers.pop(0) if self.ask_answers else (default or "")

    def ask_int(self, prompt, default=None, minimum=None, maximum=None):
        return self.ask_int_answers.pop(0) if self.ask_int_answers else (default or 0)

    def confirm(self, prompt, default=False):
        return self.confirm_answers.pop(0) if self.confirm_answers else default


@pytest.fixture
def scripted_ui():
    return ScriptedUI


@pytest.fixture
def save_home(tmp_path, monkeypatch):
    monkeypatch.setenv("IRON_AND_ASH_HOME", str(tmp_path))
    return tmp_path
