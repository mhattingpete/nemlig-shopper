"""Interactive TUI for reviewing and editing product matches."""

from collections.abc import Callable
from dataclasses import dataclass

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from .matcher import ProductMatch, select_alternative


@dataclass
class ReviewResult:
    """Result from the interactive review."""

    confirmed: bool
    matches: list[ProductMatch]


class AlternativesModal(ModalScreen[int | None]):
    """Modal dialog to select an alternative product."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        match: ProductMatch,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name)
        self.match = match

    def compose(self) -> ComposeResult:
        with Vertical(id="alternatives-dialog"):
            yield Label(f"Alternatives for: {self.match.ingredient_name}", id="alt-title")
            yield Label(f"Current: {self.match.product_name}", id="alt-current")
            yield Static("", id="alt-spacer")

            if self.match.alternatives:
                table = DataTable(id="alt-table")
                table.cursor_type = "row"
                table.add_columns("#", "Product", "Price")
                for i, alt in enumerate(self.match.alternatives):
                    price = alt.get("price")
                    price_str = f"{price:.2f} DKK" if price else "N/A"
                    table.add_row(str(i + 1), alt.get("name", "Unknown")[:50], price_str)
                yield table
            else:
                yield Label("No alternatives available", id="no-alts")

            with Horizontal(id="alt-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")

    @on(DataTable.RowSelected)
    def on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Select the alternative when row is clicked or Enter pressed."""
        if event.cursor_row is not None:
            self.dismiss(event.cursor_row)

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ReviewScreen(App[ReviewResult]):
    """Interactive screen for reviewing product matches."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
        padding: 1;
    }

    #summary {
        height: 3;
        padding: 0 1;
        background: $primary-background;
        color: $text;
        content-align: center middle;
    }

    #matches-table {
        height: 1fr;
        margin: 1 0;
    }

    #button-bar {
        height: 3;
        align: center middle;
        padding: 0 1;
    }

    #button-bar Button {
        margin: 0 1;
    }

    #alternatives-dialog {
        width: 70;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    #alt-title {
        text-style: bold;
        padding-bottom: 1;
    }

    #alt-current {
        color: $text-muted;
        padding-bottom: 1;
    }

    #alt-spacer {
        height: 1;
    }

    #alt-table {
        height: auto;
        max-height: 15;
        margin-bottom: 1;
    }

    #no-alts {
        color: $warning;
        padding: 1;
    }

    #alt-buttons {
        height: 3;
        align: center middle;
    }

    .matched {
        color: $success;
    }

    .unmatched {
        color: $error;
    }
    """

    BINDINGS = [
        Binding("q", "quit_cancel", "Cancel"),
        Binding("enter", "show_alternatives", "Alternatives"),
        Binding("c", "confirm", "Confirm"),
        Binding("escape", "quit_cancel", "Cancel"),
    ]

    def __init__(
        self,
        matches: list[ProductMatch],
        recipe_title: str | None = None,
    ) -> None:
        super().__init__()
        self.matches = list(matches)  # Make a copy
        self.recipe_title = recipe_title or "Shopping List"
        self._confirmed = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            yield Static(self._get_summary(), id="summary")
            table = DataTable(id="matches-table")
            table.cursor_type = "row"
            table.add_columns("Ingredient", "Product", "Qty", "Price", "Status")
            yield table
            with Horizontal(id="button-bar"):
                yield Button("Confirm (c)", variant="success", id="btn-confirm")
                yield Button("Cancel (q)", variant="error", id="btn-cancel")
        yield Footer()

    def on_mount(self) -> None:
        self.title = self.recipe_title
        self._refresh_table()

    def _get_summary(self) -> str:
        matched = sum(1 for m in self.matches if m.matched)
        unmatched = len(self.matches) - matched
        total = sum((m.price or 0) * m.quantity for m in self.matches if m.matched)
        return f"Items: {len(self.matches)} | Matched: {matched} | Unmatched: {unmatched} | Total: {total:.2f} DKK"

    def _refresh_table(self) -> None:
        table = self.query_one("#matches-table", DataTable)
        table.clear()

        for match in self.matches:
            if match.matched and match.product:
                price = match.price
                price_str = f"{price:.2f}" if price else "N/A"
                status = "✓" if match.product.get("available", True) else "⚠ OOS"
                table.add_row(
                    match.ingredient_name[:25],
                    match.product_name[:35],
                    str(match.quantity),
                    price_str,
                    status,
                )
            else:
                table.add_row(
                    match.ingredient_name[:25],
                    "No match found",
                    "-",
                    "-",
                    "✗",
                )

        # Update summary
        summary = self.query_one("#summary", Static)
        summary.update(self._get_summary())

    def action_show_alternatives(self) -> None:
        table = self.query_one("#matches-table", DataTable)
        if table.cursor_row is not None and 0 <= table.cursor_row < len(self.matches):
            match = self.matches[table.cursor_row]
            if match.matched and match.alternatives:
                self.push_screen(
                    AlternativesModal(match),
                    callback=self._on_alternative_selected,
                )

    def _on_alternative_selected(self, index: int | None) -> None:
        if index is not None:
            table = self.query_one("#matches-table", DataTable)
            if table.cursor_row is not None:
                row_idx = table.cursor_row
                self.matches[row_idx] = select_alternative(self.matches[row_idx], index)
                self._refresh_table()

    def action_confirm(self) -> None:
        self._confirmed = True
        self.exit(ReviewResult(confirmed=True, matches=self.matches))

    def action_quit_cancel(self) -> None:
        self.exit(ReviewResult(confirmed=False, matches=self.matches))

    @on(Button.Pressed, "#btn-confirm")
    def on_confirm_button(self) -> None:
        self.action_confirm()

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel_button(self) -> None:
        self.action_quit_cancel()


def interactive_review(
    matches: list[ProductMatch],
    recipe_title: str | None = None,
) -> ReviewResult:
    """
    Launch interactive TUI for reviewing product matches.

    Args:
        matches: List of product matches to review
        recipe_title: Optional title for the review screen

    Returns:
        ReviewResult with confirmed status and potentially modified matches
    """
    app = ReviewScreen(matches, recipe_title)
    result = app.run()
    # Handle case where app exits without explicit result (e.g., crash)
    if result is None:
        return ReviewResult(confirmed=False, matches=matches)
    return result


def run_with_review(
    matches: list[ProductMatch],
    recipe_title: str | None = None,
    on_confirm: Callable[[list[ProductMatch]], None] | None = None,
) -> tuple[bool, list[ProductMatch]]:
    """
    Run interactive review and optionally execute callback on confirm.

    Args:
        matches: List of product matches to review
        recipe_title: Optional title for the review screen
        on_confirm: Callback to execute if user confirms

    Returns:
        Tuple of (confirmed, matches)
    """
    result = interactive_review(matches, recipe_title)

    if result.confirmed and on_confirm:
        on_confirm(result.matches)

    return result.confirmed, result.matches
