# PowerShell script to set up the virtual environment and install dependencies

# Activate the virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Green
pip install -r requirements.txt

# Install sentence-transformers (required for vector DB)
Write-Host "Installing sentence-transformers..." -ForegroundColor Green
pip install sentence-transformers

# Create necessary directories
Write-Host "Creating necessary directories..." -ForegroundColor Green
python -c "import sys; sys.path.append('./src'); from config import create_directories; create_directories()"

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "To run the application:" -ForegroundColor Cyan
Write-Host "1. Activate the virtual environment: .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "2. Run the application: python main.py --serve" -ForegroundColor Cyan 