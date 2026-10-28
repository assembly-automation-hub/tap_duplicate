$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$tapPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $tapPython)) {
    python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
}
& $tapPython -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& $tapPython -B -c "from comtypes.client import GetModule; GetModule('UIAutomationCore.dll')"
if ($LASTEXITCODE -ne 0) { throw 'UI Automation wrapper generation failed.' }
& $tapPython -m PyInstaller --noconfirm --clean --onefile --windowed --name 'Tap Duplicator' --distpath . --workpath .build --specpath .build --manifest (Join-Path $PSScriptRoot 'app.manifest') --icon (Join-Path $PSScriptRoot 'tap_duplicate.ico') --hidden-import comtypes.gen.UIAutomationClient --collect-submodules comtypes.gen tap_duplicate.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
