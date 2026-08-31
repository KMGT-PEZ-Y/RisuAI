param(
    [string]$SourceCharx = (Join-Path $PSScriptRoot '..\..\characters\useful-bots\roguelikePOC.charx'),
    [string]$LuaSource = (Join-Path $PSScriptRoot 'RogueLikePOC.lua'),
    [string]$OutputCharx = (Join-Path $PSScriptRoot '..\..\characters\useful-bots\roguelikePOC-stage4A.charx'),
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

$decodeMap = New-Object byte[] 256
$encodeMap = New-Object byte[] 256
for ($i = 0; $i -lt 256; $i++) {
    $decodeMap[$i] = [Convert]::ToByte($decodeMapHex.Substring($i * 2, 2), 16)
}
for ($i = 0; $i -lt 256; $i++) {
    $encodeMap[$decodeMap[$i]] = [byte]$i
}

function Decode-RisuModule([byte[]]$bytes) {
    if ($bytes.Length -lt 7 -or $bytes[0] -ne 111 -or $bytes[1] -ne 0) {
        throw 'Invalid RPack header.'
    }
    $payloadLength = [BitConverter]::ToUInt32($bytes, 2)
    if (6 + $payloadLength -gt $bytes.Length) {
        throw 'Invalid RPack payload length.'
    }
    $decoded = New-Object byte[] $payloadLength
    for ($i = 0; $i -lt $payloadLength; $i++) {
        $decoded[$i] = $decodeMap[$bytes[$i + 6]]
    }
    return [Text.Encoding]::UTF8.GetString($decoded) | ConvertFrom-Json
}

function Encode-RisuModule($moduleRoot) {
    $json = $moduleRoot | ConvertTo-Json -Depth 100 -Compress
    $payload = [Text.UTF8Encoding]::new($false).GetBytes($json)
    $result = New-Object byte[] (6 + $payload.Length + 1)
    $result[0] = 111
    $result[1] = 0
    [BitConverter]::GetBytes([uint32]$payload.Length).CopyTo($result, 2)
    for ($i = 0; $i -lt $payload.Length; $i++) {
        $result[$i + 6] = $encodeMap[$payload[$i]]
    }
    $result[$result.Length - 1] = 0
    return $result
}

$sourcePath = (Resolve-Path -LiteralPath $SourceCharx).Path
$luaPath = (Resolve-Path -LiteralPath $LuaSource).Path
$outputPath = [IO.Path]::GetFullPath($OutputCharx)

if ([IO.Path]::GetFullPath($sourcePath) -eq $outputPath) {
    throw 'OutputCharx must not overwrite SourceCharx.'
}
if (Test-Path -LiteralPath $outputPath) {
    if (-not $Force) {
        throw "Output already exists: $outputPath. Use -Force to replace it."
    }
    Remove-Item -LiteralPath $outputPath -Force
}

$tempDirectory = Join-Path ([IO.Path]::GetTempPath()) ('roguelike-stage4a-build-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($tempDirectory) | Out-Null

try {
    [IO.Compression.ZipFile]::ExtractToDirectory($sourcePath, $tempDirectory)

    $modulePath = Join-Path $tempDirectory 'module.risum'
    $moduleRoot = Decode-RisuModule ([IO.File]::ReadAllBytes($modulePath))
    if ($moduleRoot.type -ne 'risuModule' -or -not $moduleRoot.module) {
        throw 'module.risum does not contain a Risu module.'
    }

    $luaEffect = $null
    foreach ($trigger in $moduleRoot.module.trigger) {
        foreach ($effect in $trigger.effect) {
            if ($effect.type -eq 'triggerlua') {
                $luaEffect = $effect
                break
            }
        }
        if ($luaEffect) { break }
    }
    if (-not $luaEffect) {
        throw 'No triggerlua effect was found in module.risum.'
    }

    $luaEffect.code = [IO.File]::ReadAllText($luaPath, [Text.Encoding]::UTF8)
    $moduleRoot.module.name = 'RogueLikePOC Stage4A Module'
    $moduleRoot.module.description = 'SP/MP and Type-A active skill combat POC for RogueLikePOC'
    [IO.File]::WriteAllBytes($modulePath, (Encode-RisuModule $moduleRoot))

    $cardPath = Join-Path $tempDirectory 'card.json'
    $card = [IO.File]::ReadAllText($cardPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
    $card.data.name = 'RogueLikePOC Stage4A'
    $card.data.description = 'SP/MP와 단일·전체 공격형 액티브 스킬을 구현한 RogueLikePOC Stage 4-A 데모입니다.'
    $card.data.first_mes = "Stage 4-A 전투 POC입니다. 아래 패널의 시작 버튼을 누르거나 ``/rogue``를 입력하세요."
    $card.data.modification_date = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $cardJson = $card | ConvertTo-Json -Depth 100
    [IO.File]::WriteAllText($cardPath, $cardJson, [Text.UTF8Encoding]::new($false))

    $outputDirectory = Split-Path -Parent $outputPath
    if (-not (Test-Path -LiteralPath $outputDirectory)) {
        [IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
    }
    [IO.Compression.ZipFile]::CreateFromDirectory(
        $tempDirectory,
        $outputPath,
        [IO.Compression.CompressionLevel]::Optimal,
        $false
    )
}
finally {
    if (Test-Path -LiteralPath $tempDirectory) {
        Remove-Item -LiteralPath $tempDirectory -Recurse -Force
    }
}

Get-Item -LiteralPath $outputPath | Select-Object FullName, Length, LastWriteTime
