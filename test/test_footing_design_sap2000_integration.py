"""Test footing design tool with SAP2000 storage integration."""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.viktor_tools.footing_design_tool import (
    calculate_footing_design_func,
    FootingDesignFlatInput,
)


# Mock SAP2000 data
MOCK_SUPPORT_COORDS = [
    {
        "Joint": "1",
        "X": 0.0,
        "Y": 0.0,
        "Z": -0.054,
        "Restraint": {"U1": 1, "U2": 1, "U3": 1, "R1": 1, "R2": 1, "R3": 1},
    },
    {
        "Joint": "4",
        "X": 0.0,
        "Y": 21.26,
        "Z": -0.054,
        "Restraint": {"U1": 1, "U2": 1, "U3": 1, "R1": 1, "R2": 1, "R3": 1},
    },
    {
        "Joint": "12",
        "X": 5.42,
        "Y": 0.0,
        "Z": -0.054,
        "Restraint": {"U1": 1, "U2": 1, "U3": 1, "R1": 1, "R2": 1, "R3": 1},
    },
]

MOCK_REACTION_LOADS = {
    "1": {
        "ULS3": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": 1.81,
            "F2": 3.55,
            "F3": -21.68,
            "M1": -0.78,
            "M2": 3.92,
            "M3": -0.03,
        },
        "ULS2": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": -9.39,
            "F2": -33.22,
            "F3": -40.75,
            "M1": 18.98,
            "M2": -36.43,
            "M3": -0.02,
        },
        "SLS1": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": 0.88,
            "F2": 1.68,
            "F3": -12.87,
            "M1": -0.37,
            "M2": 1.91,
            "M3": -0.02,
        },
    },
    "4": {
        "ULS3": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": 2.15,
            "F2": 4.22,
            "F3": -25.33,
            "M1": -0.92,
            "M2": 4.58,
            "M3": -0.04,
        },
        "ULS2": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": -10.5,
            "F2": -38.5,
            "F3": -45.2,
            "M1": 20.1,
            "M2": -39.8,
            "M3": -0.03,
        },
        "SLS1": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": 1.05,
            "F2": 2.01,
            "F3": -15.2,
            "M1": -0.44,
            "M2": 2.29,
            "M3": -0.02,
        },
    },
    "12": {
        "ULS3": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": 1.5,
            "F2": 2.8,
            "F3": -18.5,
            "M1": -0.65,
            "M2": 3.2,
            "M3": -0.02,
        },
        "ULS2": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": -8.2,
            "F2": -28.5,
            "F3": -35.8,
            "M1": 16.5,
            "M2": -31.2,
            "M3": -0.02,
        },
        "SLS1": {
            "Type": "combo",
            "StepType": "",
            "StepNum": 0.0,
            "F1": 0.72,
            "F2": 1.38,
            "F3": -11.2,
            "M1": -0.31,
            "M2": 1.58,
            "M3": -0.01,
        },
    },
}


class MockViktorFile:
    """Mock Viktor File object."""

    def __init__(self, data):
        self.data = data

    def getvalue_binary(self):
        """Return data as bytes."""
        return self.data.encode("utf-8")


class MockViktorStorage:
    """Mock Viktor Storage class."""

    def __init__(self, coords_data=None, reactions_data=None):
        self.coords_data = coords_data
        self.reactions_data = reactions_data

    def get(self, key, scope=None):
        """Mock get method."""
        if key == "model_support_coordinates":
            if self.coords_data is None:
                return None
            return MockViktorFile(json.dumps(self.coords_data))
        elif key == "model_reaction_loads":
            if self.reactions_data is None:
                return None
            return MockViktorFile(json.dumps(self.reactions_data))
        return None


class MockFootingDesignTool:
    """Mock FootingDesignTool to capture payload without calling API."""

    def __init__(self, footing_input):
        self.footing_input = footing_input
        self.payload_captured = None

    def build_payload(self):
        """Build and capture the payload."""
        # Store for inspection
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
        self.payload_captured = {
            "method_name": "download_design_results",
            "params": params,
            "poll_result": True,
        }
        return self.payload_captured

    def run_and_parse(self):
        """Mock run_and_parse - return fake success result."""
        from app.viktor_tools.footing_design_tool import (
            FootingDesignOutput,
            OptimalFootingDesign,
        )

        # Build payload for inspection
        self.build_payload()

        # Return mock successful result
        designs = []
        for coord in self.footing_input.section_node_coords.node_coords:
            designs.append(
                OptimalFootingDesign(
                    node_name=coord.node_name,
                    pedestal_size_mm=400.0,
                    pedestal_height_mm=600.0,
                    footing_B_mm=1500.0,
                    footing_L_mm=1500.0,
                    footing_h_mm=300.0,
                    foundation_depth_mm=900.0,
                    footing_area_m2=2.25,
                    governing_combo="ULS2",
                    total_weight_kN=15.5,
                    bearing_capacity_kPa=150.0,
                    max_bearing_pressure_kPa=125.0,
                )
            )

        return FootingDesignOutput(
            project_name="Test Project",
            num_nodes=len(designs),
            num_successful=len(designs),
            designs=designs,
        )


