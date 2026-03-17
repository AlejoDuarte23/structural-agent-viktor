"""Footing Design Tool for VIKTOR integration.

This tool performs structural checks for concrete footing design according to ACI 318/NSR-10.
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


class NodeReaction(BaseModel):
    """Single node reaction entry for a load combination."""

    node_name: str = Field(description="Node identifier (e.g., 'N1')")
    load_combo: str = Field(default="LC1", description="Load combination name")
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


class SectionNodeCoords(BaseModel):
    """Section: Node Coordinates - positions from structural model."""

    node_coords: list[NodeCoordinate] = Field(
        default_factory=lambda: [
            NodeCoordinate(node_name="N1", x=0.0, y=0.0, z=0.0),
            NodeCoordinate(node_name="N2", x=5.0, y=0.0, z=0.0),
            NodeCoordinate(node_name="N3", x=5.0, y=5.0, z=0.0),
            NodeCoordinate(node_name="N4", x=0.0, y=5.0, z=0.0),
        ],
        description="List of node coordinates from ETABS or structural software (in meters)",
    )


class SectionNodeReactions(BaseModel):
    """Section: Node Reactions & Loads - forces and moments for each node."""

    node_reactions: list[NodeReaction] = Field(
        default_factory=lambda: [
            NodeReaction(
                node_name="N1",
                load_combo="LC1",
                F1=0.0,
                F2=0.0,
                F3=-15.0,
                M1=10.0,
                M2=8.0,
                M3=0.0,
            ),
            NodeReaction(
                node_name="N2",
                load_combo="LC1",
                F1=0.0,
                F2=0.0,
                F3=-20.0,
                M1=15.0,
                M2=12.0,
                M3=0.0,
            ),
        ],
        description="List of reaction forces and moments for each node and load combination",
    )


class SectionMaterials(BaseModel):
    """Section: Material Properties."""

    fc: float = Field(default=28, description="Concrete compressive strength (MPa)")
    fy: float = Field(default=420, description="Steel yield strength (MPa)")
    gamma_fill: float = Field(
        default=19.5, description="Unit weight of fill material (kN/m³)"
    )


class SectionSoil(BaseModel):
    """Section: Soil Properties."""

    gamma_soil: float = Field(default=20, description="Unit weight of soil (kN/m³)")
    phi: float = Field(default=25, description="Soil friction angle (degrees)")


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


class SectionFooting(BaseModel):
    """Section: Footing Dimensions (initial values for iteration)."""

    b: float = Field(default=1.5, description="Initial footing width (m)")
    l: float = Field(default=1.5, description="Initial footing length (m)")
    h: float = Field(default=0.4, description="Initial slab thickness (m)")
    d: float = Field(
        default=0.210, description="Effective depth (m), typically h - 90mm cover"
    )


class SectionPedestal(BaseModel):
    """Section: Pedestal Dimensions (initial values for iteration)."""

    h_ped: float = Field(default=0.300, description="Initial pedestal size in X (m)")
    b_ped: float = Field(default=0.300, description="Initial pedestal size in Y (m)")
    ped_height: float = Field(
        default=0.600, description="Pedestal height above footing (m)"
    )


class FootingDesignInput(BaseModel):
    """Complete input parameters for footing design tool."""

    section_node_coords: SectionNodeCoords = Field(
        default_factory=SectionNodeCoords,
        description="Node coordinates from structural model",
    )
    section_node_reactions: SectionNodeReactions = Field(
        default_factory=SectionNodeReactions,
        description="Node reactions and loads",
    )
    section_materials: SectionMaterials = Field(
        default_factory=SectionMaterials,
        description="Material properties (concrete, steel, fill)",
    )
    section_soil: SectionSoil = Field(
        default_factory=SectionSoil,
        description="Soil properties",
    )
    section_bearing: SectionBearing = Field(
        default_factory=SectionBearing,
        description="Depth vs bearing capacity table",
    )
    section_footing: SectionFooting = Field(
        default_factory=SectionFooting,
        description="Initial footing dimensions",
    )
    section_pedestal: SectionPedestal = Field(
        default_factory=SectionPedestal,
        description="Initial pedestal dimensions",
    )


# =============================================================================
# Output Models
# =============================================================================


class OptimalFootingDesign(BaseModel):
    """Optimal design result for a single node."""

    node_name: str = Field(description="Node identifier")
    pedestal_size_mm: float = Field(description="Pedestal size (mm)")
    pedestal_height_mm: float = Field(description="Pedestal height (mm)")
    footing_B_mm: float = Field(description="Footing width B (mm)")
    footing_L_mm: float = Field(description="Footing length L (mm)")
    footing_h_mm: float = Field(description="Slab thickness h (mm)")
    foundation_depth_mm: float = Field(description="Total foundation depth (mm)")
    footing_area_m2: float = Field(description="Footing area (m²)")
    governing_combo: str = Field(description="Governing load combination")
    # Optional fields not included in basic export
    total_weight_kN: float | None = Field(
        default=None, description="Total footing weight (kN)"
    )
    bearing_capacity_kPa: float | None = Field(
        default=None, description="Allowable bearing capacity (kPa)"
    )
    max_bearing_pressure_kPa: float | None = Field(
        default=None, description="Maximum bearing pressure (kPa)"
    )


class FootingDesignOutput(BaseModel):
    """Output from footing design calculation."""

    project_name: str = Field(default="Footing Design Results")
    num_nodes: int = Field(description="Number of nodes analyzed")
    num_successful: int = Field(description="Number of nodes with successful designs")
    designs: list[OptimalFootingDesign] = Field(
        description="List of optimal footing designs per node"
    )


# =============================================================================
# Tool Implementation
# =============================================================================


class FootingDesignTool(ViktorTool):
    """Tool to run footing design optimization via VIKTOR app."""

    def __init__(
        self,
        footing_input: FootingDesignInput,
        workspace_id: int = 4800,
        entity_id: int = 2581,
        method_name: str = "download_design_results",
    ):
        super().__init__(workspace_id, entity_id)
        self.footing_input = footing_input
        self.method_name = method_name

    def build_payload(self) -> dict[str, Any]:
        """Build the API payload matching VIKTOR parametrization structure."""
        params = {
            "section_node_coords": {
                "node_coords": [
                    nc.model_dump()
                    for nc in self.footing_input.section_node_coords.node_coords
                ]
            },
            "section_node_reactions": {
                "node_reactions": [
                    nr.model_dump()
                    for nr in self.footing_input.section_node_reactions.node_reactions
                ]
            },
            "section_materials": self.footing_input.section_materials.model_dump(),
            "section_soil": self.footing_input.section_soil.model_dump(),
            "section_bearing": {
                "bearing_table": [
                    bt.model_dump()
                    for bt in self.footing_input.section_bearing.bearing_table
                ]
            },
            "section_footing": self.footing_input.section_footing.model_dump(),
            "section_pedestal": self.footing_input.section_pedestal.model_dump(),
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

    def run_and_parse(self) -> FootingDesignOutput:
        """Run the job and parse the result into FootingDesignOutput."""
        content = self.run_and_download()

        # Parse the downloaded JSON structure
        nodes_data = content.get("nodes", [])
        designs = []

        for node in nodes_data:
            if node.get("design_status") == "NO_DESIGN_FOUND":
                continue

            pedestal = node.get("pedestal", {})
            footing = node.get("footing", {})

            designs.append(
                OptimalFootingDesign(
                    node_name=node.get("node_name", ""),
                    pedestal_size_mm=pedestal.get("size_mm", 0),
                    pedestal_height_mm=pedestal.get("height_mm", 0),
                    footing_B_mm=footing.get("width_B_mm", 0),
                    footing_L_mm=footing.get("length_L_mm", 0),
                    footing_h_mm=footing.get("thickness_h_mm", 0),
                    foundation_depth_mm=pedestal.get("height_mm", 0)
                    + footing.get("thickness_h_mm", 0),
                    footing_area_m2=(footing.get("width_B_mm", 0) / 1000)
                    * (footing.get("length_L_mm", 0) / 1000),
                    governing_combo=node.get("governing_load_combo", "N/A"),
                    # Optional fields from extended output (not in basic export)
                    total_weight_kN=node.get("total_weight_kN"),
                    bearing_capacity_kPa=node.get("bearing_capacity_kPa"),
                    max_bearing_pressure_kPa=node.get("max_bearing_pressure_kPa"),
                )
            )

        return FootingDesignOutput(
            project_name=content.get("project", "Footing Design Results"),
            num_nodes=len(nodes_data),
            num_successful=len(designs),
            designs=designs,
        )


# =============================================================================
# Flat Input Schema for Agent (easier for LLM to use)
# =============================================================================


class FootingDesignFlatInput(BaseModel):
    """Simplified input - node coords and loads auto-loaded from SAP2000 storage."""

    # Material properties
    fc_mpa: float = Field(
        default=28,
        description="Concrete compressive strength in MPa",
    )
    fy_mpa: float = Field(
        default=420,
        description="Steel yield strength in MPa",
    )
    gamma_fill_kNm3: float = Field(
        default=19.5,
        description="Unit weight of fill material in kN/m³",
    )

    # Soil properties
    gamma_soil_kNm3: float = Field(
        default=20,
        description="Unit weight of soil in kN/m³",
    )
    phi_deg: float = Field(
        default=25,
        description="Soil friction angle in degrees",
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

    # Load combo selection (optional)
    load_combinations_to_check: list[str] | None = Field(
        default=None,
        description="List of load combinations to check (e.g., ['ULS2', 'ULS3', 'SLS1']). "
                    "If None, uses all available combinations. "
                    "The tool will select the governing combo from this list per node based on max F3.",
    )
    governing_load_combo: str | None = Field(
        default=None,
        description="DEPRECATED: Use load_combinations_to_check instead. "
                    "Specific load combo to force for all nodes (e.g., 'ULS3'). "
                    "If specified, overrides load_combinations_to_check.",
    )


async def calculate_footing_design_func(ctx: Any, args: str) -> str:
    """Auto-loads SAP2000 data from storage and runs footing design."""
    flat_input = FootingDesignFlatInput.model_validate_json(args)

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
                "Then retry footing design."
            )

        # Get reaction loads
        reactions_file = vkt.Storage().get("model_reaction_loads", scope="entity")
        if not reactions_file:
            return (
                "❌ SAP2000 reaction loads not found in storage.\n"
                "Please run these tools first:\n"
                "1. get_support_coordinates (extracts node positions from SAP2000)\n"
                "2. get_reaction_loads (extracts forces/moments from SAP2000)\n"
                "Then retry footing design."
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

    # Step 3: Build node reactions - select governing combo for each node
    node_reactions = []
    governing_combos_used = {}

    for support in support_coords:
        node_name = support["Joint"]

        # Check if reaction data exists for this node
        if node_name not in reaction_loads:
            return (
                f"❌ No reaction data found for support node '{node_name}'.\n"
                "Please ensure get_reaction_loads extracted all support nodes."
            )

        node_combos = reaction_loads[node_name]

        # Determine which combos to consider
        if flat_input.governing_load_combo:
            # Legacy: Force specific combo for all nodes
            if flat_input.governing_load_combo not in node_combos:
                available = list(node_combos.keys())
                return (
                    f"❌ Load combination '{flat_input.governing_load_combo}' not found for node '{node_name}'.\n"
                    f"Available combinations: {', '.join(available)}"
                )
            selected_combo = flat_input.governing_load_combo
        elif flat_input.load_combinations_to_check:
            # Filter to specified combos only
            combos_to_check = {
                c: node_combos[c]
                for c in flat_input.load_combinations_to_check
                if c in node_combos
            }
            if not combos_to_check:
                available = list(node_combos.keys())
                return (
                    f"❌ None of the specified load combinations {flat_input.load_combinations_to_check} "
                    f"found for node '{node_name}'.\n"
                    f"Available combinations: {', '.join(available)}"
                )
            # Select combo with max F3 from filtered list
            selected_combo = max(
                combos_to_check.keys(), key=lambda c: abs(combos_to_check[c]["F3"])
            )
        else:
            # Auto-select from all available combos: max absolute F3
            selected_combo = max(
                node_combos.keys(), key=lambda c: abs(node_combos[c]["F3"])
            )

        reaction = node_combos[selected_combo]
        governing_combos_used[node_name] = selected_combo

        node_reactions.append(
            NodeReaction(
                node_name=node_name,
                load_combo=selected_combo,
                F1=reaction["F1"],
                F2=reaction["F2"],
                F3=reaction["F3"],
                M1=reaction["M1"],
                M2=reaction["M2"],
                M3=reaction["M3"],
            )
        )

    logger.info(f"Selected governing combos: {governing_combos_used}")

    # Step 4: Build bearing capacity table
    bearing_table = []
    for depth, capacity in zip(
        flat_input.bearing_depths_m, flat_input.bearing_capacities_kPa
    ):
        bearing_table.append(
            BearingCapacityEntry(depth=depth, bearing_capacity=capacity)
        )

    # Step 5: Create complete footing input
    footing_input = FootingDesignInput(
        section_node_coords=SectionNodeCoords(node_coords=node_coords),
        section_node_reactions=SectionNodeReactions(node_reactions=node_reactions),
        section_materials=SectionMaterials(
            fc=flat_input.fc_mpa,
            fy=flat_input.fy_mpa,
            gamma_fill=flat_input.gamma_fill_kNm3,
        ),
        section_soil=SectionSoil(
            gamma_soil=flat_input.gamma_soil_kNm3,
            phi=flat_input.phi_deg,
        ),
        section_bearing=SectionBearing(bearing_table=bearing_table),
        section_footing=SectionFooting(),
        section_pedestal=SectionPedestal(),
    )

    # Step 6: Run footing design tool
    tool = FootingDesignTool(footing_input=footing_input)
    result = tool.run_and_parse()

    # Step 6.5: Store full results in Viktor Storage for use by plot tools
    try:
        result_data = result.model_dump()
        vkt.Storage().set(
            "footing_design_results",
            data=vkt.File.from_data(json.dumps(result_data, indent=2)),
            scope="entity",
        )
        logger.info(f"Stored footing design results in storage")
    except Exception as e:
        logger.warning(f"Failed to store footing design results: {e}")

    # Step 7: Format response
    if result.num_successful == 0:
        return (
            f"Footing design analysis completed for {result.num_nodes} nodes. "
            "❌ No compliant designs found - consider increasing footing dimensions or bearing capacity."
        )

    # Summarize successful designs
    design_summaries = []
    for d in result.designs:
        summary = {
            "node": d.node_name,
            "footing_mm": f"{d.footing_B_mm:.0f}x{d.footing_L_mm:.0f}x{d.footing_h_mm:.0f}",
            "pedestal_mm": f"{d.pedestal_size_mm:.0f}x{d.pedestal_height_mm:.0f}",
            "area_m2": round(d.footing_area_m2, 2),
            "governing_combo": d.governing_combo,
        }
        if d.total_weight_kN is not None:
            summary["weight_kN"] = round(d.total_weight_kN, 1)
        design_summaries.append(summary)

    result_json = {
        "project": result.project_name,
        "nodes_analyzed": result.num_nodes,
        "successful_designs": result.num_successful,
        "designs": design_summaries,
    }

    return (
        f"✅ Footing design completed successfully using SAP2000 data. "
        f"Analyzed {result.num_nodes} support nodes, found {result.num_successful} optimal designs.\n\n"
        f"Results: {json.dumps(result_json, indent=2)}"
    )


def calculate_footing_design_tool() -> Any:
    """Create the footing design function tool for the agent."""
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_footing_design",
        description=(
            "Design concrete footings according to ACI 318/NSR-10 standards. "
            "Automatically loads node coordinates and reaction loads from SAP2000 storage data. "
            "Performs two-way (punching) shear, one-way (beam action) shear, and bearing capacity checks. "
            "Iterates to find optimal (minimum weight) footing and pedestal dimensions for each support node.\n\n"
            "PREREQUISITES:\n"
            "- Must run 'get_support_coordinates' first (extracts node positions from SAP2000)\n"
            "- Must run 'get_reaction_loads' first (extracts forces/moments from SAP2000)\n"
            "- Optionally run 'get_load_combinations' to see available load combinations\n"
            "Tool will return an error if SAP2000 data is not in storage.\n\n"
            "LOAD COMBINATION SELECTION:\n"
            "- Use 'load_combinations_to_check' to specify which combos to consider (e.g., ['ULS2', 'ULS3'])\n"
            "  The tool will select the governing combo from this list per node based on max axial load (F3)\n"
            "- If 'governing_load_combo' is specified (e.g., 'ULS3'), forces that combo for ALL nodes (legacy)\n"
            "- If both are None (default), automatically checks all available combos and selects max F3 per node\n\n"
            "REQUIRED PARAMETERS:\n"
            "- Material properties: fc_mpa (concrete strength), fy_mpa (steel yield), gamma_fill_kNm3\n"
            "- Soil properties: gamma_soil_kNm3, phi_deg (friction angle)\n"
            "- Bearing capacity: bearing_depths_m and bearing_capacities_kPa (for interpolation)\n\n"
            "URL: https://beta.viktor.ai/workspaces/4800/app/editor/2581"
        ),
        params_json_schema=FootingDesignFlatInput.model_json_schema(),
        on_invoke_tool=calculate_footing_design_func,
    )


if __name__ == "__main__":
    # Test the tool locally
    footing_input = FootingDesignInput(
        section_node_coords=SectionNodeCoords(
            node_coords=[
                NodeCoordinate(node_name="N1", x=0.0, y=0.0, z=0.0),
                NodeCoordinate(node_name="N2", x=5.0, y=0.0, z=0.0),
            ]
        ),
        section_node_reactions=SectionNodeReactions(
            node_reactions=[
                NodeReaction(
                    node_name="N1",
                    load_combo="LC1",
                    F3=-15.0,
                    M1=10.0,
                    M2=8.0,
                ),
                NodeReaction(
                    node_name="N2",
                    load_combo="LC1",
                    F3=-20.0,
                    M1=15.0,
                    M2=12.0,
                ),
            ]
        ),
        section_materials=SectionMaterials(fc=28, fy=420, gamma_fill=19.5),
        section_soil=SectionSoil(gamma_soil=20, phi=25),
        section_bearing=SectionBearing(
            bearing_table=[
                BearingCapacityEntry(depth=1.0, bearing_capacity=100.0),
                BearingCapacityEntry(depth=1.5, bearing_capacity=150.0),
                BearingCapacityEntry(depth=2.0, bearing_capacity=250.0),
            ]
        ),
    )

    tool = FootingDesignTool(footing_input=footing_input)

    import pprint

    print("Payload:")
    pprint.pp(tool.build_payload())
