"""Footing Sizing and Optimization Tool for VIKTOR integration.

This tool optimizes footing geometry to minimize weight while satisfying bearing capacity
for all load combinations. Uses iterative optimization approach.
"""

from typing import Any
from pydantic import BaseModel, Field
import logging
import json
from .base import ViktorTool

logger = logging.getLogger(__name__)


class NodeCoordinate(BaseModel):
    """Single node coordinate entry."""

    node_name: str = Field(description="Node identifier (e.g., 'N1')")
    x: float = Field(default=0.0, description="X coordinate in meters")
    y: float = Field(default=0.0, description="Y coordinate in meters")
    z: float = Field(default=0.0, description="Z coordinate in meters")


class LoadCaseEntry(BaseModel):
    """Single load case entry for a node."""

    case_name: str = Field(description="Load case name (e.g., 'LC1', 'ULS2')")
    node: str = Field(description="Node name this load case applies to")
    F1: float = Field(default=0.0, description="Force in X direction (kN)")
    F2: float = Field(default=0.0, description="Force in Y direction (kN)")
    F3: float = Field(default=0.0, description="Axial force in Z direction (kN)")
    M1: float = Field(default=0.0, description="Moment about X axis (kN·m)")
    M2: float = Field(default=0.0, description="Moment about Y axis (kN·m)")
    M3: float = Field(default=0.0, description="Moment about Z axis (kN·m)")


class BearingCapacityEntry(BaseModel):
    """Single depth vs bearing capacity entry."""

    depth: float = Field(description="Foundation depth in meters")
    bearing_capacity: float = Field(description="Allowable bearing capacity (kPa)")


class SectionNodes(BaseModel):
    """Section: Node Coordinates."""

    nodes: list[NodeCoordinate] = Field(
        default_factory=lambda: [
            NodeCoordinate(node_name="N1", x=0.0, y=0.0, z=0.0),
            NodeCoordinate(node_name="N2", x=5.0, y=0.0, z=0.0),
        ],
        description="List of node coordinates (in meters)",
    )


class SectionLoadCases(BaseModel):
    """Section: Load Cases for all nodes."""

    load_cases: list[LoadCaseEntry] = Field(
        default_factory=lambda: [
            LoadCaseEntry(
                case_name="LC1",
                node="N1",
                F1=0.0,
                F2=0.0,
                F3=-15.0,
                M1=10.0,
                M2=8.0,
                M3=0.0,
            ),
            LoadCaseEntry(
                case_name="LC2",
                node="N1",
                F1=5.0,
                F2=3.0,
                F3=-18.0,
                M1=15.0,
                M2=12.0,
                M3=0.0,
            ),
        ],
        description="List of load cases for all nodes",
    )


class SectionBearing(BaseModel):
    """Section: Depth vs Bearing Capacity table."""

    bearing_table: list[BearingCapacityEntry] = Field(
        default_factory=lambda: [
            BearingCapacityEntry(depth=1.0, bearing_capacity=100.0),
            BearingCapacityEntry(depth=1.5, bearing_capacity=150.0),
            BearingCapacityEntry(depth=2.0, bearing_capacity=250.0),
        ],
        description="Allowable bearing capacity at different depths for interpolation",
    )


class SectionOptimization(BaseModel):
    """Section: Optimization settings."""

    min_footing_length: float = Field(
        default=1.0,
        description="Minimum footing length to start optimization (m)",
    )


class SectionMaterial(BaseModel):
    """Section: Material properties."""

    gamma_concrete: float = Field(
        default=24.0, description="Concrete unit weight (kN/m³)"
    )
    gamma_fill: float = Field(default=18.0, description="Fill unit weight (kN/m³)")


class FootingSizingInput(BaseModel):
    """Complete input parameters for footing sizing tool."""

    nodes_section: SectionNodes = Field(
        default_factory=SectionNodes,
        description="Node coordinates",
    )
    load_cases_section: SectionLoadCases = Field(
        default_factory=SectionLoadCases,
        description="Load cases for all nodes",
    )
    section_bearing: SectionBearing = Field(
        default_factory=SectionBearing,
        description="Depth vs bearing capacity table",
    )
    optimization_section: SectionOptimization = Field(
        default_factory=SectionOptimization,
        description="Optimization settings",
    )
    material_section: SectionMaterial = Field(
        default_factory=SectionMaterial,
        description="Material properties",
    )


