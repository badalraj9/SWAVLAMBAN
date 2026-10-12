import sys
import threading
from urllib.parse import urlparse

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.table import Table

from debate_core import ROUND_TITLES, load_configs, run_debate, save_transcript

AGENT_COLORS = {
    "agent_1": "cyan",
    "agent_2": "magenta",
    "agent_3": "yellow",
    "agent_4": "blue",
}

BAR_WIDTH = 10


def provider_of(base_url: str) -> str:
    host = urlparse(base_url).netloc.lower()
    if "openrouter" in host:
        return "OpenRouter"
    if "groq" in host:
        return "Groq"
    if "nvidia" in host:
        return "NVIDIA"
    return host or base_url


class CliEvents:
    def __init__(self, labels: dict, console: Console):
        self.labels = labels
        self.console = console
        self.lock = threading.Lock()
        self.statuses: dict = {}
        self.results: dict = {}
        self.spinners: dict = {}
        self.live: Live | None = None

    def _status_table(self) -> Table:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Agent")
        table.add_column("Status")
        for agent_id in sorted(self.labels):
            status = self.statuses.get(agent_id, "waiting")
            if status == "calling":
                cell = Group(self.spinners[agent_id], " calling")
            elif status == "responded":
                cell = "[green]responded[/green]"
            elif status == "failed":
                cell = "[red]failed[/red]"
            else:
                cell = "[dim]waiting[/dim]"
            table.add_row(self.labels[agent_id], cell)
        return table

    def on_round_start(self, round_name: str, title: str) -> None:
        with self.lock:
            self.statuses = {a: "waiting" for a in self.labels}
            self.results = {}
            self.spinners = {a: Spinner("dots") for a in self.labels}
        self.console.rule(title)
        self.live = Live(self._status_table(), console=self.console, refresh_per_second=8)
        self.live.start()

    def on_agent_start(self, agent_id: str) -> None:
        with self.lock:
            self.statuses[agent_id] = "calling"
            self._refresh()

    def on_agent_response(self, agent_id: str, result: dict) -> None:
        with self.lock:
            self.statuses[agent_id] = "responded"
            self.results[agent_id] = result
            self._refresh()

    def on_agent_error(self, agent_id: str, error: str) -> None:
        with self.lock:
            self.statuses[agent_id] = "failed"
            self.results[agent_id] = {"position": "", "confidence": 0.0, "reasoning": error}
            self._refresh()

    def on_round_complete(self, round_name: str) -> None:
        if self.live is not None:
            self.live.stop()
            self.live = None
        for agent_id in sorted(self.labels):
            result = self.results.get(agent_id, {})
            color = AGENT_COLORS.get(agent_id, "white")
            if self.statuses.get(agent_id) == "failed":
                body = f"Failed: {result.get('reasoning', 'unknown error')}"
            else:
                body = (
                    f"Position: {result.get('position', '')}\n"
                    f"Confidence: {result.get('confidence', 0):.2f}\n"
                    f"{result.get('reasoning', '')}"
                )
            self.console.print(Panel(body, title=self.labels[agent_id], border_style=color))

    def _refresh(self) -> None:
        if self.live is not None:
            self.live.update(self._status_table())


def print_tally(console: Console, tally: dict, winner: str) -> None:
    console.rule("Tally")
    total = sum(tally.values())
    for position, weight in sorted(tally.items(), key=lambda kv: kv[1], reverse=True):
        pct = (weight / total * 100) if total else 0.0
        filled = round(pct / 100 * BAR_WIDTH)
        bar = "█" * filled + "░" * (BAR_WIDTH - filled)
        mark = " ← winner" if position == winner else ""
        console.print(f"{position}  {bar}  {pct:5.1f}%{mark}")


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        topic = sys.argv[1].strip()
    elif not sys.stdin.isatty():
        print('Usage: python debate.py "<topic>"', file=sys.stderr)
        sys.exit(2)
    else:
        try:
            topic = Prompt.ask("Debate topic").strip()
        except (EOFError, KeyboardInterrupt):
            print("", file=sys.stderr)
            print('Usage: python debate.py "<topic>"', file=sys.stderr)
            sys.exit(2)
        if not topic:
            print('Usage: python debate.py "<topic>"', file=sys.stderr)
            sys.exit(2)
    configs = load_configs()
    console = Console()
    labels = {
        f"agent_{c.slot}": f"{provider_of(c.base_url)} · {c.model}"
        for c in configs
    }
    events = CliEvents(labels, console)
    transcript = run_debate(topic, configs, events)
    print_tally(console, transcript["tally"], transcript["winner"])
    path = save_transcript(transcript)
    console.print(f"Transcript: {path}")


if __name__ == "__main__":
    main()
