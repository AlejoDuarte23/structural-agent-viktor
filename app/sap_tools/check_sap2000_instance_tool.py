"""Tool to check if SAP2000 is running and available for API connection."""

import logging
from typing import Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CheckSap2000InstanceArgs(BaseModel):
    """Arguments for checking SAP2000 instance availability."""
    pass  # No arguments needed for this tool


async def check_sap2000_instance_func(ctx: Any, args: str) -> str:
    """
    Check if SAP2000 is running and available for API connection.

    This tool attempts to connect to SAP2000 to verify:
    - SAP2000 is running
    - A model is open
    - The instance is set as active for API access

    Returns a short status message indicating whether SAP2000 is ready.
    """
    try:
        from app.sap_tools.core import Sap2000Session
    except ImportError as e:
        return f"SAP2000 dependencies not available: {e}"

    try:
        # Attempt to connect to SAP2000
        with Sap2000Session() as sap:
            # If we get here, connection was successful
            model_name = "Unknown"
            try:
                # Try to get the model filename
                model_path = sap.SapModel.GetModelFilename()
                if model_path:
                    import os
                    model_name = os.path.basename(model_path)
            except Exception:
                # If we can't get the model name, that's okay
                pass

            return f"✓ SAP2000 is connected and ready. Active model: {model_name}"

    except RuntimeError as e:
        error_msg = str(e)
        if "Could not attach" in error_msg:
            return (
                "✗ SAP2000 connection failed. Please ensure:\n"
                "  1. SAP2000 is running\n"
                "  2. A model is open\n"
                "  3. Tools → Set as active instance for API is enabled\n"
                "  4. SAP2000 and Python have matching admin privileges"
            )
        return f"✗ SAP2000 connection error: {error_msg}"

    except Exception as e:
        logger.exception("Unexpected error checking SAP2000 instance")
        return f"✗ Unexpected error: {type(e).__name__}: {e}"


def check_sap2000_instance_tool() -> Any:
    """Create the function tool for checking SAP2000 instance availability."""
    from agents import FunctionTool

    return FunctionTool(
        name="check_sap2000_instance",
        description=(
            "Check if SAP2000 is running and available for API connection. "
            "This tool verifies that:\n"
            "- SAP2000 application is running\n"
            "- A structural model is open\n"
            "- The instance is set as active for API (Tools → Set as active instance for API)\n"
            "- Connection can be established via COM interface\n\n"
            "Use this tool before running other SAP2000 operations to verify the environment is ready. "
            "Returns a concise status message indicating whether SAP2000 is available."
        ),
        params_json_schema=CheckSap2000InstanceArgs.model_json_schema(),
        on_invoke_tool=check_sap2000_instance_func,
    )
