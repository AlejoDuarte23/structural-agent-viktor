"""Tool to extract reaction loads from SAP2000 and store in Viktor Storage."""

import json
import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class GetReactionLoadsArgs(BaseModel):
    """Arguments for getting reaction loads from SAP2000."""

    run_analysis: bool = Field(
        default=True,
        description="Whether to run analysis before extracting data. Set to False if analysis is already complete.",
    )


async def get_reaction_loads_func(ctx: Any, args: str) -> str:
    """
    Extract reaction loads from active SAP2000 model and store in Viktor Storage.

    This tool connects to SAP2000 and extracts reactions for all support nodes across:
    - All load combinations
    - All load cases

    For each node and load combo/case, extracts:
    - F1, F2, F3 (forces in X, Y, Z directions in kN)
    - M1, M2, M3 (moments about X, Y, Z axes in kN·m)

    The data is stored in Viktor Storage with key "model_reaction_loads" for later use.
    """
    try:
        import viktor as vkt
        from app.sap_tools.core import (
            Sap2000Session,
            run_analysis,
            get_support_reactions_all_combos,
        )
    except ImportError as e:
        return f"Error importing required modules: {e}. Ensure pywin32 is installed and SAP2000 is available."

    # Parse arguments
    payload = GetReactionLoadsArgs.model_validate_json(args)

    try:
        # Connect to SAP2000 and extract reactions
        with Sap2000Session() as sap:
            if payload.run_analysis:
                logger.info("Running SAP2000 analysis...")
                run_analysis(sap.SapModel)

            logger.info("Extracting reaction loads for all load combinations and cases...")
            supports, reactions = get_support_reactions_all_combos(sap.SapModel)
            print(reactions)

        # Store in Viktor Storage
        data_json = json.dumps(reactions, indent=2)
        vkt.Storage().set(
            "model_reaction_loads",
            data=vkt.File.from_data(data_json),
            scope="entity",
        )

        logger.info(
            f"Stored reactions for {len(reactions)} nodes in Viktor Storage"
        )

        # Build concise summary
        node_names = list(reactions.keys())
        num_nodes = len(node_names)

        # Get number of load combos/cases from first node
        num_load_combos = 0
        load_combo_names = []
        if reactions and node_names:
            first_node_reactions = reactions[node_names[0]]
            num_load_combos = len(first_node_reactions)
            load_combo_names = list(first_node_reactions.keys())

        # Sample one node's reaction for display
        sample_node = None
        sample_combo = None
        sample_reaction = None
        if reactions and node_names and load_combo_names:
            sample_node = node_names[0]
            sample_combo = load_combo_names[0]
            sample_reaction = reactions[sample_node][sample_combo]

        summary_parts = [
            f"Successfully extracted reaction loads from SAP2000 model.",
            f"Nodes with reactions: {num_nodes}",
            f"Load combinations/cases per node: {num_load_combos}",
            f"Total reaction sets: {num_nodes * num_load_combos}",
        ]

        if sample_node and sample_combo and sample_reaction:
            summary_parts.append(
                f"Sample - Node '{sample_node}', Combo '{sample_combo}': "
                f"F1={sample_reaction['F1']:.2f}kN, "
                f"F2={sample_reaction['F2']:.2f}kN, "
                f"F3={sample_reaction['F3']:.2f}kN, "
                f"M1={sample_reaction['M1']:.2f}kN·m, "
                f"M2={sample_reaction['M2']:.2f}kN·m, "
                f"M3={sample_reaction['M3']:.2f}kN·m"
            )

        summary_parts.append(
            "Data stored in Viktor Storage with key 'model_reaction_loads'."
        )

        return "\n".join(summary_parts)

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
        return f"Error extracting reaction loads: {error_msg}"

    except Exception as e:
        logger.exception("Unexpected error in get_reaction_loads_func")
        return f"Unexpected error: {type(e).__name__}: {e}"


def get_reaction_loads_tool() -> Any:
    """Create the function tool for extracting reaction loads from SAP2000."""
    from agents import FunctionTool

    return FunctionTool(
        name="get_reaction_loads",
        description=(
            "Extract reaction loads from active SAP2000 model for all support nodes. "
            "Connects to SAP2000 via COM interface and retrieves reactions for all load combinations and cases:\n"
            "- F1, F2, F3: Forces in X, Y, Z directions (kN)\n"
            "- M1, M2, M3: Moments about X, Y, Z axes (kN·m)\n"
            "The extracted data is organized by node name, then by load combo/case name, "
            "and automatically stored in Viktor Storage with key 'model_reaction_loads' "
            "for use by other tools (like footing design).\n"
            "IMPORTANT: SAP2000 must be running with a model open and set as active API instance "
            "(Tools → Set as active instance for API)."
        ),
        params_json_schema=GetReactionLoadsArgs.model_json_schema(),
        on_invoke_tool=get_reaction_loads_func,
    )
