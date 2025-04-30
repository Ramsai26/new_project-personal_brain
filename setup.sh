#!/bin/bash
# Bash script to set up the virtual environment and install dependencies

# Activate the virtual environment
echo -e "\e[32mActivating virtual environment...\e[0m"
source venv/bin/activate

# Install dependencies
echo -e "\e[32mInstalling dependencies...\e[0m"
pip install -r requirements.txt

# Install sentence-transformers (required for vector DB)
echo -e "\e[32mInstalling sentence-transformers...\e[0m"
pip install sentence-transformers

# Create necessary directories
echo -e "\e[32mCreating necessary directories...\e[0m"
python -c "import sys; sys.path.append('./src'); from config import create_directories; create_directories()"

echo -e "\n\e[32mSetup complete!\e[0m"
echo -e "\e[36mTo run the application:\e[0m"
echo -e "\e[36m1. Activate the virtual environment: source venv/bin/activate\e[0m"
echo -e "\e[36m2. Run the application: python main.py --serve\e[0m" 