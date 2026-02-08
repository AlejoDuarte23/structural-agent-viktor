import asyncio
import json
import logging
import queue
import threading
from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent
from typing import Any
from collections.abc import Callable

import viktor as vkt
from agents import Agent, Runner
from openai.types.responses import ResponseTextDeltaEvent
from agents import set_tracing_disabled

from app.tools import get_tools, TOOL_DISPLAY_NAMES
from app.viktor_tools.plotting_tool import PlotTool
from app.viktor_tools.table_tool import TableTool

from dotenv import load_dotenv

import plotly.graph_objects as go

load_dotenv()

logger = logging.getLogger(__name__)

# Event loop management for async agent in sync VIKTOR context
event_loop: asyncio.AbstractEventLoop | None = None
event_loop_thread: threading.Thread | None = None

set_tracing_disabled(True)


def ensure_loop() -> asyncio.AbstractEventLoop:
    """Ensure a background event loop is running."""
    global event_loop, event_loop_thread
    if event_loop and event_loop.is_running():
        return event_loop
    event_loop = asyncio.new_event_loop()
    event_loop_thread = threading.Thread(
        target=event_loop.run_forever, name="agent-loop", daemon=True
    )
    event_loop_thread.start()
    return event_loop


def run_async(coro):
    """Run async coroutine in background loop and wait for result."""
    loop = ensure_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result()


def _extract_call_id(raw: Any) -> str | None:
    if isinstance(raw, dict):
        return (raw.get("call_id") or raw.get("id") or raw.get("tool_call_id")) and str(
            raw.get("call_id") or raw.get("id") or raw.get("tool_call_id")
        )
    for attr in ("call_id", "id", "tool_call_id"):
        v = getattr(raw, attr, None)
        if v:
            return str(v)
    return None


def _extract_tool_name(raw: Any) -> str:
    # Responses function-call items typically have a top-level "name" (or equivalent)
    if isinstance(raw, dict):
        if raw.get("name"):
            return str(raw["name"])
        fn = raw.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            return str(fn["name"])
        if raw.get("tool_name"):
            return str(raw["tool_name"])
    for attr in ("name", "tool_name", "function_name"):
        v = getattr(raw, attr, None)
        if v:
            return str(v)
    fn = getattr(raw, "function", None)
    if fn is not None and getattr(fn, "name", None):
        return str(fn.name)
    return "tool"