# =============================================================================
# Output Models
# =============================================================================


class FootingGeometry(BaseModel):
    """Footing geometry result."""

    length_L_m: float = Field(description="Footing length L (m)")
    width_B_m: float = Field(description="Footing width B (m)")
    slab_thickness_h_m: float = Field(description="Slab thickness h (m)")
    pedestal_base_m: float = Field(description="Pedestal base size (m)")
    pedestal_height_m: float = Field(description="Pedestal height (m)")
    total_depth_m: float = Field(description="Total foundation depth (m)")
    footing_area_m2: float = Field(description="Footing area (m²)")


class LoadInfo(BaseModel):
    """Load information."""

    Fz_kN: float = Field(description="Vertical force (kN)")


class BearingPressure(BaseModel):
    """Bearing pressure results."""

    qmax_kPa: float = Field(description="Maximum bearing pressure (kPa)")


class OptimalFootingResult(BaseModel):
    """Optimal footing result for a single node."""

    footing_geometry: FootingGeometry
    loads: LoadInfo
    bearing_pressure: BearingPressure


class FootingSizingOutput(BaseModel):
    """Output from footing sizing calculation."""

    results: dict[str, OptimalFootingResult] = Field(
        description="Dictionary mapping node names to optimization results"
    )


# =============================================================================
# Tool Implementation
# =============================================================================


class FootingSizingTool(ViktorTool):
    """Tool to run footing sizing optimization via VIKTOR app."""

    def __init__(
        self,
        sizing_input: FootingSizingInput,
        workspace_id: int = 4865,
        entity_id: int = 2639,
        method_name: str = "download_results",
    ):
        super().__init__(workspace_id, entity_id)
        self.sizing_input = sizing_input
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        """Build the API payload matching VIKTOR parametrization structure."""
        params = {
            "nodes_section": {
                "nodes": [
                    {
                        "node_name": node.node_name,
                        "x": node.x,
                        "y": node.y,
                        "z": node.z,
                    }
                    for node in self.sizing_input.nodes_section.nodes
                ]
            },
            "load_cases_section": {
                "load_cases": [
                    {
                        "case_name": lc.case_name,
                        "node": lc.node,
                        "F1": lc.F1,
                        "F2": lc.F2,
                        "F3": lc.F3,
                        "M1": lc.M1,
                        "M2": lc.M2,
                        "M3": lc.M3,
                    }
                    for lc in self.sizing_input.load_cases_section.load_cases
                ]
            },
            "section_bearing": {
                "bearing_table": [
                    {"depth": bt.depth, "bearing_capacity": bt.bearing_capacity}
                    for bt in self.sizing_input.section_bearing.bearing_table
                ]
            },
            "optimization_section": {
                "min_footing_length": self.sizing_input.optimization_section.min_footing_length
            },
            "material_section": {
                "gamma_concrete": self.sizing_input.material_section.gamma_concrete,
                "gamma_fill": self.sizing_input.material_section.gamma_fill,
            },
        }
        return {
            "method_name": self.method_name,
            "params": params,
            "poll_result": True,
        }

    def run_and_download(self) -> dict:
        """Run the job and download the JSON result."""
        job = self.run()
        return self.download_result(job)

    def run_and_parse(self) -> FootingSizingOutput:
        """Run the job and parse the result into FootingSizingOutput."""
        content = self.run_and_download()

        results = {}
        for node_name, node_data in content.items():
            if isinstance(node_data, dict) and "footing_geometry" in node_data:
                geom = node_data["footing_geometry"]
                loads = node_data.get("loads", {})
                bearing = node_data.get("bearing_pressure", {})

                results[node_name] = OptimalFootingResult(
                    footing_geometry=FootingGeometry(
                        length_L_m=geom["length_L_m"],
                        width_B_m=geom["width_B_m"],
                        slab_thickness_h_m=geom["slab_thickness_h_m"],
                        pedestal_base_m=geom["pedestal_base_m"],
                        pedestal_height_m=geom["pedestal_height_m"],
                        total_depth_m=geom["total_depth_m"],
                        footing_area_m2=geom["footing_area_m2"],
                    ),
                    loads=LoadInfo(Fz_kN=loads.get("Fz_kN", 0.0)),
                    bearing_pressure=BearingPressure(
                        qmax_kPa=bearing.get("qmax_kPa", 0.0)
                    ),
                )

        return FootingSizingOutput(results=results)


