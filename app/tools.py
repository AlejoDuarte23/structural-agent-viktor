import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, Json

from app.viktor_tools.footing_sizing_tool import calculate_footing_sizing_tool
from app.viktor_tools.footing_concrete_rebar_tool import calculate_footing_concrete_rebar_tool
from app.viktor_tools.plotting_tool import generate_plot, show_hide_plot_tool
from app.viktor_tools.table_tool import generate_table, show_hide_table_tool
from app.viktor_tools.plot_footings_tool import (
    generate_footings_plot_tool,
    show_hide_footings_plot_tool,
)
from app.sap_tools.check_sap2000_instance_tool import check_sap2000_instance_tool
from app.sap_tools.get_support_coordinates_tool import get_support_coordinates_tool
from app.sap_tools.get_reaction_loads_tool import get_reaction_loads_tool
from app.sap_tools.get_load_combinations_tool import get_load_combinations_tool
from app.sap_tools.display_support_coords_table import (
    display_support_coordinates_table_tool,
)
from app.sap_tools.display_reaction_loads_table import (
    display_reaction_loads_table_tool,
)


# Friendly display names for tools in chat
TOOL_DISPLAY_NAMES: dict[str, str] = {
    "calculate_footing_sizing": "Calculate Footing Sizing (Optimization)",
    "calculate_footing_concrete_rebar": "Calculate Footing Concrete Rebar (ACI 318)",
    "generate_plotly": "Generate Plot",
    "generate_table": "Generate Table",
    "show_hide_plot": "Show/Hide Plot",
    "show_hide_table": "Show/Hide Table",
    "generate_footings_plot": "Generate Footings Plot",
    "show_hide_footings_plot": "Show/Hide Footings Plot",
    "create_dummy_workflow_node": "Create Workflow Node",
    "compose_workflow_graph": "Compose Workflow Graph",
    "check_sap2000_instance": "Check SAP2000 Connection",
    "get_support_coordinates": "Get Support Coordinates (SAP2000)",
    "get_reaction_loads": "Get Reaction Loads (SAP2000)",
    "get_load_combinations": "Get Load Combinations (SAP2000)",
    "display_support_coordinates_table": "Display Support Coordinates",
    "display_reaction_loads_table": "Display Reaction Loads",
}


class Workflow(BaseModel):
    pass


class GeometryGeneration(BaseModel):
    structure_width: float = Field(..., description="Widht of the structure in mm")
    structure_lenght: float = Field(..., description="Lenght of the structure in mm")
    structure_height: float = Field(..., description="Height of the structure in mm")
    csc_section: Literal["UB200x30", "310UBx46"]


class WindloadAnalysis(BaseModel):
    region: Literal["A", "B", "C", "D"]
    wind_speed: float = Field(..., description="Wind speed in m/s")
    exposure_level: Literal["A", "B", "C", "D"]


class Result(BaseModel):
    pass


class StructuralAnalysis(BaseModel):
    geometry_result: Result
    wind_result: Result | None = None


class FootingCapacity(BaseModel):
    soil_cateogory: Literal["A", "B", "C", "D", "F"]
    foundation_type: Literal["Footing", "Pile", "Slab"]


class FootingDesign(BaseModel):
    reaction_loads: list[float]
    footing_capacity_result: Result


class DummyWorkflowNode(BaseModel):
    node_id: str = Field(..., description="Unique id for this workflow node")
    node_type: Literal[
        "sap2000_tool",
        "sap2000_load_combos",
        "sap2000_extraction",
        "footing_sizing",
        "footing_concrete_rebar",
        "plot_output",
        "table_output",
        "footings_plot_output",
    ] = Field(..., description="Type of workflow node to add to the graph")
    label: str = Field(..., description="Human-readable label for the node")
    url: str | None = Field(
        default=None,
        description="URL to the VIKTOR app tool. Leave empty/null for output nodes (plot_output, table_output, footings_plot_output) as they are local visualization tools without URLs.",
    )
    inputs: Json[Any] = Field(
        default="{}",
        description=(
            "Input parameters for the node, provided as a JSON string. "
            'Example: \'{"wind_speed": 45.0, "region": "B"}\'.'
        ),
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of upstream node_ids this node depends on",
    )


