
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pythoncom
import win32com.client as win32
from win32com.client import VARIANT
SAP_PROGID = "CSI.SAP2000.API.SapObject"

# -------------------- Session (attach) --------------------
class Sap2000Session:
   def __init__(self):
       self.helper = None
       self.SapObject = None
       self.SapModel = None
   def __enter__(self):
       pythoncom.CoInitialize()
       try:
           # Avoid EnsureDispatch; use late-binding to reduce gen_py variant issues
           self.helper = win32.Dispatch("SAP2000v1.Helper")
           self.SapObject = self.helper.GetObject(SAP_PROGID)
           if self.SapObject is None:
               raise RuntimeError(
                   "Could not attach. In SAP2000 use: Tools -> Set as active instance for API. "
                   "Also ensure SAP2000 and Python run with the same admin level and are 64-bit."
               )
           self.SapModel = self.SapObject.SapModel
           if self.SapModel is None:
               raise RuntimeError("Attached SapObject has SapModel=None.")
           return self
       except Exception:
           pythoncom.CoUninitialize()
           raise
   def __exit__(self, exc_type, exc, tb):
       try:
           self.SapModel = None
           self.SapObject = None
           self.helper = None
       finally:
           pythoncom.CoUninitialize()

# -------------------- Robust COM return parsing --------------------
def _parse_getnamelist_result(res: Any) -> Tuple[List[str], int]:
   """
   SAP2000 OAPI 'GetNameList' order differs across wrappers.
   We accept any of these common patterns:
     (NumberNames:int, Names:list, ret:int)
     (ret:int, NumberNames:int, Names:list)
     (NumberNames:int, ret:int, Names:list)
     (Names:list, NumberNames:int, ret:int)  (rare)
   Returns: (names, ret)
   """
   if not isinstance(res, tuple):
       raise RuntimeError(f"GetNameList returned non-tuple: {type(res)} {res}")
   ints = [v for v in res if isinstance(v, int)]
   lists = [v for v in res if isinstance(v, (list, tuple))]
   # Heuristic: ret is usually the last int or the smallest int (often 0)
   ret = None
   if ints:
       # Prefer a 0/negative/low number as ret if present
       if 0 in ints:
           ret = 0
       else:
           ret = ints[-1]
   names = None
   if lists:
       # Prefer the longest list/tuple as the names list
       names = max(lists, key=lambda x: len(x))
   if ret is None or names is None:
       raise RuntimeError(f"Could not parse GetNameList return: {res}")
   return [str(n) for n in list(names)], int(ret)

def get_all_point_names(SapModel) -> List[str]:
   # Try explicit OUT args first
   try:
       res = SapModel.PointObj.GetNameList(0, [])
       names, ret = _parse_getnamelist_result(res)
       if ret != 0:
           raise RuntimeError(f"PointObj.GetNameList failed (ret={ret})")
       return names
   except Exception:
       # Fallback: call with no args (some bindings support it)
       res = SapModel.PointObj.GetNameList()
       names, ret = _parse_getnamelist_result(res)
       if ret != 0:
           raise RuntimeError(f"PointObj.GetNameList failed (ret={ret})")
       return names

def get_all_load_combos(SapModel) -> List[str]:
   try:
       res = SapModel.RespCombo.GetNameList(0, [])
       names, ret = _parse_getnamelist_result(res)
       if ret != 0:
           raise RuntimeError(f"RespCombo.GetNameList failed (ret={ret})")
       return names
   except Exception:
       res = SapModel.RespCombo.GetNameList()
       names, ret = _parse_getnamelist_result(res)
       if ret != 0:
           raise RuntimeError(f"RespCombo.GetNameList failed (ret={ret})")
       return names

def get_all_load_cases(SapModel) -> List[str]:
   try:
       res = SapModel.LoadCases.GetNameList(0, [])
       names, ret = _parse_getnamelist_result(res)
       if ret != 0:
           raise RuntimeError(f"LoadCases.GetNameList failed (ret={ret})")
       return names
   except Exception:
       res = SapModel.LoadCases.GetNameList()
       names, ret = _parse_getnamelist_result(res)
       if ret != 0:
           raise RuntimeError(f"LoadCases.GetNameList failed (ret={ret})")
       return names

