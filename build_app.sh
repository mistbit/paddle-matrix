#!/bin/bash
#
# Build script for Paddle Matrix macOS App
# This script packages the FastAPI service into a standalone macOS application
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project info
PROJECT_NAME="Paddle Matrix"
APP_NAME="${PROJECT_NAME}.app"
BUILD_DIR="build"
DIST_DIR="dist"

# Use Python 3.10 (PaddlePaddle requires Python 3.10-3.12)
PYTHON_CMD="/opt/homebrew/bin/python3.10"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Paddle Matrix - macOS App Builder${NC}"
echo -e "${GREEN}========================================${NC}"

# Check Python
echo -e "\n${YELLOW}Checking Python environment...${NC}"
if [ ! -f "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: Python 3.10 not found at $PYTHON_CMD${NC}"
    echo -e "${YELLOW}Please install Python 3.10: brew install python@3.10${NC}"
    exit 1
fi
echo "Using Python: $($PYTHON_CMD --version)"

# Create virtual environment with Python 3.10
echo -e "\n${YELLOW}Creating virtual environment with Python 3.10...${NC}"
rm -rf venv
$PYTHON_CMD -m venv venv

# Activate virtual environment
echo -e "\n${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "\n${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Clean previous builds
echo -e "\n${YELLOW}Cleaning previous builds...${NC}"
rm -rf ${BUILD_DIR} ${DIST_DIR}
rm -f *.spec.bak

# Build the app
echo -e "\n${YELLOW}Building macOS app...${NC}"
echo -e "${YELLOW}This may take several minutes...${NC}"
pyinstaller paddle_matrix.spec --clean --noconfirm

# Check if build was successful
if [ -d "${DIST_DIR}/${APP_NAME}" ]; then
    echo -e "\n${YELLOW}Fixing OpenSSL library conflict...${NC}"

    # Copy Homebrew OpenSSL libraries to fix conflict with OpenCV bundled libs
    SSL_SRC="/opt/homebrew/opt/openssl@3/lib"
    if [ -d "$SSL_SRC" ]; then
        cp -L "$SSL_SRC/libcrypto.3.dylib" "${DIST_DIR}/${APP_NAME}/Contents/Frameworks/"
        cp -L "$SSL_SRC/libssl.3.dylib" "${DIST_DIR}/${APP_NAME}/Contents/Frameworks/"
        echo -e "  Copied OpenSSL libraries from Homebrew"
    else
        echo -e "${YELLOW}  Warning: Homebrew OpenSSL not found, app may not work correctly${NC}"
    fi

    # Re-sign the app after modifying
    codesign --force --deep --sign - "${DIST_DIR}/${APP_NAME}" 2>/dev/null || true

    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}  Build successful!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "\nApp location: ${DIST_DIR}/${APP_NAME}"
    echo -e "\nTo run the app:"
    echo -e "  open ${DIST_DIR}/${APP_NAME}"
    echo -e "\nTo install the app:"
    echo -e "  cp -r ${DIST_DIR}/${APP_NAME} /Applications/"
    echo ""

    # Show app size
    APP_SIZE=$(du -sh "${DIST_DIR}/${APP_NAME}" | cut -f1)
    echo -e "App size: ${APP_SIZE}"
else
    echo -e "\n${RED}Build failed!${NC}"
    echo -e "Check the build log for errors."
    exit 1
fi

# Deactivate virtual environment
deactivate

echo -e "\n${GREEN}Done!${NC}"