#!/bin/bash

# Build script for szurubooru-toolkit Firefox Add-on

echo "Building Firefox add-on..."

# Remove any existing build
rm -f ../szurubooru-toolkit-firefox.xpi

# Create the .xpi package
zip -r ../szurubooru-toolkit-firefox.xpi * -x "*.sh" "README.md"

echo "Build complete: szurubooru-toolkit-firefox.xpi"
echo ""
echo "To install:"
echo "1. Open Firefox"
echo "2. Go to about:debugging"
echo "3. Click 'This Firefox'"
echo "4. Click 'Load Temporary Add-on...'"
echo "5. Select the manifest.json file in this directory" 