# =============================================================================
# Flat Input Schema for Agent (easier for LLM to use)
# =============================================================================


class FootingSizingFlatInput(BaseModel):
    """Simplified input - node coords and loads auto-loaded from SAP2000 storage."""

    # Material properties
    gamma_concrete_kNm3: float = Field(
        default=24.0,
        description="Concrete unit weight in kN/m³",
    )
    gamma_fill_kNm3: float = Field(
        default=18.0,
        description="Fill unit weight in kN/m³",
    )

    # Bearing capacity
    bearing_depths_m: list[float] = Field(
        default=[1.0, 1.5, 2.0],
        description="Depths for bearing capacity interpolation in meters",
    )
    bearing_capacities_kPa: list[float] = Field(
        default=[100.0, 150.0, 250.0],
        description="Allowable bearing capacities at each depth in kPa",
    )

    # Optimization settings
    min_footing_length_m: float = Field(
        default=1.0,
        description="Minimum footing length to start optimization in meters",
    )

    # Load combo selection (optional)
    load_combinations_to_check: list[str] | str | None = Field(
        default=None,
        description="List of load combinations to check (e.g., ['ULS2', 'ULS3', 'SLS1']) or a single combo name. "
        "If None, uses all available combinations. "
        "The tool will use ALL specified combos per node for optimization.",
    )


