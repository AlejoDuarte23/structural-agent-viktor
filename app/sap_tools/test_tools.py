"""Test script for SAP2000 extraction tools."""

import asyncio
import json


async def test_support_coordinates():
    """Test extracting support coordinates."""
    from app.sap_tools.get_support_coordinates_tool import get_support_coordinates_func

    print("=" * 60)
    print("Testing: Get Support Coordinates")
    print("=" * 60)

    # Prepare test arguments
    args = json.dumps({"run_analysis": True})

    # Call the tool
    result = await get_support_coordinates_func(None, args)

    print(f"\nResult:\n{result}")
    print("\n" + "=" * 60 + "\n")

    return result


async def test_reaction_loads():
    """Test extracting reaction loads."""
    from app.sap_tools.get_reaction_loads_tool import get_reaction_loads_func

    print("=" * 60)
    print("Testing: Get Reaction Loads")
    print("=" * 60)

    # Prepare test arguments
    args = json.dumps({"run_analysis": False})

    # Call the tool
    result = await get_reaction_loads_func(None, args)

    print(f"\nResult:\n{result}")
    print("\n" + "=" * 60 + "\n")

    return result


async def test_read_from_storage():
    """Test reading data from Viktor Storage."""
    try:
        import viktor as vkt

        print("=" * 60)
        print("Testing: Read from Viktor Storage")
        print("=" * 60)

        # Try to read support coordinates
        try:
            coords_file = vkt.Storage().get("model_support_coordinates", scope="entity")
            if coords_file:
                coords_data = coords_file.getvalue_binary().decode("utf-8")
                coords = json.loads(coords_data)
                print(f"\nSupport Coordinates: {len(coords)} nodes")
                if coords:
                    print(f"First node: {coords[0]}")
        except Exception as e:
            print(f"Could not read support coordinates: {e}")

        # Try to read reaction loads
        try:
            reactions_file = vkt.Storage().get("model_reaction_loads", scope="entity")
            if reactions_file:
                reactions_data = reactions_file.getvalue_binary().decode("utf-8")
                reactions = json.loads(reactions_data)
                print(f"\nReaction Loads: {len(reactions)} nodes")
                if reactions:
                    first_node = list(reactions.keys())[0]
                    print(f"First node '{first_node}': {len(reactions[first_node])} load combos")
        except Exception as e:
            print(f"Could not read reaction loads: {e}")

        print("\n" + "=" * 60 + "\n")

    except ImportError:
        print("Viktor not available - skipping storage test")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SAP2000 Tools Test Suite")
    print("=" * 60 + "\n")

    print("IMPORTANT: Before running this test, ensure:")
    print("1. SAP2000 is running")
    print("2. A model is open")
    print("3. Tools → Set as active instance for API is enabled")
    print("4. SAP2000 and Python are at the same admin level")
    print("\n" + "=" * 60 + "\n")

    input("Press ENTER to continue...")

    try:
        # Test 1: Extract support coordinates
        await test_support_coordinates()

        # Test 2: Extract reaction loads
        await test_reaction_loads()

        # Test 3: Read from storage (if running in Viktor context)
        await test_read_from_storage()

        print("✅ All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
