"""
ProspectMind CLI — personalize B2B outreach at scale.

Usage:
    prospectmind run prospects.csv --provider openai
    prospectmind run prospects.csv --provider anthropic --product "Acme CRM" --value-prop "Reduces churn by 30%"
    prospectmind run prospects.csv --provider ollama --model llama3.1 --dry-run
    prospectmind sample  # generate a sample CSV to get started
"""

from __future__ import annotations

import asyncio
import csv
import os
import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from . import __version__
from .models import LLMProvider, PersonalizationResult, RunConfig
from .pipeline import load_prospects_from_csv, results_to_csv, run_pipeline

app = typer.Typer(
    name="prospectmind",
    help="AI-powered B2B outreach personalization engine",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

SAMPLE_CSV = """\
first_name,last_name,title,company,domain,email
Sarah,Chen,VP of Engineering,Acme Corp,acme.com,sarah@acme.com
James,Park,Head of Marketing,BetaStartup,betastartup.io,james@betastartup.io
Maya,Rodriguez,CTO,GrowthCo,growthco.com,maya@growthco.com
"""


@app.command()
def run(
    input_file: Path = typer.Argument(
        ...,
        help="CSV file with prospects (columns: first_name, last_name, title, company, domain, email)",
        exists=True,
        file_okay=True,
        readable=True,
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output CSV path (default: <input>_personalized.csv)",
    ),
    provider: LLMProvider = typer.Option(
        LLMProvider.OPENAI, "--provider", "-p",
        help="LLM provider to use",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model name (default: provider's recommended model)",
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key",
        help="API key (or set OPENAI_API_KEY / ANTHROPIC_API_KEY env var)",
        envvar=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
    ),
    ollama_url: str = typer.Option(
        "http://localhost:11434", "--ollama-url",
        help="Ollama server URL (only for --provider ollama)",
    ),
    concurrency: int = typer.Option(
        3, "--concurrency", "-c",
        help="Max parallel prospects to process (1-20)",
        min=1, max=20,
    ),
    product: Optional[str] = typer.Option(
        None, "--product",
        help="Your product name (improves value prop generation)",
    ),
    value_prop: Optional[str] = typer.Option(
        None, "--value-prop",
        help="Your core value proposition (improves personalization)",
    ),
    skip_scraping: bool = typer.Option(
        False, "--skip-scraping",
        help="Skip web scraping (faster, less personalized)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Scrape but skip LLM calls (useful for testing)",
    ),
    retries: int = typer.Option(
        3, "--retries",
        help="Max LLM retry attempts per prospect",
        min=0, max=10,
    ),
    timeout: int = typer.Option(
        30, "--timeout",
        help="Scraping timeout in seconds",
        min=5, max=120,
    ),
) -> None:
    """
    [bold green]Personalize B2B cold outreach at scale.[/bold green]

    Reads a CSV of prospects, scrapes company context, and generates
    personalized subject lines + email openers for each row.
    """
    # Determine output path
    if output is None:
        stem = input_file.stem
        output = input_file.parent / f"{stem}_personalized.csv"

    console.rule("[bold blue]ProspectMind[/bold blue]")
    console.print(f"  Input:     [cyan]{input_file}[/cyan]")
    console.print(f"  Output:    [cyan]{output}[/cyan]")
    console.print(f"  Provider:  [cyan]{provider.value}[/cyan]" + (f"/{model}" if model else ""))
    console.print(f"  Scraping:  [cyan]{'disabled' if skip_scraping else 'enabled'}[/cyan]")
    if product:
        console.print(f"  Product:   [cyan]{product}[/cyan]")
    if dry_run:
        console.print("  [yellow]DRY RUN — LLM calls skipped[/yellow]")
    console.print()

    # Load prospects
    try:
        prospects = load_prospects_from_csv(input_file)
    except Exception as e:
        console.print(f"[red]Error loading CSV: {e}[/red]")
        raise typer.Exit(1)

    if not prospects:
        console.print("[yellow]No valid prospects found in CSV.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[green]Loaded {len(prospects)} prospect(s)[/green]")

    config = RunConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        ollama_base_url=ollama_url,
        concurrency=concurrency,
        max_retries=retries,
        timeout_seconds=timeout,
        dry_run=dry_run,
        skip_scraping=skip_scraping,
        your_product=product,
        your_value_prop=value_prop,
    )

    results: List[PersonalizationResult] = []
    errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Personalizing...", total=len(prospects))

        async def collect():
            nonlocal errors
            async for result in run_pipeline(prospects, config):
                results.append(result)
                if result.error:
                    errors += 1
                name = result.prospect.full_name
                score = result.personalization_score
                status = f"[red]ERR[/red]" if result.error else f"[green]{score}[/green]"
                progress.update(task_id, advance=1, description=f"{name} ({status})")

        try:
            asyncio.run(collect())
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Saving partial results...[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Pipeline error: {e}[/red]")
            if not results:
                raise typer.Exit(1)

    # Write output
    csv_content = results_to_csv(results)
    output.write_text(csv_content, encoding="utf-8")

    # Summary table
    console.print()
    _print_summary(results, errors, output)


def _print_summary(
    results: List[PersonalizationResult], errors: int, output: Path
) -> None:
    table = Table(title="Results Summary", show_header=True)
    table.add_column("Prospect", style="cyan")
    table.add_column("Company")
    table.add_column("Score", justify="right")
    table.add_column("Best Subject Line", style="green")
    table.add_column("Status")

    for r in results[:20]:  # show first 20
        status = "[red]Error[/red]" if r.error else "[green]OK[/green]"
        subject = (r.subject_lines[0][:50] + "…") if r.subject_lines and len(r.subject_lines[0]) > 50 else (r.subject_lines[0] if r.subject_lines else "—")
        table.add_row(
            r.prospect.full_name,
            r.prospect.company,
            str(r.personalization_score),
            subject if not r.error else r.error[:40],
            status,
        )

    if len(results) > 20:
        table.add_row(f"... and {len(results) - 20} more", "", "", "", "")

    console.print(table)
    console.print()
    console.print(
        f"[bold green]✓ Done![/bold green] "
        f"{len(results) - errors}/{len(results)} succeeded. "
        f"{errors} error(s). "
        f"Output saved to [cyan]{output}[/cyan]"
    )


@app.command()
def sample(
    output: Path = typer.Option(
        Path("prospects_sample.csv"),
        "--output", "-o",
        help="Where to write the sample CSV",
    ),
) -> None:
    """Generate a sample input CSV to help you get started."""
    output.write_text(SAMPLE_CSV, encoding="utf-8")
    console.print(f"[green]Sample CSV written to {output}[/green]")
    console.print()
    console.print("Next steps:")
    console.print(
        f"  [cyan]prospectmind run {output} --provider openai --product 'Your Product'[/cyan]"
    )


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
    ctx: typer.Context = typer.Context,
) -> None:
    """ProspectMind — AI-powered B2B outreach personalization."""
    if version:
        console.print(f"ProspectMind v{__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


def entry_point() -> None:
    app()


if __name__ == "__main__":
    entry_point()
