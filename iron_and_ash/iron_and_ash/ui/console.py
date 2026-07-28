"""Terminal rendering layer.

Uses ``rich`` when available for colour and layout, but degrades gracefully to
plain ``print``/``input`` so the game always runs, even with no dependencies
installed. Every other module talks to the terminal through this single
interface so the rest of the codebase never imports ``rich`` directly.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence

try:  # pragma: no cover - exercised implicitly depending on environment
    from rich.console import Console as _RichConsole
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.prompt import Prompt, IntPrompt, Confirm
    _HAS_RICH = True
except Exception:  # pragma: no cover
    _HAS_RICH = False


class UI:
    """A thin facade over the terminal.

    The methods here are intentionally small and content-agnostic; game logic
    decides *what* to say, this class only decides *how* it is drawn.
    """

    def __init__(self, use_color: bool = True) -> None:
        self._rich = _HAS_RICH and use_color
        self._console = _RichConsole() if self._rich else None

    # -- output ---------------------------------------------------------------
    def print(self, text: str = "", style: Optional[str] = None) -> None:
        if self._rich:
            self._console.print(text, style=style)
        else:
            print(_strip_markup(text))

    def rule(self, title: str = "") -> None:
        if self._rich:
            self._console.rule(title)
        else:
            line = "-" * 60
            print(f"\n{line}\n{title}\n{line}" if title else line)

    def panel(self, body: str, title: str = "", style: str = "cyan") -> None:
        if self._rich:
            self._console.print(Panel(body, title=title, border_style=style, expand=True))
        else:
            self.rule(title)
            print(_strip_markup(body))
            print("-" * 60)

    def narrate(self, text: str) -> None:
        """Story prose - a bit of breathing room and a distinct tone."""
        if self._rich:
            self._console.print(Text(text, style="italic"))
            self._console.print()
        else:
            print(f"\n{_strip_markup(text)}\n")

    def heading(self, text: str) -> None:
        if self._rich:
            self._console.print(f"[bold yellow]{text}[/bold yellow]")
        else:
            print(f"\n== {text} ==")

    def table(self, columns: Sequence[str], rows: Iterable[Sequence[str]], title: str = "") -> None:
        if self._rich:
            t = Table(title=title or None, expand=False)
            for col in columns:
                t.add_column(col)
            for row in rows:
                t.add_row(*[str(c) for c in row])
            self._console.print(t)
        else:
            if title:
                self.heading(title)
            widths = [len(c) for c in columns]
            rows = list(rows)
            for row in rows:
                for i, cell in enumerate(row):
                    widths[i] = max(widths[i], len(str(cell)))
            header = "  ".join(c.ljust(widths[i]) for i, c in enumerate(columns))
            print(header)
            print("  ".join("-" * w for w in widths))
            for row in rows:
                print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))

    # -- input ----------------------------------------------------------------
    def ask(self, prompt: str, default: Optional[str] = None,
            choices: Optional[Sequence[str]] = None) -> str:
        if self._rich:
            return Prompt.ask(prompt, default=default, choices=list(choices) if choices else None)
        suffix = f" [{default}]" if default is not None else ""
        while True:
            raw = input(f"{_strip_markup(prompt)}{suffix}: ").strip()
            if not raw and default is not None:
                return default
            if choices and raw not in choices:
                print(f"  choose one of: {', '.join(choices)}")
                continue
            if raw:
                return raw

    def ask_int(self, prompt: str, default: Optional[int] = None,
                minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
        while True:
            if self._rich:
                value = IntPrompt.ask(prompt, default=default)
            else:
                suffix = f" [{default}]" if default is not None else ""
                raw = input(f"{_strip_markup(prompt)}{suffix}: ").strip()
                if not raw and default is not None:
                    value = default
                else:
                    try:
                        value = int(raw)
                    except ValueError:
                        print("  enter a number.")
                        continue
            if minimum is not None and value < minimum:
                self.print(f"  must be at least {minimum}.")
                continue
            if maximum is not None and value > maximum:
                self.print(f"  must be at most {maximum}.")
                continue
            return value

    def confirm(self, prompt: str, default: bool = False) -> bool:
        if self._rich:
            return Confirm.ask(prompt, default=default)
        suffix = "Y/n" if default else "y/N"
        raw = input(f"{_strip_markup(prompt)} [{suffix}]: ").strip().lower()
        if not raw:
            return default
        return raw in ("y", "yes")

    def menu(self, title: str, options: Sequence[str], allow_back: bool = False) -> int:
        """Render a numbered menu and return the chosen index (0-based).

        Returns -1 if ``allow_back`` and the user chooses the back option.
        """
        self.heading(title)
        for i, opt in enumerate(options, 1):
            self.print(f"  [bold]{i}[/bold]. {opt}")
        if allow_back:
            self.print("  [bold]0[/bold]. Back")
        while True:
            lo = 0 if allow_back else 1
            choice = self.ask_int("Choose", minimum=lo, maximum=len(options))
            if choice == 0 and allow_back:
                return -1
            if 1 <= choice <= len(options):
                return choice - 1


def _strip_markup(text: str) -> str:
    """Remove rich-style ``[tag]`` markup for the plain-text fallback."""
    import re
    return re.sub(r"\[/?[a-zA-Z0-9 _#=]*\]", "", text)
