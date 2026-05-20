"""Typer-based CLI entry point.

Commands:
  insurance-intel init-db        — apply migrations/001_initial.sql
  insurance-intel run             — full sweep (Nimble + LLM + persist + digest + Slack + git)
  insurance-intel dry-run [N]     — sweep but skip Slack/git, optionally limit to first N sources
  insurance-intel test-source S   — run only one source, no Slack/git
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psycopg
import typer
from rich.console import Console
from rich.logging import RichHandler

from insurance_intel.config import settings
from insurance_intel.digest import render_markdown_report
from insurance_intel.notify import post_digest
from insurance_intel.persist import events_for_run
from insurance_intel.sources import SOURCES
from insurance_intel.sweep import run_sweep

app = typer.Typer(help="DACH Versicherungsmakler M&A signal loop.")
console = Console()


def _configure_logging() -> None:
    handlers: list[logging.Handler] = [RichHandler(console=console, rich_tracebacks=True)]
    if settings.log_file:
        settings.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(settings.log_file))
    logging.basicConfig(
        level=settings.log_level,
        handlers=handlers,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )


@app.command(name="init-db")
def init_db() -> None:
    """Apply migrations/001_initial.sql against the configured Postgres."""
    _configure_logging()
    migration = settings.repo_root / "migrations" / "001_initial.sql"
    sql = migration.read_text(encoding="utf-8")
    with psycopg.connect(settings.postgres_dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()
    console.print(f"[green]Applied {migration}[/green]")


@app.command(name="run")
def run_cmd(
    skip_notify: bool = typer.Option(False, "--skip-notify"),
    skip_git: bool = typer.Option(False, "--skip-git"),
) -> None:
    """Full weekly sweep."""
    _configure_logging()
    started_at = datetime.utcnow()
    summary = run_sweep()
    events = events_for_run(summary["run_id"])

    week_label = f"{started_at.isocalendar().year}-W{started_at.isocalendar().week:02d}"
    report = render_markdown_report(
        run_id=summary["run_id"],
        run_started_at=started_at,
        events=events,
        summary=summary,
    )

    report_dir = settings.repo_root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{week_label}.md"
    report_path.write_text(report, encoding="utf-8")
    console.print(f"[green]Wrote {report_path}[/green]")

    if not skip_notify:
        if post_digest(week_label=week_label, events=events):
            console.print("[green]ntfy digest sent[/green]")
        else:
            console.print("[yellow]ntfy digest failed (logged)[/yellow]")

    if not skip_git and settings.git_autopush:
        _git_commit_and_push(week_label=week_label, summary=summary)


@app.command(name="dry-run")
def dry_run() -> None:
    """Run sweep without notification and without git push."""
    run_cmd(skip_notify=True, skip_git=True)


@app.command(name="test-source")
def test_source(source_name: str) -> None:
    """Run a single source through the pipeline without Slack/git."""
    _configure_logging()
    matched = [s for s in SOURCES if s.name == source_name]
    if not matched:
        console.print(f"[red]No source named {source_name!r}[/red]")
        console.print(f"Available: {', '.join(s.name for s in SOURCES)}")
        raise typer.Exit(1)
    # Monkey-patch SOURCES to single source for this run
    import insurance_intel.sweep as sweep_mod
    sweep_mod.SOURCES = matched  # type: ignore[attr-defined]
    summary = run_sweep()
    console.print(summary)


def _git_commit_and_push(*, week_label: str, summary: dict) -> None:
    repo = settings.git_repo_dir
    try:
        subprocess.run(["git", "-C", str(repo), "add", "reports/"], check=True)
        msg = (
            f"weekly run {week_label}: "
            f"{summary['events_added']} events, "
            f"{summary['sources_failed']}/{summary['sources_attempted']} sources failed"
        )
        subprocess.run(["git", "-C", str(repo), "commit", "-m", msg], check=False)
        subprocess.run(["git", "-C", str(repo), "push"], check=False)
        console.print(f"[green]git commit + push: {msg}[/green]")
    except subprocess.CalledProcessError as exc:
        console.print(f"[yellow]git step failed: {exc}[/yellow]")


if __name__ == "__main__":
    app()
