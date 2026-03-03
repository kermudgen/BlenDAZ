# Multi-Character Registration - Testing Guide

Flow: register_only → scan → register → activate

---

## Prerequisites
- Blender open with one or more Genesis 8/9 characters (mesh + armature)
- Character(s) in **T-pose**
- **System Console open** (Window > Toggle System Console)

---

## STEP 1: Register Only (N-Panel Setup)

Run `register_only.py` to get the N-Panel without any character setup.

1. Open **Text Editor** in Blender
2. Open: `D:\Dev\BlenDAZ\register_only.py`
3. Click **Run Script**

**Expected console output:**
```
======================================================================
  BLENDAZ REGISTER ONLY
======================================================================
--- Step 1: daz_bone_select ---
  OK — daz_bone_select registered
--- Step 2: PoseBridge ---
  OK — PoseBridge registered (N-panel available)
  OK — Draw handler registered
--- Step 3: PoseBlend ---
  OK — PoseBlend registered
======================================================================
  REGISTER COMPLETE
======================================================================
```

**Verify:**
- [ ] No errors in console
- [ ] Open N-Panel (press **N**) → **DAZ** tab exists
- [ ] BlenDAZ root panel shows:
  ```
  [BlenDAZ]                    (toggle button)

  [Scan for Characters]

  No characters registered
  Click 'Scan' to find DAZ rigs
  ```
- [ ] No characters listed (registry is empty)
- [ ] BlenDAZ Setup sub-panel is visible (collapsed)

---

## STEP 2: Scan for Characters

1. In the DAZ tab, click **"Scan for Characters"**
2. Check the info bar at bottom of Blender

**Expected info bar:**
```
Found N DAZ rig(s): ArmatureName (unregistered), ...
```

**Expected N-Panel after scan:**
```
[BlenDAZ]

Unregistered:
  ArmatureName  [Register]
  (more if multiple characters)

[Scan for Characters]
```

**Verify:**
- [ ] All DAZ rigs found (check count matches your scene)
- [ ] Each rig shows as "unregistered" in info bar
- [ ] "Unregistered:" section appears in panel
- [ ] Each rig has a **Register** button next to it
- [ ] No "Characters:" section yet (nothing registered)

---

## STEP 3: Register First Character

1. Click **"Register"** next to the character you want to set up

**Check System Console for:**
```
============================================================
  REGISTERING CHARACTER: ArmatureName (tag: ...)
============================================================
  Body mesh: ArmatureName Mesh
  Z-offset: -50.0m

--- Generating outline from ArmatureName Mesh ---
  ...
  OK — Outline generated: PB_Outline_...
  Moved 'PB_Outline_...': Z ... -> -50.0
  Moved '..._LineArt_Copy': Z ... -> -50.0
  Moved 'PB_Camera_Body_...': Z ... -> -49.3
  Moved 'PB_Light_...': Z ... -> -49.3
  OK — Body control points: N
  ...
  Registered character [0]: ArmatureName
```

**Expected N-Panel after registration:**
```
[BlenDAZ]

Characters:
  (o) ArmatureName             (active)

(any remaining unregistered rigs with Register buttons)

[Scan for Characters]
```

**Verify:**
- [ ] Console shows outline generation succeeded
- [ ] Console shows objects moved to Z=-50
- [ ] Console shows control points captured
- [ ] "Registered character [0]" in console
- [ ] N-Panel shows character under "Characters:" with filled radio
- [ ] Character removed from "Unregistered:" list

**Visual check:**
- [ ] Mannequin NOT overlapping main character (moved to Z=-50)
- [ ] In Outliner: select mannequin → Properties → Transform → Z ≈ -50

**If Z-offset is NOT working (mannequin overlaps character):**
Copy the full console output from `REGISTERING CHARACTER` through
`Registered character` and report it. STOP here until fixed.

---

## STEP 4: Register Second Character (if applicable)

If you have a second DAZ rig in the scene:

1. It should still appear under "Unregistered:" in the N-Panel
   (if not, click **Scan for Characters** again)
2. Click **"Register"** next to the second rig

**Verify:**
- [ ] Z-offset is **-55.0m** (5m below first character)
- [ ] Console shows "Registered character [1]"
- [ ] N-Panel shows both characters under "Characters:"
- [ ] Second character is now active (filled radio)
- [ ] "Unregistered:" section gone (all registered)

---

## STEP 5: Activate (Start Touch)

1. In N-Panel, click the **BlenDAZ** toggle button
   (or it may already be active from registration)

**Verify:**
- [ ] BlenDAZ button shows as pressed/depressed
- [ ] Hover over bones shows highlights/tooltips
- [ ] Click-drag on bones rotates them

---

## STEP 6: Test Character Switching

### Via N-Panel:
1. Click the inactive character name under "Characters:"

**Verify:**
- [ ] Radio icons swap
- [ ] Active armature changes
- [ ] Bone hover works on the new character

### Via Mesh Click (with Touch active):
1. Click on the other character's body mesh in viewport

**Verify:**
- [ ] BlenDAZ switches to that character's rig
- [ ] Bone hover/selection works on the switched character
- [ ] Click back on first character's mesh switches back

---

## STEP 7: PoseBridge Panel Views

1. Open PoseBridge section in N-Panel
2. Click **Body** / **Hands** / **Face** buttons

**Verify:**
- [ ] Camera switches to per-character camera (not legacy names)
- [ ] Body view shows mannequin + outline
- [ ] No missing camera errors

---

## Troubleshooting

**N-Panel doesn't appear after register_only.py:**
Check console for registration errors. Ensure paths in script are correct.

**Scan finds no characters:**
Armatures need DAZ marker bones (`lPectoral`, `rPectoral`, `lCollar`, `rCollar`).

**Register button fails:**
Check System Console for full traceback. Common: no body mesh found as
child of armature.

**Z-offset not working:**
Copy full console output from the registration step and report it.

**Switch doesn't work via mesh click:**
Touch must be active (BlenDAZ button pressed). The mesh must have an
Armature modifier pointing to a registered armature.

---

**Last Updated:** 2026-02-26
