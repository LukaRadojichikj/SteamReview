# main.py
import json
import hashlib
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from steam import fetch_reviews
from llm import summarise

app = typer.Typer(add_completion=False)
console = Console()


def _print_table(game: str, snapshots: list[dict]) -> None:
    table = Table(
        title=f"Steam Snapshots for {game}",
        expand=True,
        box=box.SIMPLE_HEAVY,
    )
    table.add_column("Rec?", no_wrap=True, ratio=1)             # NEW
    table.add_column("Sentiment", style="bold", no_wrap=True, ratio=1)
    table.add_column("TL;DR", overflow="fold", ratio=4)
    table.add_column("Author", no_wrap=True, ratio=2)

    if not snapshots:
        console.print("[yellow]No reviews found.[/yellow]")
        return

    for s in snapshots:
        if "error" in s:
            table.add_row("⚠️", "error", s["error"], s.get("author", "?"))  # NEW first cell
        else:
            rec = "✅" if s.get("recommended") else "❌"                     # NEW
            table.add_row(
                rec,                                                        # NEW first cell
                s.get("sentiment", "?"),
                s.get("tldr", ""),
                s.get("author", "?"),
            )
    console.print(table)



def _hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _load_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@app.command()
def run(
    game: str = typer.Argument(..., help="Exact (or fuzzy) Steam game title"),
    count: int = typer.Option(3, min=1, max=20, help="Number of reviews to fetch"),
    fmt: str = typer.Option("table", "--format", case_sensitive=False, help="Output: table|json"),
    out: Optional[str] = typer.Option(None, help="Save snapshots to a JSON file"),
    fuzzy: bool = typer.Option(False, help="Enable fuzzy title matching"),
    cache_file: Path = typer.Option(Path(".cache/llm_cache.json"), help="Path to LLM cache file"),
    no_cache: bool = typer.Option(False, help="Disable LLM cache"),
    debug: bool = typer.Option(False, help="Print raw reviews and Gemini outputs for debugging"),
):
    """Fetch Steam reviews and summarise them with Gemini into snapshots (with optional caching)."""
    try:
        reviews = fetch_reviews(game, count=count, fuzzy=fuzzy)
        if debug:
            for r in reviews:
                console.print(f"[cyan]Raw review ({r['author']}):[/cyan] {r['text']}\n")
    except Exception as e:
        console.print(f"[red]Failed to fetch reviews:[/red] {e}")
        raise typer.Exit(code=1)

    cache = {} if no_cache else _load_cache(cache_file)
    snapshots: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=False,  # set True when you're done debugging
        console=console,
    ) as progress:
        task = progress.add_task("Summarising reviews...", total=len(reviews))
        for rev in reviews:
            key = _hash_text(rev["text"])
            try:
                loaded_from_cache = False
                if not no_cache and key in cache:
                    s = cache[key]
                    loaded_from_cache = True
                else:
                    s = summarise(rev["text"])  # summarise decides when to re-ask; no trimming here
                    if not no_cache:
                        cache[key] = s

                if debug:
                    from pprint import pformat
                    src = "[cache]" if loaded_from_cache else "[llm]"
                    progress.console.print(
                        f"[magenta]Gemini output {src} for {rev['author']}:[/magenta]\n"
                        + pformat(s, width=100)
                    )

                s["author"] = rev["author"]
                s["recommended"] = rev.get("recommended")   # NEW
                snapshots.append(s)
            except Exception as e:
                snapshots.append({"error": str(e), "author": rev["author"]})
            finally:
                progress.advance(task)

    if not no_cache:
        _save_cache(cache_file, cache)

    if fmt.lower() == "json":
        console.print(json.dumps(snapshots, indent=2, ensure_ascii=False))
    else:
        _print_table(game, snapshots)

    if out:
        Path(out).write_text(json.dumps(snapshots, indent=2, ensure_ascii=False), encoding="utf-8")
        console.print(f"[green]Saved to {out}[/green]")


if __name__ == "__main__":
    app()
