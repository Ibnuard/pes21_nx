$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskButtons = @{
  x = 'X_Button.png'; y = 'Y_Button.png'; l = 'L_Button.png'
  zl = 'ZL_Button.png'; zr = 'ZR_Button.png'
  sl = 'SL_Button.png'; sr = 'SR_Button.png'
  ls = 'LeftStick_Default_CORE.png'; rs = 'RightStick_Default_CORE.png'
  right = 'Directional_Button_Right.png'
  up = 'Directional_Button_Up.png'
  down = 'Directional_Button_Down.png'
  left = 'Directional_Button_Left.png'
}
foreach ($key in $taskButtons.Keys) {
  Copy-Item -LiteralPath (Join-Path $taskRoot "art/SwitchButton/$($taskButtons[$key])") -Destination (Join-Path $taskRoot "data/switch_button_$key.bin")
}
