"""Tool to display support coordinates from storage in Table view."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DisplaySupportCoordinatesArgs(BaseModel):
    """Arguments for displaying support coordinates in table."""

    auto_show: bool = Field(
        default=True,
        description="Automatically show the Table view after generating the table.",
    )


async def display_support_coordinates_table_func(ctx: Any, args: str) -> str:
    """
    Display support node coordinates from Viktor Storage in Table view.

    Reads from "model_support_coordinates" storage (created by get_support_coordinates tool)
    and transforms it into a table with columns: Joint, X, Y, Z, U1, U2, U3, R1, R2, R3.
    """
    try:
        import viktor as vkt
    except ImportError as e:
        return f"Error importing Viktor: {e}"

    # Parse arguments
    payload = DisplaySupportCoordinatesArgs.model_validate_json(args)

    try:
        # Read support coordinates from storage
        stored_file = vkt.Storage().get("model_support_coordinates", scope="entity")
        if not stored_file:
            return (
                "No support coordinates found in storage. "
                "Please run 'get_support_coordinates' tool first to extract data from SAP2000."
            )

        supports_json = stored_file.getvalue_binary().decode("utf-8")
        supports = json.loads(supports_json)

        if not supports or len(supports) == 0:
            return "Support coordinates data is empty. Please extract data from SAP2000 first."

        # Build table data
        column_headers = [
            "Joint",
            "X (m)",
            "Y (m)",
            "Z (m)",
            "U1",
            "U2",
            "U3",
            "R1",
            "R2",
            "R3",
        ]

        data = []
        for s in supports:
            restraint = s.get("Restraint", {})
            row = [
                str(s.get("Joint", "")),
                round(float(s.get("X", 0.0)), 3),
                round(float(s.get("Y", 0.0)), 3),
                round(float(s.get("Z", 0.0)), 3),
                int(restraint.get("U1", 0)),
                int(restraint.get("U2", 0)),
                int(restraint.get("U3", 0)),
                int(restraint.get("R1", 0)),
                int(restraint.get("R2", 0)),
                int(restraint.get("R3", 0)),
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

        logger.info(f"Displayed {len(data)} support nodes in table view")

        return (
            f"Displayed {len(data)} support nodes in Table view. "
            f"Columns: Joint, X (m), Y (m), Z (m), U1, U2, U3, R1, R2, R3. "
            f"Restraints: 0=free, 1=restrained."
        )

    except json.JSONDecodeError as e:
        logger.exception("Failed to parse support coordinates JSON")
        return f"Error parsing support coordinates data: {e}"

    except Exception as e:
        logger.exception("Unexpected error in display_support_coordinates_table_func")
        return f"Unexpected error: {type(e).__name__}: {e}"


def display_support_coordinates_table_tool() -> Any:
    """Create the function tool for displaying support coordinates in table view."""
    from agents import FunctionTool

    return FunctionTool(
        name="display_support_coordinates_table",
        description=(
            "Display support node coordinates in Table view. "
            "Reads data from Viktor Storage (key: 'model_support_coordinates') that was previously "
            "extracted using the 'get_support_coordinates' tool. "
            "Shows a table with columns: Joint, X (m), Y (m), Z (m), U1, U2, U3, R1, R2, R3. "
            "Restraints are shown as 0=free, 1=restrained. "
            "The table is automatically displayed in the Table view panel (unless auto_show=False). "
            "IMPORTANT: Must run 'get_support_coordinates' tool first to extract data from SAP2000."
        ),
        params_json_schema=DisplaySupportCoordinatesArgs.model_json_schema(),
        on_invoke_tool=display_support_coordinates_table_func,
    )
