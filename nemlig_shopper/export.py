"""Shopping list export in various formats."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .matcher import ProductMatch


def export_to_json(
    matches: list[ProductMatch],
    filepath: str | Path,
    *,
    recipe_title: str | None = None,
    include_alternatives: bool = False,
) -> None:
    """
    Export shopping list to JSON format.

    Args:
        matches: List of product matches
        filepath: Output file path
        recipe_title: Optional recipe title
        include_alternatives: Include alternative products
    """
    data: dict[str, Any] = {
        "exported_at": datetime.now().isoformat(),
        "recipe_title": recipe_title,
        "items": [],
        "summary": {
            "total_items": len(matches),
            "matched": sum(1 for m in matches if m.matched),
            "unmatched": sum(1 for m in matches if not m.matched),
        },
    }

    for match in matches:
        item: dict[str, Any] = {
            "ingredient": match.ingredient_name,
            "matched": match.matched,
            "quantity": match.quantity,
        }

        if match.matched and match.product:
            item["product"] = {
                "id": match.product_id,
                "name": match.product_name,
                "price": match.price,
                "unit_size": match.product.get("unit_size"),
            }

            if include_alternatives and match.alternatives:
                item["alternatives"] = [
                    {
                        "id": alt.get("id"),
                        "name": alt.get("name"),
                        "price": alt.get("price"),
                    }
                    for alt in match.alternatives
                ]

        data["items"].append(item)

    # Calculate total cost
    total = sum((m.price or 0) * m.quantity for m in matches if m.matched and m.price)
    data["summary"]["estimated_total"] = round(total, 2)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_to_markdown(
    matches: list[ProductMatch],
    filepath: str | Path,
    *,
    recipe_title: str | None = None,
    include_alternatives: bool = False,
) -> None:
    """
    Export shopping list to Markdown format.

    Args:
        matches: List of product matches
        filepath: Output file path
        recipe_title: Optional recipe title
        include_alternatives: Include alternative products
    """
    lines: list[str] = []

    # Header
    title = recipe_title or "Shopping List"
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    # Summary
    matched = sum(1 for m in matches if m.matched)
    unmatched = sum(1 for m in matches if not m.matched)
    total = sum((m.price or 0) * m.quantity for m in matches if m.matched and m.price)

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Items:** {len(matches)}")
    lines.append(f"- **Matched:** {matched}")
    lines.append(f"- **Unmatched:** {unmatched}")
    lines.append(f"- **Estimated Total:** {total:.2f} DKK")
    lines.append("")

    # Shopping list
    lines.append("## Items")
    lines.append("")

    for match in matches:
        if match.matched:
            price_str = f"{match.price:.2f} DKK" if match.price else "N/A"
            line_total = (match.price or 0) * match.quantity
            lines.append(
                f"- [x] **{match.ingredient_name}** → "
                f"{match.product_name} (x{match.quantity}) - {price_str}"
            )
            if match.quantity > 1 and match.price:
                lines.append(f"  - Subtotal: {line_total:.2f} DKK")

            if include_alternatives and match.alternatives:
                lines.append("  - Alternatives:")
                for alt in match.alternatives[:3]:
                    alt_name = alt.get("name", "Unknown")
                    alt_price = alt.get("price")
                    price_info = f" - {alt_price:.2f} DKK" if alt_price else ""
                    lines.append(f"    - {alt_name}{price_info}")
        else:
            lines.append(f"- [ ] **{match.ingredient_name}** → *No match found*")

    lines.append("")

    # Unmatched section if any
    unmatched_items = [m for m in matches if not m.matched]
    if unmatched_items:
        lines.append("## Unmatched Items")
        lines.append("")
        lines.append("These items need to be found manually:")
        lines.append("")
        for match in unmatched_items:
            lines.append(f"- {match.ingredient_name} (searched: '{match.search_query}')")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def export_to_pdf(
    matches: list[ProductMatch],
    filepath: str | Path,
    *,
    recipe_title: str | None = None,
) -> None:
    """
    Export shopping list to PDF format.

    Requires reportlab package.

    Args:
        matches: List of product matches
        filepath: Output file path
        recipe_title: Optional recipe title
    """
    try:
        from reportlab.lib import colors  # type: ignore[import-untyped]
        from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
        from reportlab.lib.styles import (  # type: ignore[import-untyped]
            ParagraphStyle,
            getSampleStyleSheet,
        )
        from reportlab.lib.units import cm  # type: ignore[import-untyped]
        from reportlab.platypus import (  # type: ignore[import-untyped]
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as e:
        raise ImportError("PDF export requires reportlab. Install with: uv add reportlab") from e

    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=20,
    )

    elements: list[Any] = []

    # Title
    title = recipe_title or "Shopping List"
    elements.append(Paragraph(title, title_style))
    elements.append(
        Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            subtitle_style,
        )
    )

    # Summary
    matched = sum(1 for m in matches if m.matched)
    unmatched = sum(1 for m in matches if not m.matched)
    total = sum((m.price or 0) * m.quantity for m in matches if m.matched and m.price)

    summary_data = [
        ["Items", str(len(matches))],
        ["Matched", str(matched)],
        ["Unmatched", str(unmatched)],
        ["Estimated Total", f"{total:.2f} DKK"],
    ]

    summary_table = Table(summary_data, colWidths=[4 * cm, 3 * cm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Shopping list table
    elements.append(Paragraph("Shopping List", styles["Heading2"]))
    elements.append(Spacer(1, 10))

    table_data = [["Ingredient", "Product", "Qty", "Price"]]

    for match in matches:
        if match.matched:
            price_str = f"{match.price:.2f}" if match.price else "N/A"
            table_data.append(
                [
                    match.ingredient_name,
                    match.product_name[:40] + "..."
                    if len(match.product_name) > 40
                    else match.product_name,
                    str(match.quantity),
                    price_str,
                ]
            )
        else:
            table_data.append([match.ingredient_name, "No match", "-", "-"])

    col_widths = [4 * cm, 7 * cm, 1.5 * cm, 2 * cm]
    main_table = Table(table_data, colWidths=col_widths)
    main_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 0), (3, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(main_table)

    doc.build(elements)


def export_shopping_list(
    matches: list[ProductMatch],
    filepath: str | Path,
    *,
    recipe_title: str | None = None,
    format: str | None = None,
    include_alternatives: bool = False,
) -> str:
    """
    Export shopping list to file.

    Format is auto-detected from file extension if not specified.

    Args:
        matches: List of product matches
        filepath: Output file path
        recipe_title: Optional recipe title
        format: Output format (json, md, pdf) - auto-detected if None
        include_alternatives: Include alternative products (json/md only)

    Returns:
        The format used for export
    """
    path = Path(filepath)

    # Auto-detect format from extension
    if format is None:
        ext = path.suffix.lower()
        format_map = {
            ".json": "json",
            ".md": "md",
            ".markdown": "md",
            ".pdf": "pdf",
        }
        format = format_map.get(ext, "md")

    if format == "json":
        export_to_json(
            matches,
            filepath,
            recipe_title=recipe_title,
            include_alternatives=include_alternatives,
        )
    elif format in ("md", "markdown"):
        export_to_markdown(
            matches,
            filepath,
            recipe_title=recipe_title,
            include_alternatives=include_alternatives,
        )
    elif format == "pdf":
        export_to_pdf(matches, filepath, recipe_title=recipe_title)
    else:
        raise ValueError(f"Unsupported format: {format}")

    return format
