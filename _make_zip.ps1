# Builds blendaz-latest.zip from the runtime files only.
# Dev scripts (setup_all, register_only, force_register, diagnose), orphan
# modules nothing imports (daz_rig_manager, rotation_cache, the unused
# posebridge outline generators/icons), tests, Claude session docs and the
# unreferenced Assets/ reference image are deliberately NOT shipped.
$root = $PSScriptRoot

$files = @(
  '__init__.py',
  'blender_manifest.toml',
  'LICENSE',
  'bone_utils.py',
  'daz_bone_select.py',
  'daz_shared_utils.py',
  'diag_logger.py',
  'dsf_face_groups.py',
  'fabrik_solver.py',
  'genesis8_limits.py',
  'ik_templates.py',
  'panel_ui.py'
)
$dirs = @('poseblend', 'posebridge')

# Excluded from the copied package dirs (matched against file/dir names).
$excludeNames = @(
  '*.md',
  'test_*.py',
  'QUICKSTART_TEST.py',
  'setup_posebridge.py',
  'start_posebridge.py',
  'move_posebridge_setup.py',
  'recapture_*.py',
  'extract_icon_shape.py',
  'icons.py',
  'outline_generator_body.py',
  'outline_generator_curves.py',
  'outline_generator_simple.py'
)
$excludeDirs = @('__pycache__', 'scratchpad_archive')

$zipPath = Join-Path $root 'blendaz-latest.zip'
if (Test-Path $zipPath) { Remove-Item $zipPath }

$stagingRoot = Join-Path $root '_zip_staging'
$staging = Join-Path $stagingRoot 'blendaz'
if (Test-Path $stagingRoot) { Remove-Item -Recurse -Force $stagingRoot }
New-Item -ItemType Directory -Path $staging -Force | Out-Null

foreach ($f in $files) { Copy-Item (Join-Path $root $f) $staging }
foreach ($d in $dirs) {
  Copy-Item -Recurse (Join-Path $root $d) (Join-Path $staging $d)
}

foreach ($d in $excludeDirs) {
  Get-ChildItem -Path $staging -Recurse -Directory -Filter $d | Remove-Item -Recurse -Force
}
foreach ($n in $excludeNames) {
  Get-ChildItem -Path $staging -Recurse -File -Filter $n | Remove-Item -Force
}

Compress-Archive -Path $staging -DestinationPath $zipPath -Force
Remove-Item -Recurse -Force $stagingRoot

$size = [math]::Round((Get-Item $zipPath).Length / 1KB, 1)
Write-Host "Created: $zipPath ($size KB)"
