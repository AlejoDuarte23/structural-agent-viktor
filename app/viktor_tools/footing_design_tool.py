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

    b: float = Field(default=1.0, description="Initial footing width (m)")
    l: float = Field(default=1.0, description="Initial footing length (m)")
    h: float = Field(default=0.3, description="Initial slab thickness (m)")
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
        workspace_id: int = 4796,
        entity_id: int = 2577,
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
    """Flat input parameters for footing design - easier for agent to use."""

    # Node coordinates (simplified - single node for basic usage)
    node_names: list[str] = Field(
        default=["N1", "N2"],
        description="List of node names to analyze",
    )
    node_x_coords_m: list[float] = Field(
        default=[0.0, 5.0],
        description="X coordinates for each node in meters",
    )
    node_y_coords_m: list[float] = Field(
        default=[0.0, 0.0],
        description="Y coordinates for each node in meters",
    )

    # Axial loads per node (simplified - using maximum load for design)
    axial_loads_kN: list[float] = Field(
        default=[-15.0, -20.0],
        description="Axial load Fz for each node in kN (negative = compression)",
    )
    moments_mx_kNm: list[float] = Field(
        default=[10.0, 15.0],
        description="Moment Mx for each node in kN·m",
    )
    moments_my_kNm: list[float] = Field(
        default=[8.0, 12.0],
        description="Moment My for each node in kN·m",
    )

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

    # Bearing capacity (simplified - single value or depth-dependent)
    bearing_depths_m: list[float] = Field(
        default=[1.0, 1.5, 2.0],
        description="Depths for bearing capacity interpolation in meters",
    )
    bearing_capacities_kPa: list[float] = Field(
        default=[100.0, 150.0, 250.0],
        description="Allowable bearing capacities at each depth in kPa",
    )


async def calculate_footing_design_func(ctx: Any, args: str) -> str:
    """Async function to invoke the footing design tool."""
    raw_input = json.loads(args)

    # Build structured input from flat parameters
    node_names = raw_input.get("node_names", ["N1", "N2"])
    node_x = raw_input.get("node_x_coords_m", [0.0, 5.0])
    node_y = raw_input.get("node_y_coords_m", [0.0, 0.0])
    axial_loads = raw_input.get("axial_loads_kN", [-15.0, -20.0])
    moments_mx = raw_input.get("moments_mx_kNm", [10.0, 15.0])
    moments_my = raw_input.get("moments_my_kNm", [8.0, 12.0])

    # Build node coordinates (already in meters)
    node_coords = []
    for i, name in enumerate(node_names):
        node_coords.append(
            NodeCoordinate(
                node_name=name,
                x=node_x[i] if i < len(node_x) else 0.0,
                y=node_y[i] if i < len(node_y) else 0.0,
                z=0.0,
            )
        )

    # Build node reactions (one load combo per node for simplicity)
    node_reactions = []
    for i, name in enumerate(node_names):
        node_reactions.append(
            NodeReaction(
                node_name=name,
                load_combo="LC1",
                F1=0.0,
                F2=0.0,
                F3=axial_loads[i] if i < len(axial_loads) else -15.0,
                M1=moments_mx[i] if i < len(moments_mx) else 10.0,
                M2=moments_my[i] if i < len(moments_my) else 8.0,
                M3=0.0,
            )
        )

    # Build bearing capacity table
    bearing_depths = raw_input.get("bearing_depths_m", [1.0, 1.5, 2.0])
    bearing_caps = raw_input.get("bearing_capacities_kPa", [100.0, 150.0, 250.0])
    bearing_table = []
    for i, depth in enumerate(bearing_depths):
        bearing_table.append(
            BearingCapacityEntry(
                depth=depth,
                bearing_capacity=bearing_caps[i] if i < len(bearing_caps) else 100.0,
            )
        )

    # Create structured input
    footing_input = FootingDesignInput(
        section_node_coords=SectionNodeCoords(node_coords=node_coords),
        section_node_reactions=SectionNodeReactions(node_reactions=node_reactions),
        section_materials=SectionMaterials(
            fc=raw_input.get("fc_mpa", 28),
            fy=raw_input.get("fy_mpa", 420),
            gamma_fill=raw_input.get("gamma_fill_kNm3", 19.5),
        ),
        section_soil=SectionSoil(
            gamma_soil=raw_input.get("gamma_soil_kNm3", 20),
            phi=raw_input.get("phi_deg", 25),
        ),
        section_bearing=SectionBearing(bearing_table=bearing_table),
        section_footing=SectionFooting(),
        section_pedestal=SectionPedestal(),
    )

    # Run the tool
    tool = FootingDesignTool(footing_input=footing_input)
    result = tool.run_and_parse()

    # Build summary response
    if result.num_successful == 0:
        return (
            f"Footing design analysis completed for {result.num_nodes} nodes. "
            "No compliant designs found - consider increasing footing dimensions or bearing capacity."
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
        # Add optional fields if available
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
        f"Footing design completed successfully. "
        f"Analyzed {result.num_nodes} nodes, found {result.num_successful} optimal designs. "
        f"Results: {json.dumps(result_json, indent=2)}"
    )


def calculate_footing_design_tool() -> Any:
    """Create the footing design function tool for the agent."""
    from agents import FunctionTool

    return FunctionTool(
        name="calculate_footing_design",
        description=(
            "Design concrete footings according to ACI 318/NSR-10 standards using a Viktor app. "
            "Performs two-way (punching) shear check, one-way (beam action) shear check, and bearing capacity verification. "
            "Takes node coordinates, axial loads and moments, material properties (concrete fc, steel fy), "
            "soil properties, and depth-dependent bearing capacity values. "
            "Iterates through footing and pedestal dimensions to find the optimal (minimum weight) design "
            "that satisfies all structural checks for each node. "
            "URL: https://beta.viktor.ai/workspaces/4796/app/editor/2577"
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
