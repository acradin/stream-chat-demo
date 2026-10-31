param([string]$Compiler = '')
& (Join-Path $PSScriptRoot '..\window\packaging\build.ps1') -Compiler $Compiler
