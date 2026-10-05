<#
.SYNOPSIS
    Verificación completa del proyecto Carely.

.DESCRIPTION
    Ejecuta, en orden:
      1. manage.py check
      2. la suite completa de tests
      3. comprobación de que no faltan migraciones
      4. revisión de basura en el diff (whitespace, .pyc, restos de depuración)

    Todo cambio debe terminar con este script en verde.

.PARAMETER SkipTests
    Omite la suite de tests (solo para iteración rápida).

.PARAMETER SkipMigrations
    Omite la comprobación de migraciones.

.EXAMPLE
    .\Agent\verify.ps1

.EXAMPLE
    .\Agent\verify.ps1 -SkipTests
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipMigrations
)

$ErrorActionPreference = 'Stop'

# La consola de Windows usa CP850 por defecto y rompe los acentos del output.
# Sin esto, los mensajes en español de Django salen con caracteres corruptos.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
    # En hosts sin consola no es crítico.
}
$env:PYTHONIOENCODING = 'utf-8'

# El intérprete del proyecto, nunca el global.
$Python = Join-Path $PSScriptRoot '..\env\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "No se encuentra el venv en $Python" -ForegroundColor Red
    Write-Host "Instala dependencias: pip install -r requirements\development.txt" -ForegroundColor Yellow
    exit 1
}

$Python = (Resolve-Path -LiteralPath $Python).Path
$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

$script:Failures = @()

function Invoke-Step {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][scriptblock]$Action
    )
    Write-Host ''
    Write-Host "==> $Name" -ForegroundColor Cyan

    # Django escribe parte de su salida (p. ej. "Creating test database") en
    # stderr. Con ErrorActionPreference='Stop' eso se convertiría en un error
    # falso, así que se relaja mientras dura el comando nativo.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    $output = & $Action 2>&1
    $exitCode = $LASTEXITCODE

    $ErrorActionPreference = $previousPreference

    # Se muestran solo las últimas líneas: el log de tests es largo.
    $output |
        Where-Object {
            $_ -notmatch '^\s*(\+|:|CategoryInfo|FullyQualifiedErrorId|At )' -and
            $_ -notmatch 'RemoteException'
        } |
        Select-Object -Last 25 |
        ForEach-Object { Write-Host "   $_" }

    if ($exitCode -ne 0) {
        Write-Host "   FALLO: $Name (código $exitCode)" -ForegroundColor Red
        $script:Failures += $Name
    } else {
        Write-Host "   OK" -ForegroundColor Green
    }
}

# 1. Chequeo de configuración
Invoke-Step 'manage.py check' {
    $env:DJANGO_ENV = 'test'
    & $Python manage.py check
}

# 2. Suite de tests
if (-not $SkipTests) {
    Invoke-Step 'Suite completa' {
        $env:DJANGO_ENV = 'test'
        & $Python manage.py test
    }
} else {
    Write-Host ''
    Write-Host '==> Suite completa (omitida por -SkipTests)' -ForegroundColor Yellow
}

# 3. Migraciones al día
if (-not $SkipMigrations) {
    Invoke-Step 'Migraciones al día' {
        $env:DJANGO_ENV = 'development'
        & $Python manage.py makemigrations --check --dry-run
    }
}

# 4. Basura en el diff
Write-Host ''
Write-Host '==> Revisión del diff' -ForegroundColor Cyan

$diffIssues = @()

# `git diff --check` escribe los avisos de LF/CRLF en stderr; no son
# problemas de whitespace, así que se separan del resto.
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'

$whitespace = @(git diff --check 2>&1) |
    Where-Object { $_ -notmatch 'LF will be replaced' -and $_ -notmatch 'RemoteException' }
$staged = @(git diff --cached --name-only 2>&1)
$debug = @(git diff -U0 2>&1) |
    Select-String -Pattern '^\+.*\b(print\(|breakpoint\(|pdb\.set_trace|console\.log)'

$ErrorActionPreference = $previousPreference

if ($whitespace) {
    $diffIssues += 'Whitespace conflictivo (git diff --check)'
    $whitespace | Select-Object -First 5 | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
}

$artifacts = $staged | Where-Object { $_ -match '(\.pyc$|__pycache__|\.log$|^\.env$)' }
if ($artifacts) {
    $diffIssues += 'Artefactos en el índice: ' + ($artifacts -join ', ')
    $artifacts | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
}

if ($debug) {
    $diffIssues += 'Posible código de depuración en el diff'
    $debug | Select-Object -First 5 | ForEach-Object { Write-Host "   $_" -ForegroundColor Yellow }
}

if ($diffIssues.Count -eq 0) {
    Write-Host '   OK' -ForegroundColor Green
} else {
    foreach ($issue in $diffIssues) {
        Write-Host "   FALLO: $issue" -ForegroundColor Red
        $script:Failures += $issue
    }
}

# Resumen
$env:DJANGO_ENV = 'test'
Pop-Location

Write-Host ''
if ($script:Failures.Count -eq 0) {
    Write-Host 'Todo correcto.' -ForegroundColor Green
    exit 0
}

Write-Host "Fallaron $($script:Failures.Count) comprobaciones:" -ForegroundColor Red
$script:Failures | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
exit 1