async def calculate_footing_sizing_func(ctx: Any, args: str) -> str:
    """Auto-loads SAP2000 data from storage and runs footing sizing optimization."""
    flat_input = FootingSizingFlatInput.model_validate_json(args)

    # Step 1: Load SAP2000 data from Viktor Storage
    try:
        import viktor as vkt

        # Get support coordinates
        coords_file = vkt.Storage().get("model_support_coordinates", scope="entity")
        if not coords_file:
            return (
                "❌ SAP2000 support coordinates not found in storage.\n"
                "Please run these tools first:\n"
                "1. get_support_coordinates (extracts node positions from SAP2000)\n"
                "2. get_reaction_loads (extracts forces/moments from SAP2000)\n"
                "Then retry footing sizing."
            )

        # Get reaction loads
        reactions_file = vkt.Storage().get("model_reaction_loads", scope="entity")
        if not reactions_file:
            return (
                "❌ SAP2000 reaction loads not found in storage.\n"
                "Please run these tools first:\n"
                "1. get_support_coordinates (extracts node positions from SAP2000)\n"
                "2. get_reaction_loads (extracts forces/moments from SAP2000)\n"
                "Then retry footing sizing."
            )

        # Parse JSON data from storage
        support_coords = json.loads(coords_file.getvalue_binary().decode("utf-8"))
        reaction_loads = json.loads(reactions_file.getvalue_binary().decode("utf-8"))

        logger.info(
            f"Loaded SAP2000 data: {len(support_coords)} support nodes, "
            f"{len(reaction_loads)} nodes with reactions"
        )

    except ImportError:
        return "❌ Viktor module not available - cannot access storage."
    except json.JSONDecodeError as e:
        logger.exception("Failed to parse SAP2000 storage data")
        return f"❌ Error parsing SAP2000 data from storage: {e}"
    except Exception as e:
        logger.exception("Unexpected error loading SAP2000 data")
        return f"❌ Error loading SAP2000 data from storage: {e}"

    # Step 2: Build node coordinates from support data
    node_coords = []
    for support in support_coords:
        node_coords.append(
            NodeCoordinate(
                node_name=support["Joint"],
                x=support["X"],
                y=support["Y"],
                z=support["Z"],
            )
        )

    # Step 3: Build load cases - filter by specified combinations
    load_cases_list = []

    # Normalize load_combinations_to_check to list
    if flat_input.load_combinations_to_check is not None:
        if isinstance(flat_input.load_combinations_to_check, str):
            combos_to_check = [flat_input.load_combinations_to_check]
        else:
            combos_to_check = flat_input.load_combinations_to_check
    else:
        combos_to_check = None

    for support in support_coords:
        node_name = support["Joint"]

        # Check if reaction data exists for this node
        if node_name not in reaction_loads:
            return (
                f"❌ No reaction data found for support node '{node_name}'.\n"
                "Please ensure get_reaction_loads extracted all support nodes."
            )

        node_combos = reaction_loads[node_name]

        # Filter combos if specified
        if combos_to_check:
            filtered_combos = {
                combo: data
                for combo, data in node_combos.items()
                if combo in combos_to_check
            }
            if not filtered_combos:
                available = list(node_combos.keys())
                return (
                    f"❌ None of the specified load combinations {combos_to_check} "
                    f"found for node '{node_name}'.\n"
                    f"Available combinations: {', '.join(available)}"
                )
            combos_to_use = filtered_combos
        else:
            # Use all available combos
            combos_to_use = node_combos

        # Add all filtered combos for this node
        for combo_name, reaction in combos_to_use.items():
            load_cases_list.append(
                LoadCaseEntry(
                    case_name=combo_name,
                    node=node_name,
                    F1=reaction["F1"],
                    F2=reaction["F2"],
                    F3=reaction["F3"],
                    M1=reaction["M1"],
                    M2=reaction["M2"],
                    M3=reaction["M3"],
                )
            )

    logger.info(f"Built {len(load_cases_list)} load case entries for optimization")

    # Step 4: Build bearing capacity table
    bearing_table = []
    for depth, capacity in zip(
        flat_input.bearing_depths_m, flat_input.bearing_capacities_kPa
    ):
        bearing_table.append(
            BearingCapacityEntry(depth=depth, bearing_capacity=capacity)
        )

    # Step 5: Create complete footing sizing input
    sizing_input = FootingSizingInput(
        nodes_section=SectionNodes(nodes=node_coords),
        load_cases_section=SectionLoadCases(load_cases=load_cases_list),
        section_bearing=SectionBearing(bearing_table=bearing_table),
        optimization_section=SectionOptimization(
            min_footing_length=flat_input.min_footing_length_m
        ),
        material_section=SectionMaterial(
            gamma_concrete=flat_input.gamma_concrete_kNm3,
            gamma_fill=flat_input.gamma_fill_kNm3,
        ),
    )

    # Step 6: Run footing sizing tool
    tool = FootingSizingTool(sizing_input=sizing_input)
    result = tool.run_and_parse()

    # Step 6.5: Store full results in Viktor Storage for use by plot tools
    try:
        result_data = result.model_dump()
        vkt.Storage().set(
            "footing_sizing_results",
            data=vkt.File.from_data(json.dumps(result_data, indent=2)),
            scope="entity",
        )
        logger.info(f"Stored footing sizing results in storage")
    except Exception as e:
        logger.warning(f"Failed to store footing sizing results: {e}")

    # Step 7: Format response
    if len(result.results) == 0:
        return (
            f"Footing sizing optimization completed. "
            "❌ No compliant designs found - consider adjusting optimization parameters."
        )

    # Summarize successful designs
    design_summaries = []
    for node_name, node_result in result.results.items():
        geom = node_result.footing_geometry
        summary = {
            "node": node_name,
            "footing_m": f"{geom.width_B_m:.2f}x{geom.length_L_m:.2f}x{geom.slab_thickness_h_m:.2f}",
            "pedestal_m": f"{geom.pedestal_base_m:.2f}x{geom.pedestal_height_m:.2f}",
            "area_m2": round(geom.footing_area_m2, 2),
            "total_depth_m": round(geom.total_depth_m, 2),
            "max_pressure_kPa": round(node_result.bearing_pressure.qmax_kPa, 1),
        }
        design_summaries.append(summary)

    result_json = {
        "nodes_optimized": len(result.results),
        "designs": design_summaries,
    }

    combo_msg = (
        f" using load combinations: {combos_to_check}"
        if combos_to_check
        else " using all available load combinations"
    )

    return (
        f"✅ Footing sizing optimization completed successfully{combo_msg}. "
        f"Optimized {len(result.results)} support nodes for minimum weight.\n\n"
        f"Results: {json.dumps(result_json, indent=2)}"
    )


