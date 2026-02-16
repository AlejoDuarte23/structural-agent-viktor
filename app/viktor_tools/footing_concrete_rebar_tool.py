"""Footing Concrete Rebar Design Tool for VIKTOR integration (ACI 318-19).

This tool performs detailed concrete design checks including punching shear,
one-way shear, flexure, and rebar spacing calculations.
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


class FootingGeometryEntry(BaseModel):
    """Footing and pedestal geometry for a node."""

    node_name: str = Field(description="Node identifier")
    B: float = Field(description="Footing width (m)")
    L: float = Field(description="Footing length (m)")
    H: float = Field(description="Footing thickness (m)")
    b1: float = Field(description="Pedestal width (m)")
    b2: float = Field(description="Pedestal length (m)")
    ph: float = Field(description="Pedestal height (m)")


class LoadCaseEntry(BaseModel):
    """Single load case entry for a node."""

    case_name: str = Field(description="Load case name (e.g., 'LC1', 'ULS2')")
    node_name: str = Field(description="Node name this load case applies to")
    F1: float = Field(default=0.0, description="Force in X direction (kN)")
    F2: float = Field(default=0.0, description="Force in Y direction (kN)")
    F3: float = Field(default=0.0, description="Axial force in Z direction (kN)")
    M1: float = Field(default=0.0, description="Moment about X axis (kN·m)")
    M2: float = Field(default=0.0, description="Moment about Y axis (kN·m)")
    M3: float = Field(default=0.0, description="Moment about Z axis (kN·m)")


class SectionNodes(BaseModel):
    """Section: Node Coordinates."""

    node_coordinates: list[NodeCoordinate] = Field(
        default_factory=list,
        description="List of node coordinates (in meters)",
    )


class SectionGeometry(BaseModel):
    """Section: Footing & Pedestal Dimensions."""

    node_geometry: list[FootingGeometryEntry] = Field(
        default_factory=list,
        description="Footing and pedestal geometry for each node",
    )


class SectionLoadCases(BaseModel):
    """Section: Load Cases for all nodes."""

    load_cases: list[LoadCaseEntry] = Field(
        default_factory=list,
        description="List of load cases for all nodes",
    )


class SectionConcrete(BaseModel):
    """Section: Concrete properties."""

    gamma_concrete: float = Field(
        default=24.0, description="Concrete unit weight (kN/m³)"
    )
    fc: float = Field(default=28.0, description="Concrete strength f'c (MPa)")
    fy: float = Field(default=420.0, description="Steel yield strength fy (MPa)")
    gamma_fill: float = Field(default=19.5, description="Fill unit weight (kN/m³)")
    cover: float = Field(default=60, description="Concrete cover (mm)")
    db: float = Field(default=12, description="Rebar diameter (mm)")


class FootingConcreteRebarInput(BaseModel):
    """Complete input parameters for footing concrete rebar design tool."""

    section_nodes: SectionNodes = Field(
        default_factory=SectionNodes,
        description="Node coordinates",
    )
    section_geometry: SectionGeometry = Field(
        default_factory=SectionGeometry,
        description="Footing and pedestal dimensions",
    )
    load_cases_section: SectionLoadCases = Field(
        default_factory=SectionLoadCases,
        description="Load cases for all nodes",
    )
    section_concrete: SectionConcrete = Field(
        default_factory=SectionConcrete,
        description="Concrete and steel properties",
    )


# =============================================================================
# Output Models
# =============================================================================


class NodeDesignResult(BaseModel):
    """Complete design result for a single node."""

    # Coordinates
    x_m: float
    y_m: float
    z_m: float

    # Footing geometry
    footing_width_B_m: float
    footing_length_L_m: float
    footing_thickness_H_m: float
    effective_depth_d_m: float

    # Pedestal geometry
    pedestal_width_b1_m: float
    pedestal_length_b2_m: float
    pedestal_height_ph_m: float

    # Foundation weights
    total_weight_kN: float
    slab_weight_kN: float
    pedestal_weight_kN: float
    fill_weight_kN: float

    # Punching shear (critical case)
    punching_critical_case: str
    punching_Vu_kN: float
    punching_Vc_kN: float
    punching_utilization: float
    punching_passes: bool

    # One-way shear X (critical case)
    oneway_x_critical_case: str
    oneway_x_Vu_kN: float
    oneway_x_Vc_kN: float
    oneway_x_utilization: float
    oneway_x_passes: bool

    # One-way shear Y (critical case)
    oneway_y_critical_case: str
    oneway_y_Vu_kN: float
    oneway_y_Vc_kN: float
    oneway_y_utilization: float
    oneway_y_passes: bool

    # Flexure X direction (critical case)
    flexure_x_critical_case: str
    flexure_x_As_req_mm2: float
    flexure_x_Mu_kNm: float

    # Flexure Y direction (critical case)
    flexure_y_critical_case: str
    flexure_y_As_req_mm2: float
    flexure_y_Mu_kNm: float

    # Rebar spacing X
    rebar_x_number_of_bars: int
    rebar_x_spacing_c2c_mm: float
    rebar_x_spacing_clear_mm: float

    # Rebar spacing Y
    rebar_y_number_of_bars: int
    rebar_y_spacing_c2c_mm: float
    rebar_y_spacing_clear_mm: float

    # Overall status
    all_checks_pass: bool
    status_message: str


class FootingConcreteRebarOutput(BaseModel):
    """Output from footing concrete rebar design."""

    design_parameters: dict[str, float] = Field(
        description="Design parameters used"
    )
    nodes: dict[str, NodeDesignResult] = Field(
        description="Dictionary mapping node names to design results"
    )


# =============================================================================
# Tool Implementation
# =============================================================================


class FootingConcreteRebarTool(ViktorTool):
    """Tool to run footing concrete rebar design via VIKTOR app."""

    def __init__(
        self,
        rebar_input: FootingConcreteRebarInput,
        workspace_id: int = 4864,
        entity_id: int = 2641,
        method_name: str = "download_design_results",
    ):
        super().__init__(workspace_id, entity_id)
        self.rebar_input = rebar_input
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        """Build the API payload matching VIKTOR parametrization structure."""
        params = {
            "section_nodes": {
                "node_coordinates": [
                    {
                        "node_name": node.node_name,
                        "x": node.x,
                        "y": node.y,
                        "z": node.z,
                    }
                    for node in self.rebar_input.section_nodes.node_coordinates
                ]
            },
            "section_geometry": {
                "node_geometry": [
                    {
                        "node_name": geom.node_name,
                        "B": geom.B,
                        "L": geom.L,
                        "H": geom.H,
                        "b1": geom.b1,
                        "b2": geom.b2,
                        "ph": geom.ph,
                    }
                    for geom in self.rebar_input.section_geometry.node_geometry
                ]
            },
            "load_cases_section": {
                "load_cases": [
                    {
                        "case_name": lc.case_name,
                        "node_name": lc.node_name,
                        "F1": lc.F1,
                        "F2": lc.F2,
                        "F3": lc.F3,
                        "M1": lc.M1,
                        "M2": lc.M2,
                        "M3": lc.M3,
                    }
                    for lc in self.rebar_input.load_cases_section.load_cases
                ]
            },
            "section_concrete": {
                "gamma_concrete": self.rebar_input.section_concrete.gamma_concrete,
                "fc": self.rebar_input.section_concrete.fc,
                "fy": self.rebar_input.section_concrete.fy,
                "gamma_fill": self.rebar_input.section_concrete.gamma_fill,
                "cover": int(self.rebar_input.section_concrete.cover),
                "db": int(self.rebar_input.section_concrete.db),
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

    def run_and_parse(self) -> FootingConcreteRebarOutput:
        """Run the job and parse the result into FootingConcreteRebarOutput."""
        content = self.run_and_download()

        design_params = content.get("design_parameters", {})
        nodes_data = content.get("nodes", {})

        results = {}
        for node_name, node_data in nodes_data.items():
            if isinstance(node_data, dict) and node_data.get("status") == "No load cases defined":
                # Skip nodes without proper results
                continue
            if isinstance(node_data, dict) and "footing_width_B_m" in node_data:
                results[node_name] = NodeDesignResult(**node_data)

        return FootingConcreteRebarOutput(
            design_parameters=design_params,
            nodes=results
        )


# =============================================================================
# Flat Input Schema for Agent (easier for LLM to use)
# =============================================================================


class FootingConcreteRebarFlatInput(BaseModel):
    """Simplified input - auto-loads data from storage."""

    # Concrete properties (consistent with other tools)
    fc_mpa: float = Field(
        default=28.0,
        description="Concrete compressive strength in MPa",
    )
    fy_mpa: float = Field(
        default=420.0,
        description="Steel yield strength in MPa",
    )
    gamma_concrete_kNm3: float = Field(
        default=24.0,
        description="Concrete unit weight in kN/m³",
    )
    gamma_fill_kNm3: float = Field(
        default=19.5,
        description="Fill unit weight in kN/m³",
    )
    cover_mm: float = Field(
        default=60,
        description="Concrete cover in mm",
    )
    db_mm: float = Field(
        default=12,
        description="Rebar diameter in mm",
    )

    # Load combo selection (optional)
    load_combinations_to_check: list[str] | str | None = Field(
        default=None,
        description="List of load combinations to check (e.g., ['ULS2', 'ULS3']) or a single combo name. "
        "If None, uses all available combinations. "
        "The tool will check ALL specified combos per node and identify critical cases.",
    )


async def calculate_footing_concrete_rebar_func(ctx: Any, args: str) -> str:
    """Auto-loads SAP2000 data and footing sizing results from storage, runs concrete design."""
    flat_input = FootingConcreteRebarFlatInput.model_validate_json(args)

    # Step 1: Load SAP2000 data from Viktor Storage
    try:
        import viktor as vkt

        # Get support coordinates
        coords_file = vkt.Storage().get("model_support_coordinates", scope="entity")
        if not coords_file:
            return (
                "❌ SAP2000 support coordinates not found in storage.\n"
                "Please run get_support_coordinates first."
            )

        # Get reaction loads
        reactions_file = vkt.Storage().get("model_reaction_loads", scope="entity")
        if not reactions_file:
            return (
                "❌ SAP2000 reaction loads not found in storage.\n"
                "Please run get_reaction_loads first."
            )

        # Get footing sizing results
        sizing_file = vkt.Storage().get("footing_sizing_results", scope="entity")
        if not sizing_file:
            return (
                "❌ Footing sizing results not found in storage.\n"
                "Please run calculate_footing_sizing first to get footing dimensions."
            )

        # Parse JSON data from storage
        support_coords = json.loads(coords_file.getvalue_binary().decode("utf-8"))
        reaction_loads = json.loads(reactions_file.getvalue_binary().decode("utf-8"))
        sizing_results = json.loads(sizing_file.getvalue_binary().decode("utf-8"))

        logger.info(
            f"Loaded data: {len(support_coords)} nodes, "
            f"{len(sizing_results.get('results', {}))} sized footings"
        )

    except ImportError:
        return "❌ Viktor module not available - cannot access storage."
    except json.JSONDecodeError as e:
        logger.exception("Failed to parse storage data")
        return f"❌ Error parsing data from storage: {e}"
    except Exception as e:
        logger.exception("Unexpected error loading storage data")
        return f"❌ Error loading data from storage: {e}"

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

    # Step 3: Build footing geometry from sizing results
    footing_geometry = []
    sizing_res = sizing_results.get("results", {})

    for node_name, result in sizing_res.items():
        if "footing_geometry" in result:
            geom = result["footing_geometry"]
            footing_geometry.append(
                FootingGeometryEntry(
                    node_name=node_name,
                    B=geom["width_B_m"],
                    L=geom["length_L_m"],
                    H=geom["slab_thickness_h_m"],
                    b1=geom["pedestal_base_m"],
                    b2=geom["pedestal_base_m"],  # Assuming square pedestal
                    ph=geom["pedestal_height_m"],
                )
            )

    if not footing_geometry:
        return (
            "❌ No footing geometry found in sizing results.\n"
            "Ensure calculate_footing_sizing completed successfully."
        )

    # Step 4: Build load cases - filter by specified combinations
    load_cases_list = []

    # Normalize load_combinations_to_check to list
    if flat_input.load_combinations_to_check is not None:
        if isinstance(flat_input.load_combinations_to_check, str):
            combos_to_check = [flat_input.load_combinations_to_check]
        else:
            combos_to_check = flat_input.load_combinations_to_check
    else:
        combos_to_check = None

    # Only include nodes that have sizing results
    nodes_with_geometry = {geom.node_name for geom in footing_geometry}

    for support in support_coords:
        node_name = support["Joint"]

        # Skip nodes without geometry
        if node_name not in nodes_with_geometry:
            continue

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
                    node_name=node_name,
                    F1=reaction["F1"],
                    F2=reaction["F2"],
                    F3=reaction["F3"],
                    M1=reaction["M1"],
                    M2=reaction["M2"],
                    M3=reaction["M3"],
                )
            )

    logger.info(f"Built {len(load_cases_list)} load case entries for design checks")

    # Step 5: Create complete footing concrete rebar input
    rebar_input = FootingConcreteRebarInput(
        section_nodes=SectionNodes(node_coordinates=node_coords),
        section_geometry=SectionGeometry(node_geometry=footing_geometry),
        load_cases_section=SectionLoadCases(load_cases=load_cases_list),
        section_concrete=SectionConcrete(
            gamma_concrete=flat_input.gamma_concrete_kNm3,
            fc=flat_input.fc_mpa,
            fy=flat_input.fy_mpa,
            gamma_fill=flat_input.gamma_fill_kNm3,
            cover=flat_input.cover_mm,
            db=flat_input.db_mm,
        ),
    )

    # Step 6: Run footing concrete rebar tool
    tool = FootingConcreteRebarTool(rebar_input=rebar_input)
    result = tool.run_and_parse()

    # Step 6.5: Store full results in Viktor Storage
    try:
        result_data = result.model_dump()
        vkt.Storage().set(
            "footing_rebar_results",
            data=vkt.File.from_data(json.dumps(result_data, indent=2)),
            scope="entity",
        )
        logger.info(f"Stored footing rebar results in storage")
    except Exception as e:
        logger.warning(f"Failed to store footing rebar results: {e}")

    # Step 7: Format response
    if len(result.nodes) == 0:
        return (
            f"Footing concrete design completed. "
            "❌ No design results generated."
        )

    # Summarize results
    design_summaries = []
    all_pass_count = 0

    for node_name, node_result in result.nodes.items():
        if node_result.all_checks_pass:
            all_pass_count += 1

        summary = {
            "node": node_name,
            "footing_m": f"{node_result.footing_width_B_m:.2f}x{node_result.footing_length_L_m:.2f}x{node_result.footing_thickness_H_m:.2f}",
            "effective_depth_m": round(node_result.effective_depth_d_m, 3),
            "punching_status": "PASS" if node_result.punching_passes else "FAIL",
            "punching_util": round(node_result.punching_utilization, 2),
            "oneway_x_status": "PASS" if node_result.oneway_x_passes else "FAIL",
            "oneway_y_status": "PASS" if node_result.oneway_y_passes else "FAIL",
            "rebar_x_spacing_mm": round(node_result.rebar_x_spacing_c2c_mm, 0),
            "rebar_y_spacing_mm": round(node_result.rebar_y_spacing_c2c_mm, 0),
            "all_checks_pass": node_result.all_checks_pass,
        }
        design_summaries.append(summary)

    result_json = {
        "nodes_checked": len(result.nodes),
        "nodes_passing": all_pass_count,
        "designs": design_summaries,
    }

    combo_msg = (
        f" using load combinations: {combos_to_check}"
        if combos_to_check
        else " using all available load combinations"
    )

    status_emoji = "✅" if all_pass_count == len(result.nodes) else "⚠️"

    return (
        f"{status_emoji} Footing concrete design completed{combo_msg}. "
        f"Checked {len(result.nodes)} footings: {all_pass_count} passing all checks, "
        f"{len(result.nodes) - all_pass_count} with failures.\n\n"
        f"Results: {json.dumps(result_json, indent=2)}"
    )


def calculate_footing_concrete_rebar_tool() -> Any:
    """Create the footing concrete rebar design function tool for the agent."""
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_footing_concrete_rebar",
        description=(
            "Perform detailed concrete design checks per ACI 318-19 including punching shear, "
            "one-way shear, flexure, and rebar spacing. "
            "Automatically loads node coordinates, reaction loads, and footing dimensions from storage.\n\n"
            "PREREQUISITES:\n"
            "- Must run 'get_support_coordinates' first (extracts node positions from SAP2000)\n"
            "- Must run 'get_reaction_loads' first (extracts forces/moments from SAP2000)\n"
            "- Must run 'calculate_footing_sizing' first (provides footing dimensions)\n"
            "Tool will return an error if required data is not in storage.\n\n"
            "LOAD COMBINATION SELECTION:\n"
            "- Use 'load_combinations_to_check' to specify which combos to check (e.g., ['ULS2', 'ULS3'])\n"
            "  The tool will check ALL specified combinations and identify critical cases for each check type\n"
            "- Can also pass a single combo name as a string (e.g., 'ULS3')\n"
            "- If None (default), checks all available combos\n\n"
            "DESIGN CHECKS PERFORMED:\n"
            "- Two-way shear (punching) per ACI 22.6\n"
            "- One-way shear (beam action) per ACI 22.5 in both X and Y directions\n"
            "- Flexural design and required rebar area in both directions\n"
            "- Rebar spacing and detailing (number of bars, center-to-center, clear spacing)\n"
            "- Foundation weight calculations (slab, pedestal, fill)\n\n"
            "REQUIRED PARAMETERS:\n"
            "- Concrete properties: fc_mpa (concrete strength), fy_mpa (steel yield)\n"
            "- Material weights: gamma_concrete_kNm3, gamma_fill_kNm3\n"
            "- Detailing: cover_mm (concrete cover), db_mm (rebar diameter)\n\n"
            "TYPICAL WORKFLOW:\n"
            "1. get_support_coordinates → Extract node positions\n"
            "2. get_reaction_loads → Extract forces/moments\n"
            "3. calculate_footing_sizing → Optimize footing dimensions\n"
            "4. calculate_footing_concrete_rebar → Perform detailed design checks (this tool)\n\n"
            "URL: https://beta.viktor.ai/workspaces/4864/app/editor/2641"
        ),
        params_json_schema=FootingConcreteRebarFlatInput.model_json_schema(),
        on_invoke_tool=calculate_footing_concrete_rebar_func,
    )


if __name__ == "__main__":
    # Test the tool with a real API request
    print("="*80)
    print("Testing Footing Concrete Rebar Design Tool - Live API Request")
    print("="*80)

    # Build test input matching EXACT default values from VIKTOR app definition
    rebar_input = FootingConcreteRebarInput(
        section_nodes=SectionNodes(
            node_coordinates=[
                NodeCoordinate(node_name="N1", x=0.0, y=0.0, z=0.0),
                NodeCoordinate(node_name="N2", x=5.0, y=0.0, z=0.0),
                NodeCoordinate(node_name="N3", x=10.0, y=0.0, z=0.0),
                NodeCoordinate(node_name="N4", x=0.0, y=5.0, z=0.0),
            ]
        ),
        section_geometry=SectionGeometry(
            node_geometry=[
                FootingGeometryEntry(
                    node_name="N1",
                    B=2.2,
                    L=2.4,
                    H=0.6,
                    b1=0.4,
                    b2=0.5,
                    ph=1.0,
                ),
                FootingGeometryEntry(
                    node_name="N2",
                    B=2.2,
                    L=2.4,
                    H=0.6,
                    b1=0.4,
                    b2=0.5,
                    ph=1.0,
                ),
                FootingGeometryEntry(
                    node_name="N3",
                    B=2.2,
                    L=2.4,
                    H=0.6,
                    b1=0.4,
                    b2=0.5,
                    ph=1.0,
                ),
                FootingGeometryEntry(
                    node_name="N4",
                    B=2.2,
                    L=2.4,
                    H=0.6,
                    b1=0.4,
                    b2=0.5,
                    ph=1.0,
                ),
            ]
        ),
        load_cases_section=SectionLoadCases(
            load_cases=[
                LoadCaseEntry(
                    case_name="LC1",
                    node_name="N1",
                    F1=3.0,
                    F2=2.0,
                    F3=-1750.0,
                    M1=100.0,
                    M2=100.0,
                    M3=0.0,
                ),
                LoadCaseEntry(
                    case_name="LC2",
                    node_name="N2",
                    F1=3.0,
                    F2=2.0,
                    F3=-1700.0,
                    M1=80.0,
                    M2=60.0,
                    M3=0.0,
                ),
                LoadCaseEntry(
                    case_name="LC3",
                    node_name="N3",
                    F1=3.0,
                    F2=2.0,
                    F3=-1700.0,
                    M1=80.0,
                    M2=60.0,
                    M3=0.0,
                ),
                LoadCaseEntry(
                    case_name="LC4",
                    node_name="N4",
                    F1=3.0,
                    F2=2.0,
                    F3=-1700.0,
                    M1=80.0,
                    M2=60.0,
                    M3=0.0,
                ),
            ]
        ),
        section_concrete=SectionConcrete(
            gamma_concrete=24.0,
            fc=28.0,
            fy=420.0,
            gamma_fill=19.5,
            cover=60,
            db=12,
        ),
    )

    tool = FootingConcreteRebarTool(rebar_input=rebar_input)

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
        # Run the design checks
        result = tool.run_and_parse()

        print("\n3. ✅ API Request Successful!")
        print("-" * 80)
        print(f"   Nodes checked: {len(result.nodes)}")

        print("\n4. Design Parameters:")
        print("-" * 80)
        for key, value in result.design_parameters.items():
            print(f"   {key}: {value}")

        print("\n5. Results Summary:")
        print("-" * 80)
        for node_name, node_result in result.nodes.items():
            print(f"\n   Node: {node_name}")
            print(f"   ├─ Footing: {node_result.footing_width_B_m:.2f}m × {node_result.footing_length_L_m:.2f}m × {node_result.footing_thickness_H_m:.2f}m")
            print(f"   ├─ Effective Depth: {node_result.effective_depth_d_m:.3f}m")
            print(f"   ├─ Total Weight: {node_result.total_weight_kN:.1f} kN")
            print(f"   │")
            print(f"   ├─ Punching Shear: {'✅ PASS' if node_result.punching_passes else '❌ FAIL'}")
            print(f"   │  └─ Critical: {node_result.punching_critical_case}, Util: {node_result.punching_utilization:.2f}")
            print(f"   │     Vu = {node_result.punching_Vu_kN:.1f} kN ≤ φVc = {node_result.punching_Vc_kN:.1f} kN")
            print(f"   │")
            print(f"   ├─ One-Way Shear X: {'✅ PASS' if node_result.oneway_x_passes else '❌ FAIL'}")
            print(f"   │  └─ Critical: {node_result.oneway_x_critical_case}, Util: {node_result.oneway_x_utilization:.2f}")
            print(f"   │     Vu = {node_result.oneway_x_Vu_kN:.1f} kN ≤ φVc = {node_result.oneway_x_Vc_kN:.1f} kN")
            print(f"   │")
            print(f"   ├─ One-Way Shear Y: {'✅ PASS' if node_result.oneway_y_passes else '❌ FAIL'}")
            print(f"   │  └─ Critical: {node_result.oneway_y_critical_case}, Util: {node_result.oneway_y_utilization:.2f}")
            print(f"   │     Vu = {node_result.oneway_y_Vu_kN:.1f} kN ≤ φVc = {node_result.oneway_y_Vc_kN:.1f} kN")
            print(f"   │")
            print(f"   ├─ Flexure X: As_req = {node_result.flexure_x_As_req_mm2:.0f} mm²")
            print(f"   │  └─ Critical: {node_result.flexure_x_critical_case}, Mu = {node_result.flexure_x_Mu_kNm:.1f} kN·m")
            print(f"   │")
            print(f"   ├─ Flexure Y: As_req = {node_result.flexure_y_As_req_mm2:.0f} mm²")
            print(f"   │  └─ Critical: {node_result.flexure_y_critical_case}, Mu = {node_result.flexure_y_Mu_kNm:.1f} kN·m")
            print(f"   │")
            print(f"   ├─ Rebar X: {node_result.rebar_x_number_of_bars} bars @ {node_result.rebar_x_spacing_c2c_mm:.0f}mm c/c")
            print(f"   │  └─ Clear spacing: {node_result.rebar_x_spacing_clear_mm:.0f}mm")
            print(f"   │")
            print(f"   ├─ Rebar Y: {node_result.rebar_y_number_of_bars} bars @ {node_result.rebar_y_spacing_c2c_mm:.0f}mm c/c")
            print(f"   │  └─ Clear spacing: {node_result.rebar_y_spacing_clear_mm:.0f}mm")
            print(f"   │")
            print(f"   └─ Overall: {'✅ ALL CHECKS PASS' if node_result.all_checks_pass else '❌ SOME CHECKS FAIL'}")

        # Count passing nodes
        passing_nodes = sum(1 for nr in result.nodes.values() if nr.all_checks_pass)
        total_nodes = len(result.nodes)

        print("\n6. Overall Summary:")
        print("-" * 80)
        print(f"   Total Nodes: {total_nodes}")
        print(f"   Passing All Checks: {passing_nodes}")
        print(f"   Failing Some Checks: {total_nodes - passing_nodes}")
        print(f"   Success Rate: {(passing_nodes/total_nodes)*100:.1f}%")

        print("\n7. Full Result Object:")
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
