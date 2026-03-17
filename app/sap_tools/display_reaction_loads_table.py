"""Tool to display reaction loads from storage in Table view."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DisplayReactionLoadsArgs(BaseModel):
    """Arguments for displaying reaction loads in table."""

    auto_show: bool = Field(
        default=True,
        description="Automatically show the Table view after generating the table.",
    )


async def display_reaction_loads_table_func(ctx: Any, args: str) -> str:
    """
    Display reaction loads from Viktor Storage in Table view.

    Reads from "model_reaction_loads" storage (created by get_reaction_loads tool)
    and transforms it into a flattened table showing all nodes × all load combinations.
    Columns: Node, Load Combo, F1, F2, F3, M1, M2, M3.
    """
    try:
        import viktor as vkt
    except ImportError as e:
        return f"Error importing Viktor: {e}"

    # Parse arguments
    payload = DisplayReactionLoadsArgs.model_validate_json(args)

    try:
        # Read reaction loads from storage
        stored_file = vkt.Storage().get("model_reaction_loads", scope="entity")
        if not stored_file:
            return (
                "No reaction loads found in storage. "
                "Please run 'get_reaction_loads' tool first to extract data from SAP2000."
            )

        reactions_json = stored_file.getvalue_binary().decode("utf-8")
        reactions = json.loads(reactions_json)

        if not reactions or len(reactions) == 0:
            return "Reaction loads data is empty. Please extract data from SAP2000 first."

        # Build table data - flatten nested structure
        column_headers = [
            "Node",
            "Load Combo",
            "F1 (kN)",
            "F2 (kN)",
            "F3 (kN)",
            "M1 (kN·m)",
            "M2 (kN·m)",
            "M3 (kN·m)",
        ]

        data = []
        for node_name, combos in reactions.items():
            for combo_name, reaction in combos.items():
                row = [
                    str(node_name),
                    str(combo_name),
                    round(float(reaction.get("F1", 0.0)), 2),
                    round(float(reaction.get("F2", 0.0)), 2),
                    round(float(reaction.get("F3", 0.0)), 2),
                    round(float(reaction.get("M1", 0.0)), 2),
                    round(float(reaction.get("M2", 0.0)), 2),
                    round(float(reaction.get("M3", 0.0)), 2),
                ]
                data.append(row)

        # Create TableTool structure
        from app.viktor_tools.table_tool import TableTool

        table_tool = TableTool(data=data, column_headers=column_headers)

        # Write to TableTool storage
        vkt.Storage().set(
            "TableTool",
            data=vkt.File.from_data(table_tool.model_dump_json()),
            scope="entity",
        )

        # Optionally show table
        if payload.auto_show:
            vkt.Storage().set(
                "show_table",
                data=vkt.File.from_data("show"),
                scope="entity",
            )

        num_nodes = len(reactions)
        num_combos = len(next(iter(reactions.values()))) if reactions else 0
        total_rows = len(data)

        logger.info(
            f"Displayed {total_rows} reaction load entries in table view "
            f"({num_nodes} nodes × {num_combos} combos)"
        )

        return (
            f"Displayed {total_rows} reaction load entries in Table view "
            f"({num_nodes} nodes × {num_combos} load combinations). "
            f"Columns: Node, Load Combo, F1 (kN), F2 (kN), F3 (kN), M1 (kN·m), M2 (kN·m), M3 (kN·m)."
        )

    except json.JSONDecodeError as e:
        logger.exception("Failed to parse reaction loads JSON")
        return f"Error parsing reaction loads data: {e}"

    except Exception as e:
        logger.exception("Unexpected error in display_reaction_loads_table_func")
        return f"Unexpected error: {type(e).__name__}: {e}"


def display_reaction_loads_table_tool() -> Any:
    """Create the function tool for displaying reaction loads in table view."""
    from agents import FunctionTool

    return FunctionTool(
        name="display_reaction_loads_table",
        description=(
            "Display reaction loads in Table view. "
            "Reads data from Viktor Storage (key: 'model_reaction_loads') that was previously "
            "extracted using the 'get_reaction_loads' tool. "
            "Shows a flattened table with all nodes and all load combinations: "
            "Node, Load Combo, F1 (kN), F2 (kN), F3 (kN), M1 (kN·m), M2 (kN·m), M3 (kN·m). "
            "Forces are in kN, moments are in kN·m. "
            "The table is automatically displayed in the Table view panel (unless auto_show=False). "
            "IMPORTANT: Must run 'get_reaction_loads' tool first to extract data from SAP2000."
        ),
        params_json_schema=DisplayReactionLoadsArgs.model_json_schema(),
        on_invoke_tool=display_reaction_loads_table_func,
    )
