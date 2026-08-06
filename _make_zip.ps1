$files = @(
  '__init__.py',
  'blender_manifest.toml',
  'LICENSE',
  'bone_utils.py',
  'daz_bone_select.py',
  'daz_rig_manager.py',
  'daz_shared_utils.py',
  'diag_logger.py',
  'diagnose.py',
  'dsf_face_groups.py',
  'fabrik_solver.py',
  'force_register.py',
  'genesis8_limits.py',
  'ik_templates.py',
  'panel_ui.py',
  'register_only.py',
  'rotation_cache.py',
  'setup_all.py'
)
$dirs = @('poseblend', 'posebridge', 'Assets')

$zipPath = 'D:\Dev\Blender Addons\BlenDAZ\blendaz-latest.zip'
if (Test-Path $zipPath) { Remove-Item $zipPath }

$staging = 'D:\Dev\Blender Addons\BlenDAZ\_zip_staging\blendaz'
if (Test-Path 'D:\Dev\Blender Addons\BlenDAZ\_zip_staging') { Remove-Item -Recurse -Force 'D:\Dev\Blender Addons\BlenDAZ\_zip_staging' }
New-Item -ItemType Directory -Path $staging -Force | Out-Null

foreach ($f in $files) { Copy-Item $f $staging }
foreach ($d in $dirs) {
  Copy-Item -Recurse $d "$staging\$d"
}

Get-ChildItem -Path $staging -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force

Compress-Archive -Path $staging -DestinationPath $zipPath -Force
Remove-Item -Recurse -Force 'D:\Dev\Blender Addons\BlenDAZ\_zip_staging'

$size = [math]::Round((Get-Item $zipPath).Length / 1KB, 1)
Write-Host "Created: $zipPath ($size KB)"