# -------------------- Geometry + supports --------------------
def get_point_coords(SapModel, point_name: str) -> Tuple[float, float, float]:
   # GetCoordCartesian returns (Z, X, Y, ret) based on observed behavior
   # The coordinate order is rotated from what we'd expect
   result = SapModel.PointObj.GetCoordCartesian(point_name, 0, 0, 0)

   if not isinstance(result, tuple) or len(result) != 4:
       raise RuntimeError(f"GetCoordCartesian returned unexpected format: {result}")

   # Unpack: API returns (z, x, y, ret) - coordinates are rotated!
   z_sap, x_sap, y_sap, ret = result

   if ret != 0:
       raise RuntimeError(f"GetCoordCartesian({point_name}) failed (ret={ret})")

   # Return in correct order: (x, y, z)
   return float(x_sap), float(y_sap), float(z_sap)

def get_point_restraint(SapModel, point_name: str) -> List[int]:
   """
   Handles common variants:
     (restraint, ret)  where restraint is 6-length array
     (ret, restraint)
   """
   try:
       res = SapModel.PointObj.GetRestraint(point_name, [0, 0, 0, 0, 0, 0])
   except Exception:
       res = SapModel.PointObj.GetRestraint(point_name)
   if not isinstance(res, tuple):
       raise RuntimeError(f"GetRestraint returned non-tuple: {type(res)} {res}")
   # Find the restraint array and the ret int
   restraint = None
   ret = None
   for v in res:
       if isinstance(v, int):
           # ret often 0/1; keep last int
           ret = v
       if isinstance(v, (list, tuple)) and len(v) == 6:
           restraint = v
   if restraint is None or ret is None:
       raise RuntimeError(f"Could not parse GetRestraint return: {res}")
   if int(ret) != 0:
       raise RuntimeError(f"GetRestraint({point_name}) failed (ret={ret})")
   return [int(v) for v in list(restraint)]

def get_support_nodes(SapModel) -> List[Dict[str, Any]]:
   supports: List[Dict[str, Any]] = []
   for pt in get_all_point_names(SapModel):
       r = get_point_restraint(SapModel, pt)
       if any(r):
           x, y, z = get_point_coords(SapModel, pt)
           supports.append(
               {
                   "Joint": pt,
                   "X": x,
                   "Y": y,
                   "Z": z,
                   "Restraint": {"U1": r[0], "U2": r[1], "U3": r[2], "R1": r[3], "R2": r[4], "R3": r[5]},
               }
           )
   return supports

# -------------------- Results (combos + reactions) --------------------
def run_analysis(SapModel) -> None:
   ret = SapModel.Analyze.RunAnalysis()
   if ret != 0:
       raise RuntimeError(f"Analyze.RunAnalysis failed (ret={ret})")

def select_results_output(SapModel, name: str) -> str:
   ret = SapModel.Results.Setup.DeselectAllCasesAndCombosForOutput()
   if ret != 0:
       raise RuntimeError(f"DeselectAllCasesAndCombosForOutput failed (ret={ret})")
   ret_case = SapModel.Results.Setup.SetCaseSelectedForOutput(name)
   if ret_case == 0:
       return "case"
   ret_combo = SapModel.Results.Setup.SetComboSelectedForOutput(name)
   if ret_combo == 0:
       return "combo"
   raise RuntimeError(f"Could not select '{name}' as case (ret={ret_case}) or combo (ret={ret_combo}).")