def workflow_agent_sync_stream(
    chat_history: list[dict[str, str]],
    *,
    on_done: Callable[[], None] | None = None,
    show_tool_progress: bool = True,
) -> Iterator[str]:
    """
    Sync generator for vkt.ChatResult that streams agent output token-by-token
    using Runner.run_streamed + result.stream_events().
    """
    q: queue.Queue[object] = queue.Queue()
    sentinel = object()

    loop = ensure_loop()

    async def _produce() -> None:
        call_id_to_name: dict[str, str] = {}
        try:
            agent = Agent(
                name="Workflow Assistant",
                instructions=dedent(
                    """You are a helpful assistant that creates structural engineering workflows for bridge design.
            
            STYLE RULES:
            - Be succinct and friendly - avoid over-elaboration
            - Don't aggressively propose actions - wait for user direction
            - Provide clear, concise responses
            - Only suggest next steps when explicitly asked or when clarification is needed
            - Markdown is allowed, but don't use tables; format with bold, headings, sections, and links.
            
            YOU HAVE TWO THREE ROLES:
            
            1. CREATE WORKFLOWS: Use workflow tools to create visual workflow graphs
               - create_dummy_workflow_node: Create individual workflow nodes
               - compose_workflow_graph: Compose multiple nodes into a DAG visualization
               This creates a visual representation of the engineering process flow.
            
            2. PERFORM CALCULATIONS: Use VIKTOR app tools to execute actual engineering calculations
               - generate_geometry: Generate 3D bridge geometry
               - calculate_wind_loads: Perform wind load analysis
               - calculate_structural_analysis: Perform structural analysis on bridges
               - calculate_sensitivity_analysis: Run sensitivity analysis on bridge height
               - calculate_footing_design: Design concrete footings according to ACI 318/NSR-10
               These tools call real VIKTOR applications and return actual engineering results.
            
            3. VISUALIZE DATA: Use visualization tools to display results
               - generate_plotly: Create bar plots from x and y data (agent tool, not a VIKTOR app)
               - generate_table: Create tables with optional row/column headers (agent tool, not a VIKTOR app)
               These create visualizations in the Plot and Table view panels.
               IMPORTANT: After calling generate_plotly, call show_hide_plot with action="show" to display the Plot view.
               After calling generate_table, call show_hide_table with action="show" to display the Table view.
            
            Available VIKTOR App Tools (for actual calculations):
            - generate_geometry: Generate 3D parametric truss bridge geometry (nodes, lines, members)
              URL: https://beta.viktor.ai/workspaces/4704/app/editor/2447
              Parameters: bridge_length, bridge_width, bridge_height, n_divisions, cross_section (HSS200x200x8, HSS250x250x10, HSS300x300x12, HSS350x350x16)
            
            - calculate_wind_loads: Calculate wind loads based on ASCE 7 standards
              URL: https://beta.viktor.ai/workspaces/4713/app/editor/2452
              Parameters: risk_category, wind_speed_ms, exposure_category, bridge dimensions
            
            - calculate_structural_analysis: Run structural analysis on bridge structures
              URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437
              Parameters: bridge_length, bridge_width, bridge_height, n_divisions, cross_section, load_q, wind_pressure
            
            - calculate_sensitivity_analysis: Run sensitivity analysis varying bridge height
              URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437
              Parameters: bridge_length, bridge_width, n_divisions, cross_section, load_q, wind_pressure, min_height, max_height, n_steps
            
            - calculate_footing_design: Design concrete footings according to ACI 318/NSR-10 standards
              URL: https://beta.viktor.ai/workspaces/4796/app/editor/2577
              Parameters: node_names, node_x_coords_mm, node_y_coords_mm, axial_loads_kN, moments_mx_kNm, moments_my_kNm,
                          fc_mpa (concrete strength), fy_mpa (steel yield), gamma_fill_kNm3 (fill unit weight),
                          gamma_soil_kNm3, phi_deg (soil friction angle), bearing_depths_m, bearing_capacities_kPa
              Performs two-way shear (punching), one-way shear (beam action), and bearing capacity checks.
              Iterates to find optimal (minimum weight) footing and pedestal dimensions.
            
            Available Agent Tools (local visualization, not VIKTOR apps):
            - generate_plotly: Generate bar plots for data visualization
              Parameters: x (list of floats), y (list of floats)
              Creates a Plotly bar chart displayed in the Plot view panel
            
            IMPORTANT: When creating workflow nodes, include the corresponding URL from above.
            For footing_design nodes, use: https://beta.viktor.ai/workspaces/4796/app/editor/2577
            
            Available workflow node types (for visualization with URLs):
            - geometry_generation: Define bridge geometry (bridge_length, bridge_width, bridge_height, n_divisions, cross_section)
              → Use URL: https://beta.viktor.ai/workspaces/4704/app/editor/2447
            - windload_analysis: Wind load calculations (region, wind_speed, exposure_level)
              → Use URL: https://beta.viktor.ai/workspaces/4713/app/editor/2452
            - structural_analysis: Structural analysis on bridges with load combinations
              → Use URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437
            - sensitivity_analysis: Sensitivity analysis varying bridge height
              → Use URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437
            - footing_design: Concrete footing design per ACI 318/NSR-10 (pedestal, slab, bearing checks)
              → Use URL: https://beta.viktor.ai/workspaces/4796/app/editor/2577
            
            OUTPUT NODE TYPES (local visualization tools, NO URL - displayed with dashed border):
            - plot_output: Bar chart visualization of results
              → No URL (agent tool, not a VIKTOR app)
              → Can ONLY depend on sensitivity_analysis (one dependency only)
              → Maximum ONE plot_output node per workflow
            - table_output: Table display of results  
              → No URL (agent tool, not a VIKTOR app)
              → Can depend on ANY analysis node (geometry_generation, windload_analysis, seismic_analysis, structural_analysis, sensitivity_analysis)
            
            WORKFLOW COMPOSITION RULES:
            - Build the SMALLEST workflow that satisfies the user's request (be generous with table_output nodes)
            - Only add upstream dependencies when the user explicitly asks for end-to-end calculations
           - If user asks only for "wind loads", create ONLY the windload_analysis node
            - Add dependencies (geometry, loads, etc.) ONLY when user mentions them or asks for complete analysis
            - OUTPUT NODES: plot_output and table_output have NO url field (leave it null/empty)
            
            Workflow dependency reference (use only when building full workflows):
            1. GeometryGeneration first (no dependencies)
            2. WindloadAnalysis depends on geometry_generation
            3. StructuralAnalysis depends on geometry_generation and wind load analysis
            4. SensitivityAnalysis depends on geometry_generation and wind load analysis and structural analysis for exploratory purpose
            5. FootingDesign depends on structural_analysis (uses reaction loads from structural analysis)
            6. PlotOutput depends on sensitivity_analysis ONLY (max 1 per workflow)
            7. TableOutput can depend on any node (Can be added in multiple nodes. But user can visualize just one output at the time be propositive add it in at least two node)
            
            When composing a workflow, use the compose_workflow_graph tool with all nodes
            defined together. Set proper depends_on relationships between nodes.
            
            You can either:
            - Create workflow visualizations to show the process flow
            - Execute actual calculations using VIKTOR app tools
            
            IMPORTANT: Always create the workflow first, ask for feedback to the user and then run the calculations.
           
            """
                ),
                model="gpt-5-mini",
                tools=get_tools(),
            )

            # Streamed run (no await here); events are consumed via async iterator.
            result = Runner.run_streamed(agent, input=chat_history, max_turns=20)  # type: ignore[arg-type]

            async for event in result.stream_events():
                # Token streaming from raw response delta events
                if event.type == "raw_response_event" and isinstance(
                    event.data, ResponseTextDeltaEvent
                ):
                    if event.data.delta:
                        q.put(event.data.delta)
                    continue

                if not show_tool_progress:
                    continue

                # Higher-level run item events (tool called/output, etc.)
                if event.type == "run_item_stream_event":
                    item = event.item
                    raw = getattr(item, "raw_item", None)

                    if event.name == "tool_called":
                        cid = _extract_call_id(raw)
                        tool_name = _extract_tool_name(raw)
                        if cid:
                            call_id_to_name[cid] = tool_name
                        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                        q.put(f"\n\n> ⚙️ Running **{display_name}**\n")
                        continue

                    if event.name == "tool_output":
                        cid = _extract_call_id(raw)
                        tool_name = call_id_to_name.get(cid or "", "tool")
                        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
                        q.put(f"\n> ✅ Done **{display_name}**\n\n")
                        continue

        except Exception as e:
            q.put(f"\n\n⚠️ {type(e).__name__}: {e}\n")
        finally:
            q.put(sentinel)

    asyncio.run_coroutine_threadsafe(_produce(), loop)

    def _gen() -> Iterator[str]:
        while True:
            item = q.get()
            if item is sentinel:
                break
            yield item  # type: ignore[misc]
        if on_done:
            on_done()

    return _gen()


