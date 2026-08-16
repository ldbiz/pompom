$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    uv run pyinstaller --noconfirm --clean pompom.spec

    if ($env:ISCC_PATH -and (Test-Path $env:ISCC_PATH)) {
        $isccPath = $env:ISCC_PATH
    }
    elseif ($iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue) {
        $isccPath = $iscc.Source
    }
    else {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe"
        )
        $isccPath = $candidates |
            Where-Object { $_ -and (Test-Path $_) } |
            Select-Object -First 1
    }

    if (-not $isccPath) {
        throw "Inno Setup 7 was not found. Install it from https://jrsoftware.org/isinfo.php."
    }

    & $isccPath "installer\pompom.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
