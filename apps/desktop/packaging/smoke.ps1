# Installs into a fresh workspace directory, checks the frozen app, upgrades,
# and removes only that test installation. No visible UI or screenshots.
$ErrorActionPreference = 'Stop'
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$installer = Join-Path $workspace 'dist\StreamChat-Setup-0.4.0-x64.exe'
$registryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{E2A673FA-FCFD-4696-8E08-125D5E91F5AF}_is1'
if (Test-Path -LiteralPath $registryPath) { throw 'An existing Stream Chat installation is present; leave it untouched.' }
if (-not (Test-Path -LiteralPath $installer)) { throw 'Build the installer first.' }
$scratch = [IO.Path]::GetFullPath((Join-Path $workspace ('runs\installer_smoke_' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))))
if (-not $scratch.StartsWith($workspace + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Test path outside workspace.' }
$installDirectory = Join-Path $scratch 'installed app'
$profileDirectory = Join-Path $scratch 'profile'
$appData = Join-Path $profileDirectory 'StreamChat\desktop'
New-Item -ItemType Directory -Path $scratch,$appData -Force | Out-Null
$marker = Join-Path $appData 'settings.json'
[IO.File]::WriteAllText($marker, '{"count":3}')
$originalPath = $env:PATH
$originalLocal = $env:LOCALAPPDATA
$originalPythonHome = $env:PYTHONHOME
$originalPythonPath = $env:PYTHONPATH

function Invoke-CheckedProcess([string]$File, [string[]]$Arguments) {
    $process = Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $scratch -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(30000)) {
        $process.Kill()
        throw 'Test process exceeded 30 seconds.'
    }
    if ($process.ExitCode -ne 0) { throw "Test process failed with exit code $($process.ExitCode): $([IO.Path]::GetFileName($File))" }
}

$installArguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/NOICONS',('/DIR="' + $installDirectory + '"'))
$uninstallVerified = $false
try {
    Invoke-CheckedProcess $installer ($installArguments + ('/LOG="' + (Join-Path $scratch 'install.log') + '"'))
    $registered = (Get-ItemProperty -LiteralPath $registryPath).InstallLocation.TrimEnd('\')
    if ($registered -ne $installDirectory) { throw 'Installation registration does not match test directory.' }
    # The EXE must work without a Python installation on PATH and without the repo as CWD.
    $env:PATH = Join-Path $env:SystemRoot 'System32'
    $env:LOCALAPPDATA = $profileDirectory
    $env:PYTHONHOME = $null
    $env:PYTHONPATH = $null
    $report = Join-Path $scratch 'runtime.json'
    Invoke-CheckedProcess (Join-Path $installDirectory 'StreamChat.exe') @('--self-test', ('"' + $report + '"'))
    $runtime = Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($runtime.status -ne 'ok' -or -not $runtime.frozen -or $runtime.network_calls -ne 0 -or $runtime.screenshots -ne 0) { throw 'Frozen runtime check did not pass.' }
    Invoke-CheckedProcess $installer ($installArguments + ('/LOG="' + (Join-Path $scratch 'upgrade.log') + '"'))
    if ([IO.File]::ReadAllText($marker) -ne '{"count":3}') { throw 'Upgrade modified user settings.' }
} finally {
    $env:PATH = $originalPath
    $env:LOCALAPPDATA = $originalLocal
    $env:PYTHONHOME = $originalPythonHome
    $env:PYTHONPATH = $originalPythonPath
    $uninstaller = Join-Path $installDirectory 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        $registered = (Get-ItemProperty -LiteralPath $registryPath).InstallLocation.TrimEnd('\')
        if ($registered -ne $installDirectory -or -not $installDirectory.StartsWith($scratch + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to uninstall a different installation.'
        }
        Invoke-CheckedProcess $uninstaller @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="' + (Join-Path $scratch 'uninstall.log') + '"'))
        if ((Test-Path -LiteralPath (Join-Path $installDirectory 'StreamChat.exe')) -or (Test-Path -LiteralPath $registryPath)) { throw 'Uninstall did not remove the test application.' }
        if ([IO.File]::ReadAllText($marker) -ne '{"count":3}') { throw 'Uninstall modified user settings.' }
        $uninstallVerified = $true
    }
}
@{status='ok';install=$true;runtime=$runtime;upgrade_preserves_settings=$true;uninstall=$uninstallVerified;settings_retained=$true} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $scratch 'report.json') -Encoding UTF8
Write-Output "Installer smoke test passed: $scratch"
