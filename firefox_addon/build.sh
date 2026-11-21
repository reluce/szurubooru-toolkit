#!/bin/bash
set -euo pipefail

# Build script for szurubooru-toolkit Firefox Add-on

cd "$(dirname "$0")"

echo "Building Firefox add-on..."

# Remove any existing build
rm -f ../szurubooru-toolkit-firefox.xpi

# Create the .xpi package
zip -r ../szurubooru-toolkit-firefox.xpi manifest.json background.js popup.html popup.js styles.css images -x "*.DS_Store"

echo "Build complete: szurubooru-toolkit-firefox.xpi"
echo ""
echo "To install:"
echo "1. Open Firefox"
echo "2. Go to about:debugging"
echo "3. Click 'This Firefox'"
echo "4. Click 'Load Temporary Add-on...'"
echo "5. Select the manifest.json file in this directory" 