async def create_dummy_workflow_node_func(
    _ctx: Any,
    args: str,
) -> str:
    payload = DummyWorkflowNode.model_validate_json(args)
    return f"Node '{payload.node_id}' ({payload.node_type}) created successfully."


def create_dummy_workflow_node_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="create_dummy_workflow_node",
        description="Create a dummy workflow-node JSON artifact for graph composition.",
        params_json_schema=DummyWorkflowNode.model_json_schema(),
        on_invoke_tool=create_dummy_workflow_node_func,
    )


class ComposeWorkflowGraphArgs(BaseModel):
    workflow_name: Annotated[str, Field(description="Name for the composed workflow")]
    nodes: Annotated[
        list[DummyWorkflowNode],
        Field(description="Workflow nodes with dependencies to compose"),
    ]


def toposort_edges(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    indegree: dict[str, int] = {n: 0 for n in nodes}
    outgoing: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        outgoing.setdefault(src, []).append(dst)
        indegree[dst] = indegree.get(dst, 0) + 1

    queue = [n for n, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in outgoing.get(node, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return visited == len(nodes)


async def compose_workflow_graph_func(ctx: Any, args: str) -> str:
    payload = ComposeWorkflowGraphArgs.model_validate_json(args)

    ids = [n.node_id for n in payload.nodes]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"Duplicate node_id(s): {', '.join(duplicates)}")

    id_set = set(ids)
    missing_deps: dict[str, list[str]] = {}
    edges: list[tuple[str, str]] = []
    for n in payload.nodes:
        unknown = [d for d in n.depends_on if d not in id_set]
        if unknown:
            missing_deps[n.node_id] = unknown
        for d in n.depends_on:
            edges.append((d, n.node_id))
    if missing_deps:
        msg = "; ".join(
            f"{nid} -> missing {', '.join(deps)}" for nid, deps in missing_deps.items()
        )
        raise ValueError(f"Unknown dependency node_id(s): {msg}")

    if not toposort_edges(ids, edges):
        raise ValueError("Cycle detected in depends_on; workflow_graph expects a DAG.")

    from app.workflow_graph.models import Connection, Node, Workflow
    from app.workflow_graph.viewer import WorkflowViewer

    # Default fallback URL (not applied to output nodes)
    default_url = "https://beta.viktor.ai/workspaces/4672/app/editor/2394"
    output_node_types = {"plot_output", "table_output", "footings_plot_output"}

    workflow = Workflow(
        nodes=[
            Node(
                id=n.node_id,
                title=n.label,
                type=n.node_type,
                url=None
                if n.node_type in output_node_types
                else (n.url or default_url),
                depends_on=[Connection(node_id=d) for d in n.depends_on],
            )
            for n in payload.nodes
        ]
    )

    viewer = WorkflowViewer(lambda: workflow)
    html_content = viewer.write()  # Returns HTML string

    # Store HTML in VIKTOR storage for WebView access
    try:
        import viktor as vkt

        data_json = json.dumps(
            {
                "html": html_content,
                "workflow_name": payload.workflow_name,
            }
        )
        vkt.Storage().set(
            "workflow_html",
            data=vkt.File.from_data(data_json),
            scope="entity",
        )
    except Exception:
        # Ignore if not running in VIKTOR context
        pass

    return f"Workflow '{payload.workflow_name}' created successfully with {len(payload.nodes)} nodes and {len(edges)} connections. The workflow graph has been updated and is now visible in the Workflow Graph view on the right side."


def compose_workflow_graph_tool() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="compose_workflow_graph",
        description="Compose nodes into a workflow_graph DAG and render a self-contained HTML graph.",
        params_json_schema=ComposeWorkflowGraphArgs.model_json_schema(),
        on_invoke_tool=compose_workflow_graph_func,
    )


def get_tools() -> list[Any]:
    return [
        create_dummy_workflow_node_tool(),
        compose_workflow_graph_tool(),
        check_sap2000_instance_tool(),
        get_support_coordinates_tool(),
        get_reaction_loads_tool(),
        get_load_combinations_tool(),
        display_support_coordinates_table_tool(),
        display_reaction_loads_table_tool(),
        calculate_footing_sizing_tool(),
        calculate_footing_concrete_rebar_tool(),
        generate_plot(),
        generate_table(),
        show_hide_plot_tool(),
        show_hide_table_tool(),
        generate_footings_plot_tool(),
        show_hide_footings_plot_tool(),
    ]
