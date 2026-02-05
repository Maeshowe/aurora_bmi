#!/bin/bash
# AURORA BMI - Linux Server Deployment Script
#
# Usage: ./scripts/deploy_linux.sh
#
# Prerequisites:
#   - Python 3.11+
#   - Git
#   - uv (https://docs.astral.sh/uv/)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== AURORA BMI Linux Deployment ===${NC}"

# Configuration - uses current directory
INSTALL_DIR="$(pwd)"
VENV_DIR="${INSTALL_DIR}/.venv"

echo "Install directory: ${INSTALL_DIR}"

# Step 1: Check Python version
echo -e "\n${GREEN}[1/6] Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.11+ required. Found: ${PYTHON_VERSION}${NC}"
    exit 1
fi
echo "Python ${PYTHON_VERSION} OK"

# Step 2: Check for uv
echo -e "\n${GREEN}[2/6] Checking uv installation...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv not found. Installing...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env" 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
fi
echo "uv $(uv --version) OK"

# Step 3: Install dependencies with uv
echo -e "\n${GREEN}[3/6] Installing dependencies...${NC}"
uv sync --extra dev
echo "Dependencies installed"

# Step 4: Create required directories
echo -e "\n${GREEN}[4/6] Creating data directories...${NC}"
mkdir -p "${INSTALL_DIR}/data/raw"
mkdir -p "${INSTALL_DIR}/data/processed"
mkdir -p "${INSTALL_DIR}/data/baselines"
mkdir -p "${INSTALL_DIR}/data/universe"
mkdir -p "${INSTALL_DIR}/logs"

# Step 5: Check for .env file
echo -e "\n${GREEN}[5/6] Checking configuration...${NC}"
if [ ! -f "${INSTALL_DIR}/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating template...${NC}"
    cat > "${INSTALL_DIR}/.env" << 'EOF'
# AURORA BMI Configuration
# Fill in your API keys below

POLYGON_API_KEY=your_key_here
FMP_API_KEY=your_key_here
UW_API_KEY=your_key_here

# Optional settings
LOG_LEVEL=INFO
DATA_DIR=data
EOF
    echo -e "${YELLOW}Please edit ${INSTALL_DIR}/.env with your API keys${NC}"
else
    echo ".env file found"
fi

# Step 6: Test installation
echo -e "\n${GREEN}[6/6] Testing installation...${NC}"
uv run python -c "from aurora.scoring.engine import ScoringEngine; print('Import OK')" && echo "Installation successful!"

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your API keys"
echo "  2. Test API connectivity:"
echo "     uv run python scripts/diagnose_api.py"
echo "  3. Copy systemd files:"
echo "     sudo cp scripts/aurora-daily.service /etc/systemd/system/"
echo "     sudo cp scripts/aurora-daily.timer /etc/systemd/system/"
echo "     sudo cp scripts/aurora-dashboard.service /etc/systemd/system/"
echo "  4. Enable services:"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable --now aurora-daily.timer"
echo "     sudo systemctl enable --now aurora-dashboard"
echo ""
echo "Manual run: uv run python scripts/run_daily.py"
echo "Dashboard:  uv run streamlit run aurora/dashboard/app.py --server.port 8503"
