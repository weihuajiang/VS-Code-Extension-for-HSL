param(
  [string]$HamiltonRoot = 'C:\Program Files (x86)\Hamilton',
  [string]$WorkspaceRoot = 'C:\Users\admin\Documents\GitHub\PRIVATE-VS-Code-Extension-for-HSL\solutionToBlockMarkers'
)

$converter = Join-Path $HamiltonRoot 'Bin\HxCfgFilConverter.exe'
$testRoot = Join-Path $WorkspaceRoot 'binary_conversion_tests'

if (-not (Test-Path $converter)) {
  throw "HxCfgFilConverter.exe not found at: $converter"
}

New-Item -ItemType Directory -Path $testRoot -Force | Out-Null

$cases = @(
  (Join-Path $HamiltonRoot 'Methods\VisualNTR_DemoMethod\Visual_NTR_library_demo.med'),
  (Join-Path $HamiltonRoot 'Methods\GLOBAL_VENUSI_MANAGED_MATERIALS\Global_AnswerKeys\Global_Answer_Key_CH07.med'),
  (Join-Path $HamiltonRoot 'Methods\GLOBAL_VENUSI_MANAGED_MATERIALS\Global_AnswerKeys\Global_Example_Scheduled_Method_v01.med')
)

function Is-WholeFileSimpleBase64([string]$content) {
  $noWs = [regex]::Replace($content, '\s+', '')
  if ([string]::IsNullOrWhiteSpace($noWs)) {
    return $false
  }
  if (($noWs.Length % 4) -ne 0) {
    return $false
  }
  if ($noWs -notmatch '^[A-Za-z0-9+/=]+$') {
    return $false
  }
  try {
    [Convert]::FromBase64String($noWs) | Out-Null
    return $true
  }
  catch {
    return $false
  }
}

$summary = @()

foreach ($src in $cases) {
  if (-not (Test-Path $src)) {
    throw "Missing sample MED file: $src"
  }

  $name = [IO.Path]::GetFileNameWithoutExtension($src)
  $caseDir = Join-Path $testRoot $name
  New-Item -ItemType Directory -Path $caseDir -Force | Out-Null

  $orig = Join-Path $caseDir ($name + '.original.med')
  $text = Join-Path $caseDir ($name + '.converter_text.med')
  $roundtrip = Join-Path $caseDir ($name + '.roundtrip.med')
  $roundtripText = Join-Path $caseDir ($name + '.roundtrip_text.med')

  Copy-Item $src $orig -Force

  Copy-Item $src $text -Force
  & $converter /t $text | Out-Null

  Copy-Item $src $roundtrip -Force
  & $converter /t $roundtrip | Out-Null
  & $converter /b $roundtrip | Out-Null

  Copy-Item $roundtrip $roundtripText -Force
  & $converter /t $roundtripText | Out-Null

  $origHash = (Get-FileHash -Algorithm SHA256 $orig).Hash
  $roundtripHash = (Get-FileHash -Algorithm SHA256 $roundtrip).Hash

  $textContent = [IO.File]::ReadAllText($text, [Text.Encoding]::GetEncoding(28591))
  $roundtripTextContent = [IO.File]::ReadAllText($roundtripText, [Text.Encoding]::GetEncoding(28591))

  $activityMatch = [regex]::Match($textContent, 'ActivityDocument,\s*"([^"]+)"')
  $activityBase64Decodes = $false
  if ($activityMatch.Success) {
    try {
      [Convert]::FromBase64String($activityMatch.Groups[1].Value) | Out-Null
      $activityBase64Decodes = $true
    }
    catch {
      $activityBase64Decodes = $false
    }
  }

  $summary += [PSCustomObject]@{
    Case = $name
    OriginalBinarySHA256 = $origHash
    RoundtripBinarySHA256 = $roundtripHash
    BinaryRoundtripExact = ($origHash -eq $roundtripHash)
    ConverterTextStartsWithHxCfgFile = $textContent.StartsWith('HxCfgFile,3;')
    ConverterTextExactAfterRoundtrip = ($textContent -ceq $roundtripTextContent)
    WholeFileIsSimpleBase64 = (Is-WholeFileSimpleBase64 $textContent)
    ActivityDocumentFieldIsBase64 = $activityBase64Decodes
    OriginalBytes = (Get-Item $orig).Length
    TextBytes = (Get-Item $text).Length
    RoundtripBytes = (Get-Item $roundtrip).Length
  }
}

$summaryPath = Join-Path $testRoot 'final_summary.json'
$summary | ConvertTo-Json -Depth 5 | Set-Content -Path $summaryPath -Encoding utf8

Write-Host "Wrote: $summaryPath"
Get-Content $summaryPath
