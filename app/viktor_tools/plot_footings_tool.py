"""Tool for visualizing footing designs in plan view."""

import viktor as vkt
from pydantic import BaseModel, Field
from typing import Any, Literal


class FootingDesignData(BaseModel):
    """Data for a single footing design."""

    node_name: str = Field(..., description="Node identifier")
    x: float | None = Field(
        None,
        description="X coordinate in meters. If not provided, will be loaded from SAP2000 support coordinates storage.",
    )
    y: float | None = Field(
        None,
        description="Y coordinate in meters. If not provided, will be loaded from SAP2000 support coordinates storage.",
    )
    B: float | None = Field(None, description="Footing width B in meters")
    L: float | None = Field(None, description="Footing length L in meters")
    h: float | None = Field(None, description="Footing thickness h in meters")
    pedestal_size: float | None = Field(None, description="Pedestal size in meters")
    pedestal_height: float | None = Field(
        None, description="Pedestal height in meters"
    )
    total_weight: float | None = Field(None, description="Total weight in kN")
    governing_combo: str | None = Field(None, description="Governing load combination")


class PlotFootingsInput(BaseModel):
    """Arguments for plotting footing designs."""

    footings: list[FootingDesignData] | None = Field(
        default=None,
        description="List of footing designs to plot. If not provided, will auto-load from storage.",
    )
    title: str = Field(
        default="Footing Layout Plan - Optimal Designs",
        description="Plot title",
    )
    auto_load_from_storage: bool = Field(
        default=True,
        description="Whether to auto-load design results from storage if footings list is empty or None.",
    )


class ShowHideFootingsPlotArgs(BaseModel):
    """Arguments for show/hide footings plot tool."""

    action: Literal["show", "hide"] = Field(
        ...,
        description="Action to perform: 'show' to display the footings plot view, 'hide' to hide it",
    )


async def generate_footings_plot_func(ctx: Any, args: str) -> str:
    """Store footing design data for visualization."""
    import json

    payload = PlotFootingsInput.model_validate_json(args)

    # Step 1: Auto-load design results from storage if footings not provided
    if (not payload.footings or len(payload.footings) == 0) and payload.auto_load_from_storage:
        try:
            design_results_file = vkt.Storage().get("footing_sizing_results", scope="entity")
            if not design_results_file:
                return (
                    "❌ No footing designs provided and no design results found in storage.\n"
                    "Either:\n"
                    "1. Run 'calculate_footing_sizing' first to generate designs, OR\n"
                    "2. Provide explicit footing designs in the 'footings' parameter"
                )

            design_results_data = json.loads(design_results_file.getvalue_binary().decode("utf-8"))
            results = design_results_data.get("results", {})

            if not results:
                return "❌ No successful footing designs found in storage results."

            # Convert FootingSizingOutput format to FootingDesignData list
            payload.footings = []
            for node_name, node_result in results.items():
                geom = node_result.get("footing_geometry", {})
                payload.footings.append(
                    FootingDesignData(
                        node_name=node_name,
                        x=None,  # Will be filled from coords
                        y=None,  # Will be filled from coords
                        B=geom.get("width_B_m"),  # Already in meters
                        L=geom.get("length_L_m"),
                        h=geom.get("slab_thickness_h_m"),
                        pedestal_size=geom.get("pedestal_base_m"),
                        pedestal_height=geom.get("pedestal_height_m"),
                        total_weight=None,  # Not available in sizing results
                        governing_combo=None,  # Not available in sizing results
                    )
                )
        except Exception as e:
            return f"❌ Error loading footing sizing results from storage: {e}"

    # Validation
    if not payload.footings or len(payload.footings) == 0:
        return "❌ No footing designs to plot. Provide 'footings' parameter or ensure design results are in storage."

    # Step 2: Load support coordinates from storage to fill in missing x, y values
    coords_by_node = {}
    nodes_missing_coords = []

    try:
        stored_coords = vkt.Storage().get("model_support_coordinates", scope="entity")
        if stored_coords:
            coords_data = json.loads(stored_coords.getvalue_binary().decode("utf-8"))
            # Build lookup: node name -> {x, y, z}
            for coord in coords_data:
                node_name = coord.get("Joint")
                if node_name:
                    coords_by_node[node_name] = {
                        "x": coord.get("X", 0.0),
                        "y": coord.get("Y", 0.0),
                        "z": coord.get("Z", 0.0),
                    }
    except Exception:
        # No coordinates in storage - will use provided x, y or fail
        pass

    # Step 3: Fill in missing coordinates from storage
    for footing in payload.footings:
        if footing.x is None or footing.y is None:
            # Try to load from storage
            if footing.node_name in coords_by_node:
                node_coords = coords_by_node[footing.node_name]
                footing.x = footing.x or node_coords["x"]
                footing.y = footing.y or node_coords["y"]
            else:
                nodes_missing_coords.append(footing.node_name)

    # Check if any nodes still missing coordinates
    if nodes_missing_coords:
        return (
            f"❌ Error: Cannot plot footings. Missing coordinates for nodes: {', '.join(nodes_missing_coords)}. "
            f"Either provide x, y coordinates explicitly or ensure get_support_coordinates has been run first "
            f"to load node positions from SAP2000 into storage."
        )

    # Step 4: Store plot data for visualization
    if payload:
        vkt.Storage().set(
            "PlotFootingsTool",
            data=vkt.File.from_data(payload.model_dump_json()),
            scope="entity",
        )

        coord_source = (
            "from SAP2000 storage"
            if coords_by_node
            else "from provided coordinates"
        )
        return f"✅ Footings plot data generated for {len(payload.footings)} nodes ({coord_source}). Call show_hide_footings_plot with action='show' to display the plot."
    return f"Validation error: Incorrect outputs {args}"


