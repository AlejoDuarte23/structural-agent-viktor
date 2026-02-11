"""Tool to list available load combinations and cases from SAP2000."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GetLoadCombinationsArgs(BaseModel):
    """Arguments for getting load combinations from SAP2000."""

    include_cases: bool = Field(
        default=False,
        description="Whether to include load cases in addition to load combinations. Default is False (combos only).",
    )


async def get_load_combinations_func(ctx: Any, args: str) -> str:
    """
    List all available load combinations (and optionally cases) from SAP2000.

    This helps the agent see what load combinations are available before
    selecting which ones to use for footing design or reaction extraction.
    """
    try:
        from app.sap_tools.core import (
            Sap2000Session,
            get_all_load_combos,
            get_all_load_cases,
        )
    except ImportError as e:
        return f"Error importing required modules: {e}. Ensure pywin32 is installed and SAP2000 is available."

    # Parse arguments
    payload = GetLoadCombinationsArgs.model_validate_json(args)

    try:
        # Connect to SAP2000 and extract load combo names
        with Sap2000Session() as sap:
            logger.info("Extracting load combination names from SAP2000...")
            combos = get_all_load_combos(sap.SapModel)

            cases = []
            if payload.include_cases:
                logger.info("Extracting load case names from SAP2000...")
                cases = get_all_load_cases(sap.SapModel)

        # Build response
        result = {
            "load_combinations": combos,
            "num_combinations": len(combos),
        }

        if payload.include_cases:
            result["load_cases"] = cases
            result["num_cases"] = len(cases)

        logger.info(
            f"Found {len(combos)} load combinations"
            + (f" and {len(cases)} load cases" if payload.include_cases else "")
        )

        # Format user-friendly response
        response_parts = [
            f"Found {len(combos)} load combinations in SAP2000 model:",
            f"Load Combinations: {', '.join(combos)}",
        ]

        if payload.include_cases:
            response_parts.append(f"\nFound {len(cases)} load cases:")
            response_parts.append(f"Load Cases: {', '.join(cases)}")

        response_parts.append(f"\nDetails: {json.dumps(result, indent=2)}")

        return "\n".join(response_parts)

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
        return f"Error extracting load combinations: {error_msg}"

    except Exception as e:
        logger.exception("Unexpected error in get_load_combinations_func")
        return f"Unexpected error: {type(e).__name__}: {e}"


def get_load_combinations_tool() -> Any:
    """Create the function tool for listing load combinations from SAP2000."""
    from agents import FunctionTool

    return FunctionTool(
        name="get_load_combinations",
        description=(
            "List all available load combinations and load cases from active SAP2000 model. "
            "This is useful to see what load combinations are available before selecting "
            "which ones to use for footing design or reaction extraction.\n\n"
            "Returns a list of load combination names (e.g., 'ULS2', 'ULS3', 'SLS1') "
            "and optionally load case names if include_cases=True.\n\n"
            "Use this tool BEFORE calling get_reaction_loads or calculate_footing_design "
            "to understand what load combinations are available in the model.\n\n"
            "IMPORTANT: SAP2000 must be running with a model open and set as active API instance "
            "(Tools → Set as active instance for API)."
        ),
        params_json_schema=GetLoadCombinationsArgs.model_json_schema(),
        on_invoke_tool=get_load_combinations_func,
    )
