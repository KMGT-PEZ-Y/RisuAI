param(
    [string]$SourceCharx = (Join-Path $PSScriptRoot '..\..\characters\useful-bots\roguelikePOC-stage4A.charx'),
    [string]$LuaSource = (Join-Path $PSScriptRoot 'BattleSim.lua'),
    [string]$CssSource = (Join-Path $PSScriptRoot 'BattleSim.css'),
    [string]$OutputCharx = (Join-Path $PSScriptRoot 'BattleSim-RisuAI.charx'),
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$decodeMapHex = @(
    '2cf7848bc965fbb69faeb3032d016974'
    '1fe4a3ecee5c3421934a0f6ae262029e'
    '229cfd3cfc71c7c6ad596705706d8a44'
    '12fa24865fafd17a47cefe5063dd5106'
    '6f18e052a8099d56734cb8536cc3a00e'
    '19cf3e0d7e07326846ea48f9992eaba4'
    '49205e5535380cbcd3b1581679280a1a'
    'e1f2cdc439dba2ba6072767d95ef7fc8'
    'c0de3794bfb51481922545ace7f566a7'
    '2b365ac113e34b3ae88d831b7c27b09a'
    '42eb87aadc548e7826d25729d4b7f82f'
    '8f8975f04177c21effd81511e5049717'
    'f331d09b00d7cab44f2a3bd9b26bda5d'
    'a13f3061bd913d4ee6dfbe4d828c1d23'
    '109864f485337b9043bba988f1d6a51c'
    'f6cc6eb95b0b96edd5e9c5cb08a68040'
) -join ''
$decodeMap=New-Object byte[] 256; $encodeMap=New-Object byte[] 256
for($i=0;$i-lt 256;$i++){ $decodeMap[$i]=[Convert]::ToByte($decodeMapHex.Substring($i*2,2),16) }
for($i=0;$i-lt 256;$i++){ $encodeMap[$decodeMap[$i]]=[byte]$i }
function Decode-Module([byte[]]$bytes){
  $length=[BitConverter]::ToUInt32($bytes,2); $decoded=New-Object byte[] $length
  for($i=0;$i-lt $length;$i++){ $decoded[$i]=$decodeMap[$bytes[$i+6]] }
  [Text.Encoding]::UTF8.GetString($decoded)|ConvertFrom-Json
}
function Encode-Module($root){
  $json=$root|ConvertTo-Json -Depth 100 -Compress; $payload=[Text.UTF8Encoding]::new($false).GetBytes($json); $result=New-Object byte[] (7+$payload.Length)
  $result[0]=111;$result[1]=0;[BitConverter]::GetBytes([uint32]$payload.Length).CopyTo($result,2)
  for($i=0;$i-lt $payload.Length;$i++){ $result[$i+6]=$encodeMap[$payload[$i]] };$result
}
$source=(Resolve-Path -LiteralPath $SourceCharx).Path;$lua=(Resolve-Path -LiteralPath $LuaSource).Path;$css=(Resolve-Path -LiteralPath $CssSource).Path;$output=[IO.Path]::GetFullPath($OutputCharx)
if((Test-Path -LiteralPath $output)-and-not $Force){throw "Output exists: $output (use -Force)"}
$temp=Join-Path ([IO.Path]::GetTempPath()) ('battle-sim-'+[guid]::NewGuid().ToString('N'));[IO.Directory]::CreateDirectory($temp)|Out-Null
try{
  [IO.Compression.ZipFile]::ExtractToDirectory($source,$temp);$modulePath=Join-Path $temp 'module.risum';$root=Decode-Module ([IO.File]::ReadAllBytes($modulePath))
  $effect=$null;foreach($trigger in $root.module.trigger){foreach($candidate in $trigger.effect){if($candidate.type-eq'triggerlua'){$effect=$candidate;break}};if($effect){break}}
  if(-not $effect){
    $effect=[pscustomobject]@{type='triggerlua';code='';indent=0}
    $luaTrigger=[pscustomobject]@{comment='Round/Turn Battle Lua';type='manual';conditions=@();effect=@($effect);lowLevelAccess=$false}
    $root.module.trigger=@($root.module.trigger)+@($luaTrigger)
  }
  $effect.code=[IO.File]::ReadAllText($lua,[Text.Encoding]::UTF8)
  $root.module.name='Round Turn Battle Simulator'
  $root.module.description='Python battle_sim_poc를 독립 이식한 RisuAI Lua 전투 엔진'
  $root.module.id='4af9bb2c-16a4-4d49-90b8-cba2e39e6487'
  [IO.File]::WriteAllBytes($modulePath,(Encode-Module $root))

  $cardPath=Join-Path $temp 'card.json'
  $card=[IO.File]::ReadAllText($cardPath,[Text.Encoding]::UTF8)|ConvertFrom-Json
  $card.data.name='Round Turn Battle Simulator'
  $card.data.description='Python battle_sim_poc의 1 대 1 엔진과 38종 다중 초상화 전투 연출을 구현한 독립 RisuAI 모듈입니다.'
  $card.data.first_mes='전투 시뮬레이터입니다. 아래 패널에서 상대를 선택하거나 `/battle`을 입력하세요.'
  $card.data.creator='BattleSim POC Port'
  $card.data.character_version='1.2.0'
  $card.data.modification_date=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  if(-not $card.data.extensions.risuai){$card.data.extensions|Add-Member -NotePropertyName risuai -NotePropertyValue ([pscustomobject]@{})}
  $background=[IO.File]::ReadAllText($css,[Text.Encoding]::UTF8)
  if($card.data.extensions.risuai.psobject.Properties.Name -contains 'backgroundHTML'){$card.data.extensions.risuai.backgroundHTML=$background}
  else{$card.data.extensions.risuai|Add-Member -NotePropertyName backgroundHTML -NotePropertyValue $background}
  [IO.File]::WriteAllText($cardPath,($card|ConvertTo-Json -Depth 100),[Text.UTF8Encoding]::new($false))

  if(Test-Path -LiteralPath $output){Remove-Item -LiteralPath $output -Force}
  [IO.Compression.ZipFile]::CreateFromDirectory($temp,$output,[IO.Compression.CompressionLevel]::Optimal,$false)
}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Recurse -Force}}
Get-Item -LiteralPath $output|Select-Object FullName,Length,LastWriteTime
