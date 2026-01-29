# Aura Frame Downloader - Windows Build Script
# Run this script in PowerShell to build the Windows executable

param(
    [switch]$Clean,
    [switch]$Install,
    [switch]$Build,
    [switch]$Run,
    [switch]$All
)

$ErrorActionPreference = "Stop"

function Write-Status($message) {
    Write-Host "--> $message" -ForegroundColor Cyan
}

function Install-Venv {
    Write-Status "Creating Python virtual environment"

    if (Test-Path ".\venv") {
        Write-Status "Removing existing venv"
        Remove-Item -Recurse -Force ".\venv"
    }

    python -m venv venv

    Write-Status "Upgrading pip"
    .\venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel

    Write-Status "Installing dependencies"
    .\venv\Scripts\pip.exe install -r requirements.txt

    Write-Status "Virtual environment ready"
}

function Build-App {
    Write-Status "Building Windows executable"

    if (-not (Test-Path ".\venv\Scripts\pyinstaller.exe")) {
        Write-Host "Error: PyInstaller not found. Run with -Install first." -ForegroundColor Red
        exit 1
    }

    .\venv\Scripts\pyinstaller.exe aura_gui.spec

    if (Test-Path ".\dist\Aura Downloader.exe") {
        Write-Status "Build complete: dist\Aura Downloader.exe"
        $size = (Get-Item ".\dist\Aura Downloader.exe").Length / 1MB
        Write-Host "    Size: $([math]::Round($size, 2)) MB" -ForegroundColor Green
    } else {
        Write-Host "Error: Build failed" -ForegroundColor Red
        exit 1
    }
}

function Run-App {
    Write-Status "Running Aura Frame Downloader GUI"
    .\venv\Scripts\python.exe aura_gui.py
}

function Clean-Build {
    Write-Status "Cleaning build artifacts"

    if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" }
    if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" }

    Write-Status "Clean complete"
}

# Main execution
if ($All) {
    $Install = $true
    $Build = $true
}

if (-not ($Clean -or $Install -or $Build -or $Run -or $All)) {
    Write-Host ""
    Write-Host "Aura Frame Downloader - Windows Build Script" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Usage: .\build_windows.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Install    Create venv and install dependencies"
    Write-Host "  -Build      Build the Windows executable"
    Write-Host "  -Run        Run the GUI from source"
    Write-Host "  -Clean      Remove build artifacts"
    Write-Host "  -All        Install + Build"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\build_windows.ps1 -All          # Full build"
    Write-Host "  .\build_windows.ps1 -Install      # Setup only"
    Write-Host "  .\build_windows.ps1 -Build        # Build only"
    Write-Host "  .\build_windows.ps1 -Run          # Run from source"
    Write-Host ""
    exit 0
}

if ($Clean) { Clean-Build }
if ($Install) { Install-Venv }
if ($Build) { Build-App }
if ($Run) { Run-App }

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
