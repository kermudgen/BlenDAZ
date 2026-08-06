# SPDX-License-Identifier: GPL-3.0-or-later
"""
Bridge Workflow — end-to-end edit/reload/test cycle via Claude Bridge.

Closes the loop: Claude Code edits solver code → reloads addon in live
Blender → runs test scenarios → captures screenshots + metrics → reports
tier results. No manual Blender interaction needed.

Usage from Claude Code:
    from scripts.bridge_workflow import Workflow
    wf = Workflow()
    wf.reload_addon()                    # Hot-reload after code change
    wf.run_solver_test("arm_drag")       # Run a test scenario
    wf.run_all_tests()                   # Full battery
    wf.report()                          # Print summary

Or run directly:
    python scripts/bridge_workflow.py [--reload] [--screenshot-dir PATH]
"""

import os
import sys
import time
import argparse

# Ensure we can import the bridge client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.bridge_test_client import BridgeClient, Tiers


SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               "tests", "fixtures", "screenshots")


class Workflow:
    def __init__(self, host="127.0.0.1", port=7777, screenshot_dir=None):
        self.client = BridgeClient(host, port)
        self.screenshot_dir = screenshot_dir or SCREENSHOT_DIR
        self.results = []

        if not self.client.ping():
            raise ConnectionError(
                "Bridge not reachable. Is Blender running with Claude Bridge started?"
            )

    # -----------------------------------------------------------------
    # Addon reload
    # -----------------------------------------------------------------
    def reload_addon(self):
        """Hot-reload the BlenDAZ addon without restarting Blender.

        Reloads fabrik_solver, daz_bone_select, and all sub-modules.
        Handles both Blender 5.0 extension namespace (bl_ext.user_default.blendaz)
        and legacy addon namespace (blendaz).
        Returns True if successful.
        """
        result = self.client.execute("""
import bpy, sys, importlib

# --- Detect module namespace ---
# Blender 5.0 extensions: bl_ext.user_default.blendaz
# Legacy addons: blendaz
PREFIX = None
for prefix in ['bl_ext.user_default.blendaz', 'blendaz']:
    if prefix in sys.modules:
        PREFIX = prefix
        break

if not PREFIX:
    print("WARN: blendaz not found in sys.modules")
    print("RELOAD_FAIL")
else:
    print(f"Using namespace: {PREFIX}")

    # --- Purge stale draw handlers ---
    try:
        dbs = sys.modules.get(f'{PREFIX}.daz_bone_select')
        if dbs and hasattr(dbs, 'VIEW3D_OT_daz_bone_select'):
            cls = dbs.VIEW3D_OT_daz_bone_select
            if hasattr(cls, '_active_draw_handlers'):
                for h in list(cls._active_draw_handlers):
                    try:
                        bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
                    except:
                        pass
                cls._active_draw_handlers.clear()
                print("Purged draw handlers")
    except Exception as e:
        print(f"Handler purge skipped: {e}")

    # --- Reload all blendaz modules ---
    blendaz_modules = [k for k in sys.modules if k == PREFIX or k.startswith(PREFIX + '.')]
    print(f"Reloading {len(blendaz_modules)} modules...")

    # Sort so parent modules reload before children
    blendaz_modules.sort(key=lambda x: x.count('.'))

    for mod_name in blendaz_modules:
        try:
            mod = sys.modules[mod_name]
            importlib.reload(mod)
        except Exception as e:
            print(f"  WARN: {mod_name}: {e}")

    # --- Re-register the extension ---
    try:
        root = sys.modules[PREFIX]
        if hasattr(root, 'unregister'):
            try:
                root.unregister()
            except:
                pass
        if hasattr(root, 'register'):
            root.register()
        print("Re-registered blendaz extension")
    except Exception as e:
        print(f"Registration: {e}")

    print("RELOAD_OK")
""", timeout=30)
        success = "RELOAD_OK" in result
        if success:
            print("Addon reloaded successfully")
        else:
            print(f"Reload may have issues:\n{result}")
        return success

    def reload_solver_only(self):
        """Lightweight reload — just fabrik_solver module.

        Faster than full reload when only tweaking solver parameters.
        """
        result = self.client.execute("""
import sys, importlib
for prefix in ['bl_ext.user_default.blendaz', 'blendaz']:
    mod = sys.modules.get(f'{prefix}.fabrik_solver')
    if mod:
        importlib.reload(mod)
        print("RELOAD_OK")
        break
else:
    print("WARN: fabrik_solver not in sys.modules")
""")
        return "RELOAD_OK" in result

    # -----------------------------------------------------------------
    # Debug overlay
    # -----------------------------------------------------------------
    def enable_overlay(self):
        """Enable the FABRIK debug overlay in the live Blender session.

        Loads scripts/debug_overlay.py and sets _FABRIK_DEBUG_OVERLAY = True.
        The overlay will draw chain state during the next FABRIK drag.
        """
        result = self.client.execute("""
import sys, os, importlib

# Add dev scripts dir to path for debug_overlay import
dev_scripts = 'D:\Dev\Blender Addons\BlenDAZ/scripts'
if dev_scripts not in sys.path:
    sys.path.insert(0, dev_scripts)

# Also try the extension's own scripts dir
for prefix in ['bl_ext.user_default.blendaz', 'blendaz']:
    root = sys.modules.get(prefix)
    if root and hasattr(root, '__file__'):
        ext_scripts = os.path.join(os.path.dirname(root.__file__), 'scripts')
        if ext_scripts not in sys.path:
            sys.path.insert(0, ext_scripts)
        break

# Load/reload the overlay module
try:
    if 'debug_overlay' in sys.modules:
        importlib.reload(sys.modules['debug_overlay'])
        debug_overlay = sys.modules['debug_overlay']
    else:
        import debug_overlay
    debug_overlay.register()
    print("Overlay module loaded and registered")
except ImportError as e:
    print(f"WARN: Could not load debug_overlay: {e}")

# Set the flag and inject the module reference into daz_bone_select
dbs = None
for prefix in ['bl_ext.user_default.blendaz', 'blendaz']:
    dbs = sys.modules.get(f'{prefix}.daz_bone_select')
    if dbs:
        break

if dbs:
    dbs._FABRIK_DEBUG_OVERLAY = True
    dbs._debug_overlay = sys.modules.get('debug_overlay')
    if dbs._debug_overlay:
        print("OVERLAY_OK")
    else:
        print("WARN: overlay module not available for injection")
else:
    print("WARN: daz_bone_select not found in sys.modules")
""")
        success = "OVERLAY_OK" in result
        if success:
            print("Debug overlay enabled — will draw during next FABRIK drag")
        else:
            print(f"Overlay setup issue:\n{result}")
        return success

    def disable_overlay(self):
        """Disable the FABRIK debug overlay."""
        result = self.client.execute("""
import sys
dbs = None
for prefix in ['bl_ext.user_default.blendaz', 'blendaz']:
    dbs = sys.modules.get(f'{prefix}.daz_bone_select')
    if dbs:
        break
if dbs:
    dbs._FABRIK_DEBUG_OVERLAY = False
overlay = sys.modules.get('debug_overlay')
if overlay:
    overlay.clear()
print("OVERLAY_OFF")
""")
        success = "OVERLAY_OFF" in result
        if success:
            print("Debug overlay disabled")
        return success

    # -----------------------------------------------------------------
    # Screenshots
    # -----------------------------------------------------------------
    def screenshot(self, name="test"):
        """Capture viewport screenshot. Returns filepath."""
        os.makedirs(self.screenshot_dir, exist_ok=True)
        ts = time.strftime("%H%M%S")
        filepath = os.path.join(self.screenshot_dir, f"{name}_{ts}.png")
        self.client.screenshot(filepath)
        return filepath

    # -----------------------------------------------------------------
    # Test scenarios
    # -----------------------------------------------------------------
    def run_solver_test(self, scenario="arm_drag"):
        """Run a named test scenario and return results.

        Available scenarios:
            arm_drag        — Drag forearm with pinned hand, measure pin drift
            bake_mute_pop   — Test invariant #3 (bake+mute cycle)
            hip_translate   — Translate hip with pinned hand, measure drift
            euler_clamp     — Test invariant #8 (clamp matches constraint)
        """
        if scenario == "arm_drag":
            return self._test_arm_drag()
        elif scenario == "bake_mute_pop":
            return self._test_bake_mute_pop()
        elif scenario == "hip_translate":
            return self._test_hip_translate()
        elif scenario == "euler_clamp":
            return self._test_euler_clamp()
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

    def run_all_tests(self, with_screenshots=False):
        """Run all test scenarios. Returns list of results."""
        self.results = []
        scenarios = ["bake_mute_pop", "arm_drag", "hip_translate", "euler_clamp"]

        self.client.reset_pose()

        for name in scenarios:
            try:
                if with_screenshots:
                    self.screenshot(f"{name}_before")

                result = self.run_solver_test(name)
                result["scenario"] = name

                if with_screenshots:
                    self.screenshot(f"{name}_after")

                self.results.append(result)
                self.client.reset_pose()
            except Exception as e:
                self.results.append({
                    "scenario": name,
                    "status": "ERROR",
                    "error": str(e),
                })

        return self.results

    def report(self):
        """Print a summary of test results."""
        if not self.results:
            print("No results. Run run_all_tests() first.")
            return

        print(f"\n{'='*60}")
        print(f"BlenDAZ Solver Test Report")
        print(f"{'='*60}")

        worst_tier = "T0"
        tier_order = ["T0", "T1", "T2", "T3"]

        for r in self.results:
            name = r.get("scenario", "?")
            status = r.get("status", "OK")
            tier = r.get("tier", "?")

            if status == "ERROR":
                print(f"  {name:25s}  ERROR: {r.get('error', '?')}")
                worst_tier = "T3"
                continue

            detail = r.get("detail", "")
            print(f"  {name:25s}  {tier:4s}  {detail}")

            if tier in tier_order and tier_order.index(tier) > tier_order.index(worst_tier):
                worst_tier = tier

        print(f"{'='*60}")
        print(f"  Overall: {worst_tier}")
        if worst_tier in ("T0", "T1"):
            print(f"  Verdict: SHIPPABLE")
        elif worst_tier == "T2":
            print(f"  Verdict: NEEDS SIGN-OFF")
        else:
            print(f"  Verdict: NOT SHIPPABLE")
        print(f"{'='*60}\n")

    # -----------------------------------------------------------------
    # Individual test implementations
    # -----------------------------------------------------------------
    def _test_bake_mute_pop(self):
        """Invariant #3: bake+mute cycle zero pop."""
        result = self.client.test_bake_mute_pop()
        worst = result["overall_tier"]
        max_delta = max(
            (b["delta_mm"] for b in result["bones"].values()), default=0
        )
        return {
            "status": "OK",
            "tier": worst,
            "detail": f"max delta {max_delta:.3f}mm",
            "data": result,
        }

    def _test_arm_drag(self):
        """Simulate arm drag: rotate shoulder, measure hand pin drift."""
        # Get hand position before
        hand_before = self.client.get_bone_world_pos("lHand")
        if hand_before is None:
            return {"status": "ERROR", "error": "lHand not found", "tier": "?"}

        # Rotate shoulder (simulates a drag)
        self.client.set_bone_rotation("lShldrBend", (30, 0, -20))

        # Measure hand drift
        result = self.client.measure_position_delta("lHand", hand_before)

        self.client.reset_pose()

        return {
            "status": "OK",
            "tier": result["tier"],
            "detail": f"hand drift {result['mm']:.2f}mm after shoulder 30° drag",
            "data": result,
        }

    def _test_hip_translate(self):
        """Translate hip, measure hand pin drift (the core pin test)."""
        hand_before = self.client.get_bone_world_pos("lHand")
        if hand_before is None:
            return {"status": "ERROR", "error": "lHand not found", "tier": "?"}

        # Move hip forward 10cm (significant translation)
        self.client.move_bone("hip", (0, 0.1, 0))

        result = self.client.measure_position_delta("lHand", hand_before)

        self.client.reset_pose()

        return {
            "status": "OK",
            "tier": result["tier"],
            "detail": f"hand drift {result['mm']:.2f}mm after hip 10cm translate",
            "data": result,
        }

    def _test_euler_clamp(self):
        """Invariant #8: euler clamp matches Blender's LIMIT_ROTATION."""
        result = self.client.execute_json("""
import bpy, json, math
from mathutils import Euler, Quaternion

arm = bpy.context.active_object
bone_name = 'lShldrBend'
pb = arm.pose.bones.get(bone_name)

if not pb:
    print(json.dumps({"error": "bone not found"}))
else:
    limit_c = None
    for c in pb.constraints:
        if c.type == 'LIMIT_ROTATION':
            limit_c = c
            break

    if not limit_c:
        print(json.dumps({"error": "no LIMIT_ROTATION constraint"}))
    else:
        # Set a rotation that exceeds limits
        pb.rotation_mode = 'QUATERNION'
        test_euler = Euler((math.radians(80), math.radians(50), math.radians(-80)))
        pb.rotation_quaternion = test_euler.to_quaternion()

        # Manually clamp (our Step 4b)
        euler = pb.rotation_quaternion.to_euler('XYZ')
        if limit_c.use_limit_x:
            euler.x = max(limit_c.min_x, min(limit_c.max_x, euler.x))
        if limit_c.use_limit_y:
            euler.y = max(limit_c.min_y, min(limit_c.max_y, euler.y))
        if limit_c.use_limit_z:
            euler.z = max(limit_c.min_z, min(limit_c.max_z, euler.z))
        clamped = euler.to_quaternion()
        pb.rotation_quaternion = clamped

        # Let Blender apply constraint
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        arm_eval = arm.evaluated_get(dg)
        pb_eval = arm_eval.pose.bones[bone_name]
        blender_rot = pb_eval.rotation_quaternion.copy()

        if clamped.dot(blender_rot) < 0:
            blender_rot = -blender_rot
        delta = clamped.rotation_difference(blender_rot)
        deg = math.degrees(delta.angle)
        tier = "T0" if deg < 0.5 else "T1" if deg < 5.0 else "T2" if deg < 15.0 else "T3"

        # Reset
        pb.rotation_quaternion = Quaternion()
        bpy.context.view_layer.update()

        print(json.dumps({"degrees": round(deg, 4), "tier": tier}))
""")

        if "error" in result:
            return {"status": "ERROR", "error": result["error"], "tier": "?"}

        return {
            "status": "OK",
            "tier": result["tier"],
            "detail": f"clamp delta {result['degrees']:.4f}°",
            "data": result,
        }


# -----------------------------------------------------------------
# CLI
# -----------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="BlenDAZ bridge workflow")
    parser.add_argument("--reload", action="store_true", help="Reload addon before testing")
    parser.add_argument("--screenshots", action="store_true", help="Capture before/after screenshots")
    parser.add_argument("--screenshot-dir", default=None, help="Screenshot output directory")
    parser.add_argument("--scenario", default=None, help="Run a single scenario instead of all")
    args = parser.parse_args()

    wf = Workflow(screenshot_dir=args.screenshot_dir)

    if args.reload:
        print("Reloading addon...")
        wf.reload_addon()
        print()

    if args.scenario:
        print(f"Running scenario: {args.scenario}")
        result = wf.run_solver_test(args.scenario)
        result["scenario"] = args.scenario
        wf.results = [result]
    else:
        print("Running all tests...")
        wf.run_all_tests(with_screenshots=args.screenshots)

    wf.report()


if __name__ == "__main__":
    main()
