[CmdletBinding()]
param(
  [string]$Root,
  [long]$MaxFileBytes = 1MB
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Root)) {
  $scriptPath = $MyInvocation.MyCommand.Path
  if ([string]::IsNullOrWhiteSpace($scriptPath)) {
    throw "Unable to resolve the script path; pass -Root explicitly."
  }
  $Root = Split-Path -Parent (Split-Path -Parent $scriptPath)
}
$rootPath = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\', '/')
$allowedBinaries = @(
  "data/silent.bin",
  # Generated RGBA atlas linked into the controller overlay by bin2o.
  "data/badge_atlas.bin",
  "data/cup_hub_stadium.bin",
  "data/cup_hub_trophy.bin",
  "data/cup_hub_header_ornament.bin",
  "data/main_menu_background.bin",
  "data/main_menu_brand.bin",
  "data/main_menu_button_a.bin",
  "data/main_menu_button_b.bin",
  "data/main_menu_icons.bin",
  "data/main_menu_portrait_2player.bin",
  "data/main_menu_portrait_credits.bin",
  "data/main_menu_portrait_exhibition.bin",
  "data/main_menu_portrait_settings.bin",
  "data/switch_button_down.bin",
  "data/switch_button_l.bin",
  "data/switch_button_left.bin",
  "data/switch_button_ls.bin",
  "data/switch_button_right.bin",
  "data/switch_button_rs.bin",
  "data/switch_button_sl.bin",
  "data/switch_button_sr.bin",
  "data/switch_button_up.bin",
  "data/switch_button_x.bin",
  "data/switch_button_y.bin",
  "data/switch_button_zl.bin",
  "data/switch_button_zr.bin"
)
$allowedAssetFiles = @(
  "assets/fonts/efootball/efootballsans-bold.ttf",
  "assets/fonts/efootball/efootballsans-light.ttf",
  "assets/fonts/efootball/efootballsans-regular.ttf",
  "assets/fonts/efootball/efootballstencil-regular.ttf"
)
$allowedLargeFiles = @(
  "data/cup_hub_stadium.bin",
  "data/cup_hub_trophy.bin",
  "data/cup_hub_header_ornament.bin",
  "data/pes21_player_registry.json",
  "source/efootball_font_atlas.h",
  "source/team_select_background.h"
)
$allowedLargePrefixes = @("art/")
$allowedPlaceholders = @(
  "runtime-template/assets/responses/.donotdelete",
  "runtime-template/download/.donotdelete",
  "runtime-template/pesmobile/content/paks/.donotdelete",
  "runtime-template/ue4game/pesmobile/pesmobile/content/paks/.donotdelete",
  "runtime-template/savedata/.donotdelete"
)
$forbiddenExtensions = @(
  ".apk", ".obb", ".so", ".pak", ".cpk",
  ".nro", ".elf", ".nacp", ".nso", ".nsp", ".npdm",
  ".o", ".a", ".map", ".log", ".p12", ".pfx",
  ".dex", ".odex", ".vdex", ".zip", ".7z", ".rar",
  ".tar", ".tgz", ".gz", ".bz2", ".xz", ".bin"
)
$forbiddenDirectories = @(
  "assets", "download", "pesmobile", "ue4game", "savedata",
  "dist", "build", "logs", "offline-responses", "mesa-install"
)
$forbiddenNames = @(
  "generate-offline-responses.py", "prepare-runtime.ps1"
)
$privateKeyPattern = '-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE\s+KEY-----'
$localPathPattern = '(?i)([A-Z]:\\' + 'Users\\|/ho' +
  'me/[^/\s]+/|/mnt/[a-z]/' + 'Users/)'
$failures = [System.Collections.Generic.List[string]]::new()

$gitDirectory = Join-Path $rootPath ".git"
if (Test-Path -LiteralPath $gitDirectory) {
  $publishablePaths = @(
    & git -C $rootPath ls-files --cached --others --exclude-standard
  )
  if ($LASTEXITCODE -ne 0) {
    throw "git ls-files failed with exit code $LASTEXITCODE"
  }
  $files = @(
    foreach ($relativePath in $publishablePaths) {
      $candidate = Join-Path $rootPath $relativePath
      if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        Get-Item -LiteralPath $candidate -Force
      }
    }
  )
} else {
  $files = Get-ChildItem -LiteralPath $rootPath -Recurse -Force -File
}

foreach ($file in $files) {
  $relative = $file.FullName.Substring($rootPath.Length).TrimStart('\', '/')
  $relative = $relative.Replace('\', '/')
  $relativeLower = $relative.ToLowerInvariant()
  $parts = $relativeLower.Split('/')
  $extension = $file.Extension.ToLowerInvariant()

  if ($allowedPlaceholders -contains $relativeLower) {
    continue
  }

  $isAllowedAssetFile = $allowedAssetFiles -contains $relativeLower
  $isAllowedLargePrefix = @(
    $allowedLargePrefixes | Where-Object { $relativeLower.StartsWith($_) }
  ).Count -gt 0

  foreach ($part in $parts[0..([Math]::Max(0, $parts.Length - 2))]) {
    if ((($forbiddenDirectories -contains $part) -and -not $isAllowedAssetFile) -or
        $part -like ".codex-*") {
      $failures.Add("forbidden directory: $relative")
      break
    }
  }

  if ($forbiddenNames -contains $file.Name.ToLowerInvariant()) {
    $failures.Add("private preparation tool: $relative")
  }

  if ($forbiddenExtensions -contains $extension -and
      $allowedBinaries -notcontains $relativeLower) {
    $failures.Add("forbidden file type: $relative")
  }

  if ($file.Length -gt $MaxFileBytes -and
      $allowedBinaries -notcontains $relativeLower -and
      $allowedLargeFiles -notcontains $relativeLower -and
      -not $isAllowedLargePrefix) {
    $failures.Add("unexpected large file ($($file.Length) bytes): $relative")
  }

  if ($allowedBinaries -contains $relativeLower) {
    continue
  }

  try {
    $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction Stop
    if ($content -match $privateKeyPattern) {
      $failures.Add("private-key material: $relative")
    }
    if ($content -match $localPathPattern) {
      $failures.Add("absolute local user path: $relative")
    }
  } catch {
    $failures.Add("could not inspect file: $relative")
  }
}

if ($failures.Count -gt 0) {
  Write-Error ("Public-tree audit failed:`n - " +
    (($failures | Sort-Object -Unique) -join "`n - "))
}

Write-Host "Public-tree audit passed: $($files.Count) files checked."