def get_joint_reaction_first_row(SapModel, joint_name: str) -> Dict[str, Any]:
   # ItemTypeElm: 0 = ObjectElm (for point object name)
   # With early binding (gen_py), we must pass pythoncom.Missing for output parameters
   result = SapModel.Results.JointReact(
       joint_name,
       0,  # ItemTypeElm
       pythoncom.Missing,  # NumberResults (OUT)
       pythoncom.Missing,  # Obj (OUT)
       pythoncom.Missing,  # Elm (OUT)
       pythoncom.Missing,  # LoadCase (OUT)
       pythoncom.Missing,  # StepType (OUT)
       pythoncom.Missing,  # StepNum (OUT)
       pythoncom.Missing,  # F1 (OUT)
       pythoncom.Missing,  # F2 (OUT)
       pythoncom.Missing,  # F3 (OUT)
       pythoncom.Missing,  # M1 (OUT)
       pythoncom.Missing,  # M2 (OUT)
       pythoncom.Missing   # M3 (OUT)
   )

   if not isinstance(result, tuple):
       raise RuntimeError(f"JointReact returned non-tuple: {type(result)}")

   # Actual order from debug: (ret, NumberResults, Obj, Elm, LoadCase, StepType, StepNum, F1, F2, F3, M1, M2, M3)
   # That's 13 elements: 2 ints and 11 arrays
   if len(result) != 13:
       raise RuntimeError(f"Expected 13 elements, got {len(result)}: {result}")

   (
       ret_code,
       number_results,
       obj,
       elm,
       load_case_arr,
       step_type,
       step_num,
       f1,
       f2,
       f3,
       m1,
       m2,
       m3,
   ) = result

   if ret_code != 0:
       raise RuntimeError(f"JointReact({joint_name}) failed (ret={ret_code})")

   # Return first row if available
   if not load_case_arr or len(load_case_arr) == 0:
       return {
           "ResultName": "",
           "StepType": "",
           "StepNum": 0.0,
           "F1": 0.0,
           "F2": 0.0,
           "F3": 0.0,
           "M1": 0.0,
           "M2": 0.0,
           "M3": 0.0,
       }

   i = 0
   return {
       "ResultName": str(load_case_arr[i]),
       "StepType": str(step_type[i]),
       "StepNum": float(step_num[i]),
       "F1": float(f1[i]),
       "F2": float(f2[i]),
       "F3": float(f3[i]),
       "M1": float(m1[i]),
       "M2": float(m2[i]),
       "M3": float(m3[i]),
   }

def get_support_reactions_all_combos(SapModel) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
   """
   Returns:
       - List of support nodes with coordinates
       - Dict of reactions organized by joint name, then by load combo/case
   """
   supports = get_support_nodes(SapModel)
   print(f"{len(supports)=}")

   # Get all load combinations
   names: List[str] = []
   names.extend(get_all_load_combos(SapModel))
   print(f"{names=}")

   # Organize reactions by joint, then by load combo
   reactions_by_joint: Dict[str, Dict[str, Any]] = {}

   for s in supports:
       j = s["Joint"]
       reactions_by_joint[j] = {}

   for name in names:
       print(f"Getting {name=}")
       selected_type = select_results_output(SapModel, name)
       print(f"{selected_type=}")

       for s in supports:
           j = s["Joint"]
           print(f"{j=}")
           r = get_joint_reaction_first_row(SapModel, j)
           print(f"{r=}")

           # Store reaction for this joint and load combo
           reactions_by_joint[j][name] = {
               "Type": selected_type,
               "StepType": r["StepType"],
               "StepNum": r["StepNum"],
               "F1": r["F1"],
               "F2": r["F2"],
               "F3": r["F3"],
               "M1": r["M1"],
               "M2": r["M2"],
               "M3": r["M3"],
           }

   return supports, reactions_by_joint

def save_json(payload: Dict[str, Any], out_path: str | Path) -> None:
   out_path = Path(out_path).resolve()
   out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

# -------------------- Main --------------------
if __name__ == "__main__":
   COORDS_FILE = "support_nodes_coordinates.json"
   REACTIONS_FILE = "support_reactions_by_node.json"

   with Sap2000Session() as sap:
       run_analysis(sap.SapModel)
       supports, reactions = get_support_reactions_all_combos(sap.SapModel)

       # Save support coordinates
       save_json(supports, COORDS_FILE)
       print(f"\nSupport nodes: {len(supports)}")
       print(f"Wrote coordinates to: {Path(COORDS_FILE).resolve()}")

       # Save reactions by node
       save_json(reactions, REACTIONS_FILE)
       print(f"\nReactions for {len(reactions)} nodes")
       if reactions:
           first_node = list(reactions.keys())[0]
           num_combos = len(reactions[first_node])
           print(f"Load combos/cases per node: {num_combos}")
       print(f"Wrote reactions to: {Path(REACTIONS_FILE).resolve()}")