# Customer Support Resolution Agent — Windows setup script
# Usage: .\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host "Creating virtual environment..." -ForegroundColor Cyan
python -m venv venv

Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Copy .env.example to .env and add your API keys"
Write-Host "  2. Activate: .\venv\Scripts\Activate.ps1"
Write-Host "  3. Run API:  uvicorn app:app --reload"
Write-Host "  4. Run UI:   streamlit run ui.py"