async def show_hide_footings_plot_func(ctx: Any, args: str) -> str:
    """Show or hide the footings plot view."""
    payload = ShowHideFootingsPlotArgs.model_validate_json(args)
    action = payload.action

    if action == "show":
        print("Showing Footings Plot View")
    else:
        print("Hiding Footings Plot View")

    vkt.Storage().set(
        "show_footings_plot",
        data=vkt.File.from_data(action),
        scope="entity",
    )
    print(f"Footings Plot Visibility State Changed to {action}")
    return f"Footings Plot Visibility State Changed to {action}"


def generate_footings_plot_tool() -> Any:
    """Create the function tool for generating footings plot."""
    from agents import FunctionTool

    return FunctionTool(
        name="generate_footings_plot",
        description=(
            "Generate a plan view plot of footing designs showing footings, pedestals, and node positions. "
            "\n\n"
            "AUTOMATIC MODE (Recommended):\n"
            "Simply call with {} (empty parameters) to auto-load:\n"
            "1. Design results from 'calculate_footing_sizing' (dimensions, geometry)\n"
            "2. Node coordinates from 'get_support_coordinates' (x, y positions)\n"
            "The tool will automatically merge this data and create the plot.\n\n"
            "MANUAL MODE:\n"
            "Alternatively, provide explicit 'footings' list with node_name and design parameters "
            "(B, L, h, pedestal_size, etc.). Coordinates will still be auto-loaded from storage.\n\n"
            "VISUALIZATION:\n"
            "- Footings shown as light gray rectangles with dimensions\n"
            "- Pedestals shown as dark gray rectangles\n"
            "- Node labels and hover info\n"
            "- Equal aspect ratio for accurate geometric representation\n\n"
            "After generating, call show_hide_footings_plot with action='show' to display.\n\n"
            "PREREQUISITES:\n"
            "- get_support_coordinates (for node positions)\n"
            "- calculate_footing_sizing (for design results) if using automatic mode"
        ),
        params_json_schema=PlotFootingsInput.model_json_schema(),
        on_invoke_tool=generate_footings_plot_func,
    )


def show_hide_footings_plot_tool() -> Any:
    """Create the function tool for showing/hiding footings plot."""
    from agents import FunctionTool

    return FunctionTool(
        name="show_hide_footings_plot",
        description=(
            "Show or hide the Footings Plot view panel. "
            "Pass 'show' to display the footings plot view, 'hide' to hide it."
        ),
        params_json_schema=ShowHideFootingsPlotArgs.model_json_schema(),
        on_invoke_tool=show_hide_footings_plot_func,
    )
