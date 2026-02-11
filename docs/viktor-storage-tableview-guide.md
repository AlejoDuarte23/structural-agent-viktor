# Guide: Viktor Storage + TableView

This guide explains how to use **Viktor Storage** to store data from an agent tool and display it in a **TableView** within the VIKTOR Controller.

## 📋 Table of Contents

1. [System Architecture](#system-architecture)
2. [Step 1: Define the Tool (table_tool.py)](#step-1-define-the-tool)
3. [Step 2: Register the Tool (tools.py)](#step-2-register-the-tool)
4. [Step 3: Display in Controller (controller.py)](#step-3-display-in-controller)
5. [Complete Data Flow](#complete-data-flow)
6. [Key Concepts](#key-concepts)

---

## System Architecture

```
┌─────────────────┐
│   Agent (LLM)   │
│   GPT-4/Claude  │
└────────┬────────┘
         │ invokes tool
         ▼
┌─────────────────────────┐
│  table_tool.py          │
│  - display_table_func() │
│  - Validates data       │
│  - Saves to Storage     │
└────────┬────────────────┘
         │ vkt.Storage().set()
         ▼
┌─────────────────────────┐
│   VIKTOR Storage        │
│   Key: "TableTool"      │
│   Scope: "entity"       │
└────────┬────────────────┘
         │ vkt.Storage().get()
         ▼
┌─────────────────────────┐
│  controller.py          │
│  - table_view()         │
│  - Reads from Storage   │
│  - Renders TableView    │
└─────────────────────────┘
```

---

## Step 1: Define the Tool

**File**: `app/viktor_tools/table_tool.py`

### 1.1 Data Model (Pydantic)

```python
from pydantic import BaseModel, Field

class TableTool(BaseModel):
    """Arguments for a table view tool"""

    data: list[list[str | float | int]] = Field(
        ...,
        description="Table data as a list of rows, where each row is a list of values",
    )
    column_headers: list[str] = Field(
        ...,
        description="Column headers for each column"
    )
```

**Expected data structure:**
```json
{
  "data": [
    ["Node1", 15.5, 200.0],
    ["Node2", 18.2, 250.0],
    ["Node3", 12.8, 180.0]
  ],
  "column_headers": ["Node Name", "Force (kN)", "Moment (kN·m)"]
}
```

### 1.2 Tool Function

```python
import viktor as vkt
from typing import Any

async def display_table_func(ctx: Any, args: str) -> str | None:
    """Displays Table in TableView"""

    # 1. Validate and parse JSON arguments
    payload = TableTool.model_validate_json(args)
    print(f"{payload}=")

    if payload:
        # 2. Save to Viktor Storage
        vkt.Storage().set(
            "TableTool",  # ← Unique key to identify this data
            data=vkt.File.from_data(payload.model_dump_json()),  # ← Convert to JSON
            scope="entity",  # ← Persist by entity (not by user)
        )
        return "Table generated. Open the Table view panel to view it."

    return f"Validation error Incorrect Outputs {args}"
```

### 1.3 Register as FunctionTool

```python
def generate_table() -> Any:
    from agents import FunctionTool

    return FunctionTool(
        name="generate_table",
        description=(
            "Generate a table visualization. "
            "Takes data as a list of rows (each row is a list of values). "
            "Accepts column_headers for labeling columns. "
            "The table will be displayed in the Table view panel and can be downloaded as CSV."
        ),
        params_json_schema=TableTool.model_json_schema(),
        on_invoke_tool=display_table_func,
    )
```

---

## Step 2: Register the Tool

**File**: `app/tools.py`

```python
from app.viktor_tools.table_tool import generate_table, show_hide_table_tool

def get_tools() -> list[Any]:
    return [
        # ... other tools
        generate_table(),           # ← Tool to generate table
        show_hide_table_tool(),     # ← Tool to show/hide table
    ]
```

**Tool display name (optional for UI)**:
```python
TOOL_DISPLAY_NAMES: dict[str, str] = {
    "generate_table": "Generate Table",
    "show_hide_table": "Show/Hide Table",
}
```

---

## Step 3: Display in Controller

**File**: `app/controller.py`

### 3.1 Visibility Function

This function controls whether the TableView should be displayed:

```python
def get_table_visibility(params, **kwargs):
    """Controls TableView visibility"""

    # Clean storage when chat is reset
    if not params.chat:
        entities = vkt.Storage().list(scope="entity")
        for entity in entities:
            if entity == "show_table":
                vkt.Storage().delete("show_table", scope="entity")
            if entity == "TableTool":
                vkt.Storage().delete("TableTool", scope="entity")

    try:
        # Read visibility state
        out_bool = vkt.Storage().get("show_table", scope="entity").getvalue()
        print(f"{out_bool=}")
        if out_bool == "show":
            return True
        return False
    except Exception:
        # If no data, view is hidden
        return False
```

### 3.2 TableView Method

```python
from app.viktor_tools.table_tool import TableTool
import json
import logging

logger = logging.getLogger(__name__)

class Controller(vkt.Controller):
    parametrization = Parametrization

    @vkt.TableView("Table Tool", width=100, visible=get_table_visibility)
    def table_view(self, params, **kwargs) -> vkt.TableResult:
        """Display table from Viktor Storage"""

        # 1. Clean storage when chat is reset
        if not params.chat:
            try:
                vkt.Storage().delete("TableTool", scope="entity")
            except Exception:
                pass

        try:
            # 2. Read data from Viktor Storage
            raw = (
                vkt.Storage()
                .get("TableTool", scope="entity")
                .getvalue_binary()
                .decode("utf-8")
            )
            logger.info(f"Table raw data: {raw}")

            # 3. Deserialize JSON to Pydantic model
            tool_input = TableTool.model_validate_json(raw)
            logger.info(f"Table tool_input: {tool_input}")

            # 4. Return TableResult
            return vkt.TableResult(
                data=tool_input.data,
                column_headers=tool_input.column_headers
            )
        except Exception as e:
            logger.exception(f"Error in table_view: {e}")
            return vkt.TableResult([["Error", "using Tool"]])
```

---

## Complete Data Flow

### Practical Example

**1. User sends message to agent**:
```
"Show a table with footing analysis data"
```

**2. Agent invokes the tool**:
```json
{
  "data": [
    ["N1", 300, 600, 1200, 1200, 300],
    ["N2", 350, 700, 1400, 1400, 400],
    ["N3", 300, 600, 1000, 1000, 300]
  ],
  "column_headers": [
    "Node",
    "Pedestal (mm)",
    "Height (mm)",
    "Footing B (mm)",
    "Footing L (mm)",
    "Thickness (mm)"
  ]
}
```

**3. `display_table_func()` saves to Storage**:
```python
vkt.Storage().set(
    "TableTool",
    data=vkt.File.from_data(json_string),
    scope="entity"
)
```

**4. `table_view()` reads from Storage**:
```python
raw = vkt.Storage().get("TableTool", scope="entity").getvalue_binary()
tool_input = TableTool.model_validate_json(raw)
return vkt.TableResult(data=tool_input.data, column_headers=tool_input.column_headers)
```

**5. VIKTOR renders the table**:
```
┌──────┬──────────────┬────────────┬──────────────┬──────────────┬───────────────┐
│ Node │ Pedestal(mm) │ Height(mm) │ Footing B(mm)│ Footing L(mm)│ Thickness(mm) │
├──────┼──────────────┼────────────┼──────────────┼──────────────┼───────────────┤
│ N1   │ 300          │ 600        │ 1200         │ 1200         │ 300           │
│ N2   │ 350          │ 700        │ 1400         │ 1400         │ 400           │
│ N3   │ 300          │ 600        │ 1000         │ 1000         │ 300           │
└──────┴──────────────┴────────────┴──────────────┴──────────────┴───────────────┘
```

---

## Key Concepts

### 1. **Viktor Storage API**

```python
# Save data
vkt.Storage().set(
    key="TableTool",           # Unique identifier
    data=vkt.File.from_data(json_string),  # Data as File
    scope="entity"             # Persistence level
)

# Read data
file = vkt.Storage().get("TableTool", scope="entity")
raw_data = file.getvalue_binary()  # bytes
json_string = raw_data.decode("utf-8")  # str

# List keys
entities = vkt.Storage().list(scope="entity")  # ['TableTool', 'PlotTool', ...]

# Delete data
vkt.Storage().delete("TableTool", scope="entity")
```

### 2. **Storage Scopes**

| Scope | Persistence | Use Case |
|-------|------------|----------|
| `"entity"` | Per VIKTOR entity (recommended) | Data shared between users in the same entity |
| `"user"` | Per user | User-specific data |
| `"workspace"` | Per workspace | Data shared across the entire workspace |

### 3. **Pydantic Serialization**

```python
# Model → JSON string
json_string = payload.model_dump_json()

# JSON string → Model
payload = TableTool.model_validate_json(json_string)
```

### 4. **Dynamic Visibility**

The `visible` parameter in the decorator controls whether the view is shown:

```python
@vkt.TableView("Table Tool", width=100, visible=get_table_visibility)
def table_view(self, params, **kwargs):
    # ...
```

The `get_table_visibility()` function returns:
- `True` → View visible
- `False` → View hidden

---

## Control Tool: Show/Hide Table

To control visibility programmatically:

```python
class ShowHideTableArgs(BaseModel):
    action: Literal["show", "hide"] = Field(
        ...,
        description="Action to perform: 'show' to display the table view, 'hide' to hide it"
    )

async def show_hide_table_func(ctx: Any, args: str) -> str:
    """Show or hide the table view."""
    payload = ShowHideTableArgs.model_validate_json(args)
    action = payload.action

    # Save visibility state
    vkt.Storage().set(
        "show_table",
        data=vkt.File.from_data(action),  # "show" or "hide"
        scope="entity"
    )
    return f"Table Visibility State Changed to {action}"
```

**Usage from agent**:
```python
# After generating the table
await show_hide_table_func(ctx, '{"action": "show"}')
```

---

## Advantages of this Pattern

✅ **Separation of concerns**: Tool saves, Controller reads
✅ **Persistence**: Data survives between calls
✅ **Controlled visibility**: Programmatic show/hide
✅ **Type safety**: Pydantic validates structure
✅ **Automatic cleanup**: Storage is cleaned when chat resets

---

## Analogous Pattern: PlotlyView

The same pattern is used for `PlotlyView`:

```python
# Tool saves plot data
vkt.Storage().set("PlotTool", data=vkt.File.from_data(json), scope="entity")

# Controller reads and renders
@vkt.PlotlyView("Plot Tool", width=100, visible=get_visibility)
def plot_view(self, params, **kwargs) -> vkt.PlotlyResult:
    raw = vkt.Storage().get("PlotTool", scope="entity").getvalue()
    tool_input = PlotTool.model_validate_json(raw)
    fig = go.Figure(...)  # Create chart
    return vkt.PlotlyResult(fig.to_json())
```

---

## References

- **Viktor Storage Docs**: https://docs.viktor.ai/docs/storage
- **Viktor TableView**: https://docs.viktor.ai/docs/views/table-view
- **Pydantic Models**: https://docs.pydantic.dev/

---

**Author**: Structural Agent Team
**Last updated**: 2026-02-08