@pytest.mark.asyncio
async def test_footing_design_with_sap2000_data():
    """Test footing design with SAP2000 data loaded from storage."""

    # Create input args with default values
    input_args = {
        "fc_mpa": 28,
        "fy_mpa": 420,
        "gamma_fill_kNm3": 19.5,
        "gamma_soil_kNm3": 20,
        "phi_deg": 25,
        "bearing_depths_m": [1.0, 1.5, 2.0],
        "bearing_capacities_kPa": [100.0, 150.0, 250.0],
        "governing_load_combo": None,  # Auto-select
    }

    # Mock Viktor module and storage
    mock_vkt = MagicMock()
    mock_storage = MockViktorStorage(
        coords_data=MOCK_SUPPORT_COORDS, reactions_data=MOCK_REACTION_LOADS
    )
    mock_vkt.Storage.return_value = mock_storage

    captured_tool = None

    def mock_tool_constructor(footing_input):
        """Capture the tool instance."""
        nonlocal captured_tool
        captured_tool = MockFootingDesignTool(footing_input)
        return captured_tool

    # Patch imports and run function
    with patch.dict("sys.modules", {"viktor": mock_vkt}):
        with patch(
            "app.viktor_tools.footing_design_tool.FootingDesignTool",
            side_effect=mock_tool_constructor,
        ):
            result = await calculate_footing_design_func(None, json.dumps(input_args))

    # Verify result
    assert "✅" in result
    assert "3" in result  # 3 nodes
    assert "Footing design completed successfully" in result

    # Verify payload was built correctly
    assert captured_tool is not None
    assert captured_tool.payload_captured is not None

    payload = captured_tool.payload_captured
    params = payload["params"]

    # Check node coordinates were loaded from storage
    node_coords = params["section_node_coords"]["node_coords"]
    assert len(node_coords) == 3
    assert node_coords[0]["node_name"] == "1"
    assert node_coords[0]["x"] == 0.0
    assert node_coords[0]["y"] == 0.0
    assert node_coords[0]["z"] == -0.054

    assert node_coords[2]["node_name"] == "12"
    assert node_coords[2]["x"] == 5.42  # Corrected coordinate
    assert node_coords[2]["y"] == 0.0

    # Check node reactions were loaded and governing combo selected
    node_reactions = params["section_node_reactions"]["node_reactions"]
    assert len(node_reactions) == 3

    # Node 1 - ULS2 should be selected (F3=-40.75, highest absolute)
    node1_reaction = next(r for r in node_reactions if r["node_name"] == "1")
    assert node1_reaction["load_combo"] == "ULS2"
    assert node1_reaction["F3"] == -40.75
    assert node1_reaction["M1"] == 18.98

    # Node 4 - ULS2 should be selected (F3=-45.2, highest absolute)
    node4_reaction = next(r for r in node_reactions if r["node_name"] == "4")
    assert node4_reaction["load_combo"] == "ULS2"
    assert node4_reaction["F3"] == -45.2

    # Node 12 - ULS2 should be selected (F3=-35.8, highest absolute)
    node12_reaction = next(r for r in node_reactions if r["node_name"] == "12")
    assert node12_reaction["load_combo"] == "ULS2"
    assert node12_reaction["F3"] == -35.8

    # Check material properties
    materials = params["section_materials"]
    assert materials["fc"] == 28
    assert materials["fy"] == 420
    assert materials["gamma_fill"] == 19.5

    # Check soil properties
    soil = params["section_soil"]
    assert soil["gamma_soil"] == 20
    assert soil["phi"] == 25

    # Check bearing capacity
    bearing = params["section_bearing"]["bearing_table"]
    assert len(bearing) == 3
    assert bearing[0]["depth"] == 1.0
    assert bearing[0]["bearing_capacity"] == 100.0
    assert bearing[2]["depth"] == 2.0
    assert bearing[2]["bearing_capacity"] == 250.0

    print("\n✅ Test passed! Payload structure:")
    print(json.dumps(payload, indent=2))


