"""Interactive TUI for pantry item selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

if TYPE_CHECKING:
    from .planner import ConsolidatedIngredient


@dataclass
class PantryCheckResult:
    """Result from the pantry check TUI."""

    confirmed: bool
    excluded_items: list[str] = field(default_factory=list)
    included_items: list[str] = field(default_factory=list)


class PantryCheckScreen(App[PantryCheckResult]):
    """Interactive screen for selecting pantry items to exclude."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
        padding: 1;
    }

    #header-info {
        height: auto;
        padding: 1;
        background: $primary-background;
        color: $text;
    }

    #header-title {
        text-style: bold;
        padding-bottom: 1;
    }

    #header-desc {
        color: $text-muted;
    }

    #items-table {
        height: 1fr;
        margin: 1 0;
    }

    #summary {
        height: 3;
        padding: 0 1;
        background: $surface-darken-1;
        content-align: center middle;
    }

    #button-bar {
        height: 3;
        align: center middle;
        padding: 0 1;
    }

    #button-bar Button {
        margin: 0 1;
    }

    .selected-cell {
        color: $success;
    }

    .unselected-cell {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_item", "Toggle"),
        Binding("a", "select_all", "Select All"),
        Binding("n", "select_none", "Select None"),
        Binding("enter", "confirm", "Confirm"),
        Binding("q", "quit_cancel", "Cancel"),
        Binding("escape", "quit_cancel", "Cancel"),
    ]

    def __init__(
        self,
        pantry_candidates: list[ConsolidatedIngredient],
        title: str | None = None,
    ) -> None:
        super().__init__()
        self.candidates = list(pantry_candidates)
        self.screen_title = title or "Pantry Check"
        # Start with all items selected (user has them at home by default)
        self.selected: set[int] = set(range(len(pantry_candidates)))

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            with Vertical(id="header-info"):
                yield Label("Do you already have these items at home?", id="header-title")
                yield Label(
                    "Selected items will be excluded from your shopping list.",
                    id="header-desc",
                )
            table = DataTable(id="items-table")
            table.cursor_type = "row"
            table.add_columns("", "Item", "Quantity")
            yield table
            yield Static(self._get_summary(), id="summary")
            with Horizontal(id="button-bar"):
                yield Button("Confirm (enter)", variant="success", id="btn-confirm")
                yield Button("Cancel (q)", variant="error", id="btn-cancel")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.screen_title
        self._refresh_table()

    def _get_summary(self) -> str:
        excluded = len(self.selected)
        included = len(self.candidates) - excluded
        return f"Excluding: {excluded} | Buying: {included}"

    def _refresh_table(self) -> None:
        table = self.query_one("#items-table", DataTable)
        table.clear()

        for i, candidate in enumerate(self.candidates):
            checkbox = "[x]" if i in self.selected else "[ ]"
            qty_str = ""
            if candidate.total_quantity is not None:
                qty = candidate.total_quantity
                if qty == int(qty):
                    qty_str = str(int(qty))
                else:
                    qty_str = f"{qty:.2f}".rstrip("0").rstrip(".")
                if candidate.unit:
                    qty_str += f" {candidate.unit}"
            table.add_row(checkbox, candidate.name, qty_str)

        # Update summary
        summary = self.query_one("#summary", Static)
        summary.update(self._get_summary())

    def action_toggle_item(self) -> None:
        table = self.query_one("#items-table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.candidates):
            row_idx = table.cursor_row
            if row_idx in self.selected:
                self.selected.discard(row_idx)
            else:
                self.selected.add(row_idx)
            self._refresh_table()
            # Keep cursor on same row
            table.move_cursor(row=row_idx)

    def action_select_all(self) -> None:
        self.selected = set(range(len(self.candidates)))
        self._refresh_table()

    def action_select_none(self) -> None:
        self.selected.clear()
        self._refresh_table()

    def action_confirm(self) -> None:
        excluded = [self.candidates[i].name for i in sorted(self.selected)]
        included = [
            self.candidates[i].name for i in range(len(self.candidates)) if i not in self.selected
        ]
        self.exit(
            PantryCheckResult(confirmed=True, excluded_items=excluded, included_items=included)
        )

    def action_quit_cancel(self) -> None:
        self.exit(PantryCheckResult(confirmed=False))

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Toggle selection when row is double-clicked or Enter pressed on row."""
        self.action_toggle_item()

    @on(Button.Pressed, "#btn-confirm")
    def on_confirm_button(self) -> None:
        self.action_confirm()

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel_button(self) -> None:
        self.action_quit_cancel()


def interactive_pantry_check(
    pantry_candidates: list[ConsolidatedIngredient],
    title: str | None = None,
) -> PantryCheckResult:
    """
    Launch interactive TUI for pantry item selection.

    Args:
        pantry_candidates: List of ingredients identified as potential pantry items
        title: Optional title for the screen

    Returns:
        PantryCheckResult with confirmed status and items to exclude/include
    """
    if not pantry_candidates:
        return PantryCheckResult(confirmed=True)

    app = PantryCheckScreen(pantry_candidates, title)
    result = app.run()

    # Handle case where app exits without explicit result
    if result is None:
        return PantryCheckResult(confirmed=False)
    return result


def simple_pantry_prompt(
    pantry_candidates: list[ConsolidatedIngredient],
) -> PantryCheckResult:
    """
    Simple CLI prompt for pantry item selection (non-TUI fallback).

    Args:
        pantry_candidates: List of ingredients identified as potential pantry items

    Returns:
        PantryCheckResult with items to exclude
    """
    import click

    if not pantry_candidates:
        return PantryCheckResult(confirmed=True)

    click.echo()
    click.echo("=" * 50)
    click.echo("PANTRY CHECK")
    click.echo("=" * 50)
    click.echo("These items are commonly found in household pantries.")
    click.echo("Enter the numbers of items you DON'T have (comma-separated),")
    click.echo("or press Enter to exclude all (you have them all).")
    click.echo()

    for i, candidate in enumerate(pantry_candidates, 1):
        qty_str = ""
        if candidate.total_quantity is not None:
            qty = candidate.total_quantity
            if qty == int(qty):
                qty_str = f" ({int(qty)}"
            else:
                qty_str = f" ({qty:.2f}".rstrip("0").rstrip(".")
            if candidate.unit:
                qty_str += f" {candidate.unit}"
            qty_str += ")"
        click.echo(f"  {i}. {candidate.name}{qty_str}")

    click.echo()
    response = click.prompt(
        "Items you need to buy (e.g., '1,3,5' or 'all' or Enter to skip all)",
        default="",
        show_default=False,
    )

    response = response.strip().lower()

    if response == "" or response == "none":
        # User has all items - exclude everything
        excluded = [c.name for c in pantry_candidates]
        return PantryCheckResult(confirmed=True, excluded_items=excluded, included_items=[])

    if response == "all":
        # User needs all items - include everything
        included = [c.name for c in pantry_candidates]
        return PantryCheckResult(confirmed=True, excluded_items=[], included_items=included)

    # Parse comma-separated numbers
    try:
        need_indices = {int(x.strip()) - 1 for x in response.split(",") if x.strip()}
        excluded = []
        included = []
        for i, candidate in enumerate(pantry_candidates):
            if i in need_indices:
                included.append(candidate.name)
            else:
                excluded.append(candidate.name)
        return PantryCheckResult(confirmed=True, excluded_items=excluded, included_items=included)
    except ValueError:
        click.echo("Invalid input. Including all items in shopping list.")
        included = [c.name for c in pantry_candidates]
        return PantryCheckResult(confirmed=True, excluded_items=[], included_items=included)