def get_visibility(params, **kwargs):
    if not params.chat:
        entities = vkt.Storage().list(scope="entity")
        for entity in entities:
            if entity == "show_plot":
                vkt.Storage().delete("show_plot", scope="entity")
            if entity == "PlotTool":
                vkt.Storage().delete("PlotTool", scope="entity")

    try:
        out_bool = vkt.Storage().get("show_plot", scope="entity").getvalue()
        print(f"{out_bool=}")
        if out_bool == "show":
            return True
        return False
    except Exception:
        # If there is no data, then view is hidden.
        return False


def get_table_visibility(params, **kwargs):
    if not params.chat:
        entities = vkt.Storage().list(scope="entity")
        for entity in entities:
            if entity == "show_table":
                vkt.Storage().delete("show_table", scope="entity")
            if entity == "TableTool":
                vkt.Storage().delete("TableTool", scope="entity")

    try:
        out_bool = vkt.Storage().get("show_table", scope="entity").getvalue()
        print(f"{out_bool=}")
        if out_bool == "show":
            return True
        return False
    except Exception:
        # If there is no data, then view is hidden.
        return False


class Parametrization(vkt.Parametrization):
    title = vkt.Text("""# VIKTOR Bridge Workflow Agent
    
Create visual workflow graphs for bridge engineering projects! 🎨
    
**What I can do:**
- 📊 Build interactive workflow diagrams with clickable tool links
- 🔧 Execute real engineering calculations (bridge geometry, wind loads, seismic analysis, footing design)
- 🔗 Connect multiple analysis steps into complete workflows
    
""")
    chat = vkt.Chat("", method="call_llm")


