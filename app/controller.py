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
                name="Structural Analysis Assistant",
                instructions=dedent(
                    """You are a helpful assistant for structural engineering tasks using SAP2000 integration.

            STYLE RULES:
            - Be succinct and friendly - avoid over-elaboration
            - Don't aggressively propose actions - wait for user direction
            - Provide clear, concise responses
            - Only suggest next steps when explicitly asked or when clarification is needed
            - Markdown is allowed, but don't use tables; format with bold, headings, sections, and links.

            YOUR CAPABILITIES:

            1. SAP2000 DATA EXTRACTION
               Connect to SAP2000 via COM interface and extract model data:

               - get_support_coordinates: Extract support node coordinates and restraints
                 * Returns: Joint name, X/Y/Z coordinates (m), restraint conditions (U1-U3, R1-R3)
                 * Data stored in Viktor Storage under key: "model_support_coordinates"

               - get_reaction_loads: Extract reaction forces and moments for all load combinations
                 * Returns: F1/F2/F3 (kN), M1/M2/M3 (kN·m) for each node and load combo
                 * Data stored in Viktor Storage under key: "model_reaction_loads"

               IMPORTANT: SAP2000 must be running with a model open and configured as active API instance
               (Tools → Set as active instance for API in SAP2000).

            2. DATA DISPLAY
               Transform extracted SAP2000 data into table views:

               - display_support_coordinates_table: Show support nodes in table format
                 * Columns: Joint, X (m), Y (m), Z (m), U1, U2, U3, R1, R2, R3
                 * Automatically shows Table view panel
                 * Must run get_support_coordinates first

               - display_reaction_loads_table: Show reaction loads in flattened table
                 * Columns: Node, Load Combo, F1 (kN), F2 (kN), F3 (kN), M1 (kN·m), M2 (kN·m), M3 (kN·m)
                 * Shows all nodes × all load combinations
                 * Automatically shows Table view panel
                 * Must run get_reaction_loads first

               TYPICAL WORKFLOW:
               User: "Extract support coordinates"
               → Call get_support_coordinates
               User: "Show them in a table"
               → Call display_support_coordinates_table

            3. FOOTING DESIGN (Future Integration)
               - calculate_footing_design: Design concrete footings according to ACI 318/NSR-10
                 * URL: https://beta.viktor.ai/workspaces/4796/app/editor/2577
                 * Performs punching shear, beam shear, and bearing capacity checks
                 * Finds optimal pedestal and footing dimensions
                 * Currently uses manual input; SAP2000 integration coming soon

            4. VISUALIZATION TOOLS
               - generate_plotly: Create line/bar plots from x and y data
                 * Must call show_hide_plot with action="show" after to display

               - generate_table: Create custom tables with data and column headers
                 * Must call show_hide_table with action="show" after to display

               - show_hide_plot: Control Plot view panel visibility
               - show_hide_table: Control Table view panel visibility

            5. WORKFLOW GRAPHS (Optional)
               Create visual workflow diagrams to document engineering processes:

               - create_dummy_workflow_node: Create individual nodes
               - compose_workflow_graph: Combine nodes into DAG visualization

               Available node types for workflows:
               - sap2000_extraction: SAP2000 data extraction step (no URL - represents extraction process)
               - footing_design: Footing design per ACI 318/NSR-10
                 → URL: https://beta.viktor.ai/workspaces/4796/app/editor/2577
               - plot_output: Visualization node (no URL)
               - table_output: Table display node (no URL)

            GENERAL APPROACH:
            - Extract data from SAP2000 when requested
            - Display extracted data in tables for user review
            - Use footing design tool with extracted data (future integration)
            - Create workflow graphs to document process flow (optional)
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
    title = vkt.Text("""# VIKTOR Structural Analysis Agent

Extract and analyze data from SAP2000 models! 🏗️

**What I can do:**
- 📊 Extract support coordinates and reaction loads from SAP2000 via COM
- 📋 Display extracted data in interactive tables
- 🔧 Design concrete footings according to ACI 318/NSR-10
- 📈 Visualize data with plots and charts
- 🔗 Create workflow graphs to document processes

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
