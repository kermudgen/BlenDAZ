# SPDX-License-Identifier: GPL-3.0-or-later
"""
Bridge Test Client — remote solver testing via the Claude Bridge addon.

Talks to a running Blender instance (with Claude Bridge on port 7777) to:
- Read bone rotations and positions
- Pose bones and measure deltas
- Run solver code and capture results
- Take viewport screenshots for visual regression

Usage from Claude Code or Python:
    from scripts.bridge_test_client import BridgeClient
    client = BridgeClient()
    client.ping()
    client.get_bone_rotation("lShldrBend")
    client.screenshot("test.png")

Or run directly for a health check:
    python scripts/bridge_test_client.py
"""

import json
import os
import sys

try:
    import requests
except ImportError:
    # Fallback to urllib for environments without requests
    import urllib.request
    import urllib.error

    class _MinimalRequests:
        """Tiny requests-like wrapper around urllib."""
        class Response:
            def __init__(self, data, status):
                self._data = data
                self.status_code = status
            def json(self):
                return json.loads(self._data)

        @staticmethod
        def get(url, timeout=10):
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return _MinimalRequests.Response(resp.read(), resp.status)
            except urllib.error.URLError as e:
                raise ConnectionError(str(e))

        @staticmethod
        def post(url, json=None, timeout=10):
            data = __builtins__['__import__']('json').dumps(json).encode() if json else b''
            req = urllib.request.Request(url, data=data,
                                         headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return _MinimalRequests.Response(resp.read(), resp.status)
            except urllib.error.URLError as e:
                raise ConnectionError(str(e))

    requests = _MinimalRequests()


# ---------------------------------------------------------------------------
# Golden rule tier thresholds
# ---------------------------------------------------------------------------
class Tiers:
    T0_DEG = 0.5     # Perfect
    T1_DEG = 5.0     # Cosmetic
    T2_DEG = 15.0    # Noticeable
    T3_DEG = 15.0    # Disruptive (>= this)

    T0_MM = 1.0      # 1mm
    T1_MM = 5.0      # 5mm
    T2_MM = 15.0     # 15mm

    @staticmethod
    def classify_deg(degrees):
        if degrees < Tiers.T0_DEG: return "T0"
        if degrees < Tiers.T1_DEG: return "T1"
        if degrees < Tiers.T2_DEG: return "T2"
        return "T3"

    @staticmethod
    def classify_mm(mm):
        if mm < Tiers.T0_MM: return "T0"
        if mm < Tiers.T1_MM: return "T1"
        if mm < Tiers.T2_MM: return "T2"
        return "T3"


# ---------------------------------------------------------------------------
# Bridge Client
# ---------------------------------------------------------------------------
class BridgeClient:
    def __init__(self, host="127.0.0.1", port=7777):
        self.base_url = f"http://{host}:{port}"

    # -- Low level --------------------------------------------------------

    def ping(self):
        """Check if the bridge is reachable."""
        try:
            r = requests.get(f"{self.base_url}/ping", timeout=3)
            return r.json().get("success", False)
        except Exception:
            return False

    def execute(self, code, timeout=15):
        """Execute Python code in Blender. Returns parsed output or raises."""
        r = requests.post(self.base_url,
                          json={"action": "execute_code", "code": code},
                          timeout=timeout)
        result = r.json()
        if not result.get("success"):
            raise RuntimeError(f"Blender exec failed: {result.get('error', result.get('output', 'unknown'))}")
        return result.get("output", "")

    def execute_json(self, code, timeout=15):
        """Execute code that prints JSON, return parsed dict."""
        raw = self.execute(code, timeout)
        # The output may have trailing whitespace or newlines
        return json.loads(raw.strip())

    # -- Scene helpers ----------------------------------------------------

    def get_armature_name(self):
        """Get the active armature name."""
        return self.execute_json("""
import bpy, json
obj = bpy.context.active_object
if obj and obj.type == 'ARMATURE':
    print(json.dumps({"name": obj.name}))
else:
    print(json.dumps({"name": None}))
""")["name"]

    def get_bone_rotation(self, bone_name):
        """Get a bone's rotation quaternion [w,x,y,z]."""
        return self.execute_json(f"""
import bpy, json
arm = bpy.context.active_object
pb = arm.pose.bones.get('{bone_name}')
if pb:
    q = pb.rotation_quaternion
    print(json.dumps([q.w, q.x, q.y, q.z]))
else:
    print(json.dumps(None))
""")

    def get_bone_world_pos(self, bone_name):
        """Get a bone's world-space head position [x,y,z] from evaluated depsgraph."""
        return self.execute_json(f"""
import bpy, json
bpy.context.view_layer.update()
arm = bpy.context.active_object
dg = bpy.context.evaluated_depsgraph_get()
arm_eval = arm.evaluated_get(dg)
pb = arm_eval.pose.bones.get('{bone_name}')
if pb:
    pos = arm.matrix_world @ pb.matrix.translation
    print(json.dumps([pos.x, pos.y, pos.z]))
else:
    print(json.dumps(None))
""")

    def get_chain_state(self, bone_names):
        """Get rotations and world positions for a list of bones."""
        names_str = json.dumps(bone_names)
        return self.execute_json(f"""
import bpy, json
bpy.context.view_layer.update()
arm = bpy.context.active_object
dg = bpy.context.evaluated_depsgraph_get()
arm_eval = arm.evaluated_get(dg)
result = {{}}
for name in {names_str}:
    pb = arm.pose.bones.get(name)
    pb_eval = arm_eval.pose.bones.get(name)
    if pb and pb_eval:
        q = pb.rotation_quaternion
        pos = arm.matrix_world @ pb_eval.matrix.translation
        result[name] = {{
            "rotation": [q.w, q.x, q.y, q.z],
            "world_pos": [pos.x, pos.y, pos.z]
        }}
print(json.dumps(result))
""")

    # -- Pose manipulation ------------------------------------------------

    def reset_pose(self):
        """Reset all bones to rest pose."""
        self.execute("""
import bpy
from mathutils import Quaternion, Vector
arm = bpy.context.active_object
for pb in arm.pose.bones:
    pb.rotation_mode = 'QUATERNION'
    pb.rotation_quaternion = Quaternion()
    pb.location = Vector((0,0,0))
    pb.scale = Vector((1,1,1))
bpy.context.view_layer.update()
print("ok")
""")

    def set_bone_rotation(self, bone_name, euler_degrees):
        """Set a bone's rotation from euler degrees (x,y,z)."""
        ex, ey, ez = euler_degrees
        self.execute(f"""
import bpy, math
from mathutils import Euler
arm = bpy.context.active_object
pb = arm.pose.bones['{bone_name}']
pb.rotation_mode = 'QUATERNION'
pb.rotation_quaternion = Euler((math.radians({ex}), math.radians({ey}), math.radians({ez}))).to_quaternion()
bpy.context.view_layer.update()
print("ok")
""")

    def move_bone(self, bone_name, delta_xyz):
        """Translate a bone by delta (x,y,z) in local space."""
        dx, dy, dz = delta_xyz
        self.execute(f"""
import bpy
from mathutils import Vector
arm = bpy.context.active_object
pb = arm.pose.bones['{bone_name}']
pb.location += Vector(({dx}, {dy}, {dz}))
bpy.context.view_layer.update()
print("ok")
""")

    # -- Screenshot -------------------------------------------------------

    def screenshot(self, filepath):
        """Capture a viewport screenshot. Returns the absolute path."""
        abspath = os.path.abspath(filepath).replace("\\", "/")
        self.execute(f"""
import bpy
bpy.ops.screen.screenshot(filepath='{abspath}')
print("ok")
""")
        return abspath

    # -- Measurements -----------------------------------------------------

    def measure_rotation_delta(self, bone_name, quat_before):
        """Measure rotation delta in degrees between current and a reference quaternion."""
        qb = json.dumps(quat_before)
        return self.execute_json(f"""
import bpy, json, math
from mathutils import Quaternion
arm = bpy.context.active_object
pb = arm.pose.bones['{bone_name}']
q_now = pb.rotation_quaternion.copy()
q_ref = Quaternion({qb})
if q_now.dot(q_ref) < 0:
    q_ref = -q_ref
delta = q_now.rotation_difference(q_ref)
deg = math.degrees(delta.angle)
print(json.dumps({{"degrees": round(deg, 4), "tier": "{{}}"}}))
""".replace("{{}}", '" + ("T0" if deg < 0.5 else "T1" if deg < 5.0 else "T2" if deg < 15.0 else "T3") + "'))

    def measure_position_delta(self, bone_name, pos_before):
        """Measure position delta in mm between current and a reference position."""
        pb = json.dumps(pos_before)
        return self.execute_json(f"""
import bpy, json
from mathutils import Vector
bpy.context.view_layer.update()
arm = bpy.context.active_object
dg = bpy.context.evaluated_depsgraph_get()
arm_eval = arm.evaluated_get(dg)
pb_eval = arm_eval.pose.bones['{bone_name}']
pos_now = arm.matrix_world @ pb_eval.matrix.translation
pos_ref = Vector({pb})
delta_m = (pos_now - pos_ref).length
delta_mm = delta_m * 1000
tier = "T0" if delta_mm < 1.0 else "T1" if delta_mm < 5.0 else "T2" if delta_mm < 15.0 else "T3"
print(json.dumps({{"mm": round(delta_mm, 2), "tier": tier}}))
""")

    # -- High-level test scenarios ----------------------------------------

    def test_bake_mute_pop(self, bone_names=None):
        """Test invariant #3: bake+mute cycle should cause zero pop.

        Returns dict with per-bone position deltas and overall tier.
        """
        if bone_names is None:
            bone_names = ["lCollar", "lShldrBend", "lForearmBend", "lHand"]

        names_str = json.dumps(bone_names)
        return self.execute_json(f"""
import bpy, json, math
from mathutils import Vector

arm = bpy.context.active_object
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
arm_eval = arm.evaluated_get(dg)

bones = {names_str}

# Capture pre-bake world positions
pre = {{}}
for name in bones:
    pb_eval = arm_eval.pose.bones.get(name)
    if pb_eval:
        pre[name] = (arm.matrix_world @ pb_eval.matrix.translation).copy()

# Bake + mute (mirrors invariant #3)
for name in bones:
    pb = arm.pose.bones.get(name)
    pb_eval = arm_eval.pose.bones.get(name)
    if pb and pb_eval:
        pb.rotation_quaternion = pb_eval.rotation_quaternion.copy()
        for c in pb.constraints:
            if c.type == 'LIMIT_ROTATION':
                c.mute = True

bpy.context.view_layer.update()

# Measure post-bake positions
dg = bpy.context.evaluated_depsgraph_get()
arm_eval = arm.evaluated_get(dg)

results = {{}}
worst_tier = "T0"
for name in bones:
    if name not in pre:
        continue
    pb_eval = arm_eval.pose.bones[name]
    post = arm.matrix_world @ pb_eval.matrix.translation
    delta_mm = (post - pre[name]).length * 1000
    tier = "T0" if delta_mm < 1.0 else "T1" if delta_mm < 5.0 else "T2" if delta_mm < 15.0 else "T3"
    results[name] = {{"delta_mm": round(delta_mm, 3), "tier": tier}}
    if ["T0","T1","T2","T3"].index(tier) > ["T0","T1","T2","T3"].index(worst_tier):
        worst_tier = tier

# Restore constraints
for name in bones:
    pb = arm.pose.bones.get(name)
    if pb:
        for c in pb.constraints:
            if c.type == 'LIMIT_ROTATION':
                c.mute = False

print(json.dumps({{"bones": results, "overall_tier": worst_tier}}))
""")

    def test_pin_hold(self, pin_bone="lHand", move_bone="hip",
                      move_delta=(0, 0.1, 0)):
        """Test pin maintenance: move a bone, check if pinned bone stays put.

        Returns dict with pin drift in mm and tier.
        """
        dx, dy, dz = move_delta
        return self.execute_json(f"""
import bpy, json
from mathutils import Vector

arm = bpy.context.active_object
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
arm_eval = arm.evaluated_get(dg)

# Record pin bone position before
pin_pb = arm_eval.pose.bones['{pin_bone}']
pin_before = (arm.matrix_world @ pin_pb.matrix.translation).copy()

# Move the root bone
move_pb = arm.pose.bones['{move_bone}']
move_pb.location += Vector(({dx}, {dy}, {dz}))
bpy.context.view_layer.update()

# Read pin bone position after
dg = bpy.context.evaluated_depsgraph_get()
arm_eval = arm.evaluated_get(dg)
pin_pb = arm_eval.pose.bones['{pin_bone}']
pin_after = arm.matrix_world @ pin_pb.matrix.translation

drift_mm = (pin_after - pin_before).length * 1000
tier = "T0" if drift_mm < 1.0 else "T1" if drift_mm < 5.0 else "T2" if drift_mm < 15.0 else "T3"

# Undo the move
move_pb.location -= Vector(({dx}, {dy}, {dz}))
bpy.context.view_layer.update()

print(json.dumps({{
    "pin_bone": "{pin_bone}",
    "move_bone": "{move_bone}",
    "move_delta": [{dx}, {dy}, {dz}],
    "drift_mm": round(drift_mm, 2),
    "tier": tier,
    "pin_before": [round(v,4) for v in pin_before],
    "pin_after": [round(v,4) for v in pin_after],
}}))
""")


# ---------------------------------------------------------------------------
# CLI health check
# ---------------------------------------------------------------------------
def main():
    client = BridgeClient()

    if not client.ping():
        print("FAIL: Bridge not reachable at http://127.0.0.1:7777")
        print("  - Is Blender running?")
        print("  - Is Claude Bridge addon started? (Sidebar > Claude Bridge > Start Server)")
        sys.exit(1)

    print("Bridge connection: OK")

    arm_name = client.get_armature_name()
    if not arm_name:
        print("WARN: No active armature. Select a DAZ character.")
        sys.exit(0)

    print(f"Active armature: {arm_name}")

    # Quick chain readout
    chain = ["lCollar", "lShldrBend", "lForearmBend", "lHand"]
    state = client.get_chain_state(chain)
    print(f"\nLeft arm chain ({len(state)} bones found):")
    for name, data in state.items():
        pos = data["world_pos"]
        print(f"  {name:20s}  pos=({pos[0]:+.3f}, {pos[1]:+.3f}, {pos[2]:+.3f})")

    # Bake+mute pop test
    print("\nBake+mute pop test (invariant #3):")
    result = client.test_bake_mute_pop()
    for name, data in result["bones"].items():
        print(f"  {name:20s}  delta={data['delta_mm']:.3f}mm  {data['tier']}")
    print(f"  Overall: {result['overall_tier']}")

    # Pin hold test (without actual solver — just FK, so hand WILL drift)
    print("\nPin hold test (FK only — no solver, drift expected):")
    result = client.test_pin_hold()
    print(f"  {result['pin_bone']} drift: {result['drift_mm']:.2f}mm  {result['tier']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