class Controller(vkt.Controller):
    parametrization = Parametrization

    def call_llm(self, params, **kwargs) -> vkt.ChatResult | None:
        """Handle chat interaction with the workflow agent."""
        if not params.chat:
            return None

        messages = params.chat.get_messages()
        chat_history = [{"role": m["role"], "content": m["content"]} for m in messages]

        text_stream = workflow_agent_sync_stream(
            chat_history,
            on_done=self._update_workflow_storage,  # run after stream completes
            show_tool_progress=True,  # emoji tool status lines
        )

        return vkt.ChatResult(params.chat, text_stream)

    def _update_workflow_storage(self) -> None:
        """Scan for generated workflows and store the latest one."""
        workflows_dir = Path.cwd() / "workflow_graph" / "generated_workflows"
        if not workflows_dir.exists():
            return

        # Find the most recently modified workflow
        workflow_dirs = [d for d in workflows_dir.iterdir() if d.is_dir()]
        if not workflow_dirs:
            return

        latest_dir = max(workflow_dirs, key=lambda d: d.stat().st_mtime)
        html_path = latest_dir / "index.html"

        if html_path.exists():
            html_content = html_path.read_text(encoding="utf-8")
            data_json = json.dumps(
                {
                    "html": html_content,
                    "workflow_name": latest_dir.name,
                }
            )
            vkt.Storage().set(
                "workflow_html",
                data=vkt.File.from_data(data_json),
                scope="entity",
            )

    @vkt.WebView("Workflow Graph", width=100)
    def workflow_view(self, params, **kwargs) -> vkt.WebResult:
        """Display the generated workflow graph."""
        # Clear storage when chat is reset
        if not params.chat:
            try:
                vkt.Storage().delete("workflow_html", scope="entity")
            except Exception:
                pass

        try:
            stored_file = vkt.Storage().get("workflow_html", scope="entity")
            if stored_file:
                data_json = stored_file.getvalue_binary().decode("utf-8")
                data = json.loads(data_json)
                html_content = data.get("html", "")
                if html_content:
                    return vkt.WebResult(html=html_content)
        except Exception:
            pass

        # Default placeholder when no workflow exists
        placeholder_html = "<!DOCTYPE html><html><head><style>body { margin: 0; background-color: white; }</style></head><body></body></html>"
        return vkt.WebResult(html=placeholder_html)

    @vkt.PlotlyView("Plot Tool", width=100, visible=get_visibility)
    def plot_view(self, params, **kwargs) -> vkt.PlotlyResult:
        if not params.chat:
            try:
                vkt.Storage().delete("PlotTool", scope="entity")
            except Exception:
                pass
        try:
            raw = vkt.Storage().get("PlotTool", scope="entity").getvalue()  # str
            logger.info(f"Plot raw data: {raw}")
            tool_input = PlotTool.model_validate(json.loads(raw))
            logger.info(f"Plot tool_input: {tool_input}")

            fig = go.Figure(
                data=[
                    go.Scatter(
                        x=tool_input.x,
                        y=tool_input.y,
                        mode="lines+markers",
                        line=dict(color="blue", width=2),
                        marker=dict(color="red", size=8),
                    )
                ],
                layout=go.Layout(
                    title="Line Plot",
                    xaxis_title=tool_input.xlabel,
                    yaxis_title=tool_input.ylabel,
                ),
            )
        except Exception as e:
            logger.exception(f"Error in plot_view: {e}")
            fig = go.Figure()

        return vkt.PlotlyResult(fig.to_json())

    @vkt.TableView("Table Tool", width=100, visible=get_table_visibility)
    def table_view(self, params, **kwargs) -> vkt.TableResult:
        if not params.chat:
            try:
                vkt.Storage().delete("TableTool", scope="entity")
            except Exception:
                pass
        try:
            raw = (
                vkt.Storage()
                .get("TableTool", scope="entity")
                .getvalue_binary()
                .decode("utf-8")
            )
            logger.info(f"Table raw data: {raw}")
            tool_input = TableTool.model_validate_json(raw)
            logger.info(f"Table tool_input: {tool_input}")
            return vkt.TableResult(
                data=tool_input.data, column_headers=tool_input.column_headers
            )
        except Exception as e:
            logger.exception(f"Error in table_view: {e}")
            return vkt.TableResult([["Error", "using Tool"]])
