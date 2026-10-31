param([string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$pythonExe = Join-Path $workspace '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Create .venv and install the runtime and packaging requirements first. See INSTALLER.md.' }
if (-not $Compiler) {
    $candidates = @((Join-Path $workspace 'build\tools\inno\ISCC.exe'),
                    (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
                    (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'))
    $Compiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler)) { throw 'Inno Setup 7 ISCC.exe is required. Pass -Compiler or see INSTALLER.md.' }
$buildId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$buildRoot = Join-Path $workspace "build\desktop\$buildId"
$outputDirectory = Join-Path $workspace 'dist'
$bundle = Join-Path $buildRoot 'dist\StreamChat'
New-Item -ItemType Directory -Path $buildRoot,$outputDirectory -Force | Out-Null
# Keep the packager cache inside the workspace as well.
$previousConfig = $env:PYINSTALLER_CONFIG_DIR
$env:PYINSTALLER_CONFIG_DIR = Join-Path $buildRoot 'cache'
Push-Location $workspace
try {
    & $pythonExe -m PyInstaller --noconfirm --distpath (Join-Path $buildRoot 'dist') --workpath (Join-Path $buildRoot 'work') (Join-Path $PSScriptRoot 'desktop.spec')
    if ($LASTEXITCODE -ne 0) { throw 'Desktop bundle build failed.' }
    & $pythonExe -B (Join-Path $PSScriptRoot 'verify_bundle.py') $bundle (Join-Path $buildRoot 'work\desktop\Analysis-00.toc')
    if ($LASTEXITCODE -ne 0) { throw 'Bundle verification failed.' }
    & $Compiler '/Qp' ('/DBundleDir=' + $bundle) ('/DOutputDirectory=' + $outputDirectory) (Join-Path $PSScriptRoot 'setup.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Windows installer build failed.' }
    $installer = Join-Path $outputDirectory 'StreamChat-Setup-0.2.0-x64.exe'
    $hash = Get-FileHash -LiteralPath $installer -Algorithm SHA256
    [IO.File]::WriteAllText(($installer + '.sha256'), ($hash.Hash.ToLowerInvariant() + '  ' + [IO.Path]::GetFileName($installer) + "`n"))
    Write-Output "Installer ready: $installer"
} finally {
    Pop-Location
    $env:PYINSTALLER_CONFIG_DIR = $previousConfig
}
