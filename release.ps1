# Build the extension zip into repo/ and regenerate repo/index.json (the URL Blender reads).
# Usage: bump `version` in super_batch_render/blender_manifest.toml, run .\release.ps1, then commit and push.
param([string]$Blender = "E:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
Set-Location $PSScriptRoot

$repo = New-Item -ItemType Directory -Force "$PSScriptRoot\repo"
Remove-Item "$repo\*.zip" -ErrorAction SilentlyContinue  # one version in the index, Blender updates to it
& $Blender --command extension build --source-dir "$PSScriptRoot\super_batch_render" --output-dir $repo
if ($LASTEXITCODE) { throw "extension build failed" }
& $Blender --command extension server-generate --repo-dir $repo
if ($LASTEXITCODE) { throw "server-generate failed" }
Get-ChildItem repo
