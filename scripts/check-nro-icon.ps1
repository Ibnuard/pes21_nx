param(
  [Parameter(Mandatory = $true)][string]$IconPath,
  [string]$NroPath = ""
)

$ErrorActionPreference = "Stop"
$iconFile = (Resolve-Path -LiteralPath $IconPath).Path
$iconBytes = [IO.File]::ReadAllBytes($iconFile)
if ($iconBytes.Length -lt 4 -or $iconBytes[0] -ne 255 -or $iconBytes[1] -ne 216) {
  throw "NRO icon must be a JPEG: $iconFile"
}
Add-Type -AssemblyName System.Drawing
$iconImage = [Drawing.Image]::FromFile($iconFile)
try {
  if ($iconImage.Width -ne 256 -or $iconImage.Height -ne 256 -or
      $iconImage.RawFormat.Guid -ne [Drawing.Imaging.ImageFormat]::Jpeg.Guid) {
    throw "NRO icon must be a 256x256 JPEG: $iconFile"
  }
} finally {
  $iconImage.Dispose()
}

if ($NroPath) {
  $nro = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $NroPath).Path)
  if ($nro.Length -lt 0x1c -or [Text.Encoding]::ASCII.GetString($nro, 0x10, 4) -ne 'NRO0') {
    throw "Invalid NRO header."
  }
  [long]$assetOffset = [BitConverter]::ToUInt32($nro, 0x18)
  if ($assetOffset -lt 0x38 -or $assetOffset + 0x38 -gt $nro.Length -or
      [Text.Encoding]::ASCII.GetString($nro, [int]$assetOffset, 4) -ne 'ASET') {
    throw "Invalid NRO ASET header."
  }
  [ulong]$relative = [BitConverter]::ToUInt64($nro, [int]$assetOffset + 8)
  [ulong]$length = [BitConverter]::ToUInt64($nro, [int]$assetOffset + 16)
  if ($length -ne $iconBytes.Length -or $relative -lt 0x38 -or
      $relative -gt ($nro.Length - $assetOffset) -or
      $length -gt ($nro.Length - $assetOffset - $relative)) {
    throw "Missing, invalid, or different NRO icon."
  }
  $embedded = New-Object byte[] $iconBytes.Length
  [Array]::Copy($nro, [long]($assetOffset + $relative), $embedded, 0, $embedded.Length)
  if ([Convert]::ToBase64String($embedded) -cne [Convert]::ToBase64String($iconBytes)) {
    throw "Embedded NRO icon differs from icon.jpg."
  }
  Write-Output "NRO icon verified byte-for-byte: $NroPath"
} else {
  Write-Output "NRO icon validated: JPEG 256x256 ($iconFile)"
}
