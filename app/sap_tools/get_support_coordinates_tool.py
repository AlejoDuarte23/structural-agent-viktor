"""Tool to extract support node coordinates from SAP2000 and store in Viktor Storage."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GetSupportCoordinatesArgs(BaseModel):
    """Arguments for getting support coordinates from SAP2000."""

    run_analysis: bool = Field(
        default=True,
        description="Whether to run analysis before extracting data. Set to False if analysis is already complete.",
    )


async def get_support_coordinates_func(ctx: Any, args: str) -> str:
    """
    Extract support node coordinates from active SAP2000 model and store in Viktor Storage.

    This tool connects to SAP2000, extracts all support nodes with their:
    - X, Y, Z coordinates
    - Restraint conditions (U1, U2, U3, R1, R2, R3)

    The data is stored in Viktor Storage with key "model_support_coordinates" for later use.
    """
    try:
        import viktor as vkt
        from app.sap_tools.core import (
            Sap2000Session,
            run_analysis,
            get_support_nodes,
        )
    except ImportError as e:
        return f"Error importing required modules: {e}. Ensure pywin32 is installed and SAP2000 is available."

    # Parse arguments
    payload = GetSupportCoordinatesArgs.model_validate_json(args)

    try:
        # Connect to SAP2000 and extract support coordinates
        with Sap2000Session() as sap:
            if payload.run_analysis:
                logger.info("Running SAP2000 analysis...")
                run_analysis(sap.SapModel)

            logger.info("Extracting support node coordinates...")
            supports = get_support_nodes(sap.SapModel)

        # Store in Viktor Storage
        data_json = json.dumps(supports, indent=2)
        vkt.Storage().set(
            "model_support_coordinates",
            data=vkt.File.from_data(data_json),
            scope="entity",
        )

        logger.info(f"Stored {len(supports)} support nodes in Viktor Storage")

        # Return concise summary (not full data)
        node_names = [s["Joint"] for s in supports]
        summary = {
            "status": "success",
            "num_support_nodes": len(supports),
            "node_names": node_names[:10],  # Show first 10 only
            "total_nodes": len(node_names),
            "storage_key": "model_support_coordinates",
        }

        if len(node_names) > 10:
            summary["note"] = f"Showing first 10 of {len(node_names)} nodes"

        return (
            f"Successfully extracted {len(supports)} support nodes from SAP2000 model. "
            f"Nodes: {', '.join(node_names[:10])}{'...' if len(node_names) > 10 else ''}. "
            f"Data stored in Viktor Storage with key 'model_support_coordinates'."
        )

    except RuntimeError as e:
        error_msg = str(e)
        if "Could not attach" in error_msg:
            return (
                "Failed to connect to SAP2000. Please ensure:\n"
                "1. SAP2000 is running\n"
                "2. A model is open\n"
                "3. Go to Tools → Set as active instance for API\n"
                "4. SAP2000 and Python are running at the same admin level (both elevated or both normal)\n"
                f"Error: {error_msg}"
            )
        return f"Error extracting support coordinates: {error_msg}"

    except Exception as e:
        logger.exception("Unexpected error in get_support_coordinates_func")
        return f"Unexpected error: {type(e).__name__}: {e}"


def get_support_coordinates_tool() -> Any:
    """Create the function tool for extracting support coordinates from SAP2000."""
    from agents import FunctionTool

    return FunctionTool(
        name="get_support_coordinates",
        description=(
            "Extract support node coordinates from active SAP2000 model. "
            "Connects to SAP2000 via COM interface and retrieves all support nodes with:\n"
            "- Joint name/ID\n"
            "- X, Y, Z coordinates (meters)\n"
            "- Restraint conditions (U1, U2, U3, R1, R2, R3 as 0=free, 1=restrained)\n"
            "The extracted data is automatically stored in Viktor Storage with key 'model_support_coordinates' "
            "for use by other tools (like footing design).\n"
            "IMPORTANT: SAP2000 must be running with a model open and set as active API instance "
            "(Tools → Set as active instance for API)."
        ),
        params_json_schema=GetSupportCoordinatesArgs.model_json_schema(),
        on_invoke_tool=get_support_coordinates_func,
    )