def calculate_footing_sizing_tool() -> Any:
    """Create the footing sizing function tool for the agent."""
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_footing_sizing",
        description=(
            "Optimize footing geometry to minimize weight while satisfying bearing capacity. "
            "Automatically loads node coordinates and reaction loads from SAP2000 storage data. "
            "Uses iterative optimization to find the lightest footing that meets all load combination requirements.\n\n"
            "PREREQUISITES:\n"
            "- Must run 'get_support_coordinates' first (extracts node positions from SAP2000)\n"
            "- Must run 'get_reaction_loads' first (extracts forces/moments from SAP2000)\n"
            "- Optionally run 'get_load_combinations' to see available load combinations\n"
            "Tool will return an error if SAP2000 data is not in storage.\n\n"
            "LOAD COMBINATION SELECTION:\n"
            "- Use 'load_combinations_to_check' to specify which combos to use (e.g., ['ULS2', 'ULS3'])\n"
            "  The tool will optimize footings to satisfy ALL specified combinations per node\n"
            "- Can also pass a single combo name as a string (e.g., 'ULS3')\n"
            "- If None (default), uses all available combos for optimization\n\n"
            "OPTIMIZATION:\n"
            "- Iterates through design space: L, B, h, pedestal size, pedestal height\n"
            "- Checks bearing capacity for all load cases\n"
            "- Handles eccentric loading (single and biaxial eccentricity)\n"
            "- Returns minimum weight solution that satisfies all constraints\n\n"
            "REQUIRED PARAMETERS:\n"
            "- Material properties: gamma_concrete_kNm3, gamma_fill_kNm3\n"
            "- Bearing capacity: bearing_depths_m and bearing_capacities_kPa (for interpolation)\n"
            "- Optimization: min_footing_length_m (starting size for iteration)\n\n"
            "URL: https://beta.viktor.ai/workspaces/4865/app/editor/2639"
        ),
        params_json_schema=FootingSizingFlatInput.model_json_schema(),
        on_invoke_tool=calculate_footing_sizing_func,
    )