@pytest.mark.asyncio
async def test_footing_design_with_specific_load_combo():
    """Test footing design with specific load combo selection."""

    input_args = {
        "fc_mpa": 30,
        "fy_mpa": 420,
        "gamma_fill_kNm3": 19.5,
        "gamma_soil_kNm3": 18,
        "phi_deg": 30,
        "bearing_depths_m": [1.0, 2.0, 3.0],
        "bearing_capacities_kPa": [150.0, 250.0, 350.0],
        "governing_load_combo": "ULS3",  # Force ULS3 for all nodes
    }

    mock_vkt = MagicMock()
    mock_storage = MockViktorStorage(
        coords_data=MOCK_SUPPORT_COORDS, reactions_data=MOCK_REACTION_LOADS
    )
    mock_vkt.Storage.return_value = mock_storage

    captured_tool = None

    def mock_tool_constructor(footing_input):
        nonlocal captured_tool
        captured_tool = MockFootingDesignTool(footing_input)
        return captured_tool

    with patch.dict("sys.modules", {"viktor": mock_vkt}):
        with patch(
            "app.viktor_tools.footing_design_tool.FootingDesignTool",
            side_effect=mock_tool_constructor,
        ):
            result = await calculate_footing_design_func(None, json.dumps(input_args))

    assert "✅" in result
    assert captured_tool is not None

    # Verify all nodes use ULS3
    node_reactions = captured_tool.payload_captured["params"]["section_node_reactions"][
        "node_reactions"
    ]
    for reaction in node_reactions:
        assert reaction["load_combo"] == "ULS3"

    # Verify material properties
    materials = captured_tool.payload_captured["params"]["section_materials"]
    assert materials["fc"] == 30

    # Verify soil properties
    soil = captured_tool.payload_captured["params"]["section_soil"]
    assert soil["gamma_soil"] == 18
    assert soil["phi"] == 30

    print("\n✅ Test passed! Specific load combo ULS3 used for all nodes")


@pytest.mark.asyncio
async def test_footing_design_missing_coordinates():
    """Test error handling when support coordinates are missing."""

    input_args = {"fc_mpa": 28}

    mock_vkt = MagicMock()
    # Storage returns None for coordinates
    mock_storage = MockViktorStorage(coords_data=None, reactions_data=None)
    mock_vkt.Storage.return_value = mock_storage

    with patch.dict("sys.modules", {"viktor": mock_vkt}):
        result = await calculate_footing_design_func(None, json.dumps(input_args))

    assert "❌" in result
    assert "support coordinates not found" in result
    assert "get_support_coordinates" in result
    assert "get_reaction_loads" in result

    print("\n✅ Test passed! Proper error message for missing coordinates")


@pytest.mark.asyncio
async def test_footing_design_missing_reactions():
    """Test error handling when reaction loads are missing."""

    input_args = {"fc_mpa": 28}

    mock_vkt = MagicMock()
    # Storage has coords but no reactions
    mock_storage = MockViktorStorage(
        coords_data=MOCK_SUPPORT_COORDS, reactions_data=None
    )
    mock_vkt.Storage.return_value = mock_storage

    with patch.dict("sys.modules", {"viktor": mock_vkt}):
        result = await calculate_footing_design_func(None, json.dumps(input_args))

    assert "❌" in result
    assert "reaction loads not found" in result
    assert "get_reaction_loads" in result

    print("\n✅ Test passed! Proper error message for missing reactions")


@pytest.mark.asyncio
async def test_footing_design_invalid_load_combo():
    """Test error handling when invalid load combo is specified."""

    input_args = {
        "fc_mpa": 28,
        "governing_load_combo": "INVALID_COMBO",  # Doesn't exist
    }

    mock_vkt = MagicMock()
    mock_storage = MockViktorStorage(
        coords_data=MOCK_SUPPORT_COORDS, reactions_data=MOCK_REACTION_LOADS
    )
    mock_vkt.Storage.return_value = mock_storage

    with patch.dict("sys.modules", {"viktor": mock_vkt}):
        result = await calculate_footing_design_func(None, json.dumps(input_args))

    assert "❌" in result
    assert "INVALID_COMBO" in result
    assert "not found" in result
    assert "Available" in result

    print("\n✅ Test passed! Proper error message for invalid load combo")


if __name__ == "__main__":
    # Run tests manually
    import asyncio

    print("=" * 80)
    print("Running Footing Design SAP2000 Integration Tests")
    print("=" * 80)

    asyncio.run(test_footing_design_with_sap2000_data())
    asyncio.run(test_footing_design_with_specific_load_combo())
    asyncio.run(test_footing_design_missing_coordinates())
    asyncio.run(test_footing_design_missing_reactions())
    asyncio.run(test_footing_design_invalid_load_combo())

    print("\n" + "=" * 80)
    print("All tests passed! ✅")
    print("=" * 80)