if __name__ == "__main__":
    # Test the tool with a real API request
    print("="*80)
    print("Testing Footing Sizing Tool - Live API Request")
    print("="*80)

    # Build test input with sample nodes and load cases
    sizing_input = FootingSizingInput(
        nodes_section=SectionNodes(
            nodes=[
                NodeCoordinate(node_name="N1", x=0.0, y=0.0, z=0.0),
                NodeCoordinate(node_name="N2", x=5.0, y=0.0, z=0.0),
                NodeCoordinate(node_name="N3", x=5.0, y=5.0, z=0.0),
                NodeCoordinate(node_name="N4", x=0.0, y=5.0, z=0.0),
            ]
        ),
        load_cases_section=SectionLoadCases(
            load_cases=[
                # Node N1 - two load cases
                LoadCaseEntry(
                    case_name="LC1",
                    node="N1",
                    F1=0.0,
                    F2=0.0,
                    F3=15.0,
                    M1=10.0,
                    M2=8.0,
                    M3=0.0,
                ),
                LoadCaseEntry(
                    case_name="LC2",
                    node="N1",
                    F1=5.0,
                    F2=3.0,
                    F3=18.0,
                    M1=15.0,
                    M2=12.0,
                    M3=0.0,
                ),
                # Node N2 - two load cases
                LoadCaseEntry(
                    case_name="LC1",
                    node="N2",
                    F1=0.0,
                    F2=0.0,
                    F3=20.0,
                    M1=15.0,
                    M2=12.0,
                    M3=0.0,
                ),
                LoadCaseEntry(
                    case_name="LC2",
                    node="N2",
                    F1=8.0,
                    F2=4.0,
                    F3=23.0,
                    M1=20.0,
                    M2=18.0,
                    M3=0.0,
                ),
                # Node N3 - two load cases
                LoadCaseEntry(
                    case_name="LC1",
                    node="N3",
                    F1=0.0,
                    F2=0.0,
                    F3=20.0,
                    M1=15.0,
                    M2=12.0,
                    M3=0.0,
                ),
                LoadCaseEntry(
                    case_name="LC2",
                    node="N3",
                    F1=8.0,
                    F2=4.0,
                    F3=23.0,
                    M1=20.0,
                    M2=18.0,
                    M3=0.0,
                ),
                # Node N4 - two load cases
                LoadCaseEntry(
                    case_name="LC1",
                    node="N4",
                    F1=0.0,
                    F2=0.0,
                    F3=15.0,
                    M1=10.0,
                    M2=8.0,
                    M3=0.0,
                ),
                LoadCaseEntry(
                    case_name="LC2",
                    node="N4",
                    F1=5.0,
                    F2=3.0,
                    F3=18.0,
                    M1=15.0,
                    M2=12.0,
                    M3=0.0,
                ),
            ]
        ),
        section_bearing=SectionBearing(
            bearing_table=[
                BearingCapacityEntry(depth=1.0, bearing_capacity=150.0),
                BearingCapacityEntry(depth=1.5, bearing_capacity=180.0),
                BearingCapacityEntry(depth=2.0, bearing_capacity=200.0),
            ]
        ),
        optimization_section=SectionOptimization(
            min_footing_length=1.3
        ),
        material_section=SectionMaterial(
            gamma_concrete=24.0,
            gamma_fill=18.0
        ),
    )

    tool = FootingSizingTool(sizing_input=sizing_input)

    import pprint

    print("\n1. Generated Payload:")
    print("-" * 80)
    pprint.pp(tool.build_payload())

    print("\n2. Making API Request to VIKTOR...")
    print("-" * 80)
    print(f"   Workspace ID: {tool.workspace_id}")
    print(f"   Entity ID: {tool.entity_id}")
    print(f"   Method: {tool.method_name}")

    try:
        # Run the optimization
        result = tool.run_and_parse()

        print("\n3. ✅ API Request Successful!")
        print("-" * 80)
        print(f"   Nodes optimized: {len(result.results)}")

        print("\n4. Results Summary:")
        print("-" * 80)
        for node_name, node_result in result.results.items():
            geom = node_result.footing_geometry
            print(f"\n   Node: {node_name}")
            print(f"   ├─ Footing: {geom.width_B_m:.2f}m × {geom.length_L_m:.2f}m × {geom.slab_thickness_h_m:.2f}m")
            print(f"   ├─ Pedestal: {geom.pedestal_base_m:.2f}m × {geom.pedestal_height_m:.2f}m")
            print(f"   ├─ Total Depth: {geom.total_depth_m:.2f}m")
            print(f"   ├─ Area: {geom.footing_area_m2:.2f}m²")
            print(f"   └─ Max Pressure: {node_result.bearing_pressure.qmax_kPa:.1f} kPa")

        print("\n5. Full Result Object:")
        print("-" * 80)
        pprint.pp(result.model_dump())

        print("\n" + "="*80)
        print("✅ Test Complete - Tool is working correctly!")
        print("="*80)

    except Exception as e:
        print("\n3. ❌ API Request Failed!")
        print("-" * 80)
        print(f"   Error: {type(e).__name__}")
        print(f"   Message: {str(e)}")
        import traceback
        print("\n   Traceback:")
        traceback.print_exc()
        print("\n" + "="*80)
        print("❌ Test Failed - Check error details above")
        print("="*80)
