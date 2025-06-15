# szurubooru-toolkit Chrome Extension

This Chrome extension allows you to import images from web pages directly to your szurubooru instance using the szurubooru-toolkit.

## Features

- Import current tab to szurubooru
- Import all open tabs to szurubooru
- Optional cookie file support for authenticated downloads
- Optional range specification for limiting downloads
- Dark mode support
- Desktop notifications for import status

## Installation

### Prerequisites

1. Make sure you have the szurubooru-toolkit Python package installed and configured
2. Start the Flask webserver by running: `python run-webserver.py` from the main repository directory

### Installing the Extension in Chrome

1. Open Chrome
2. Navigate to `chrome://extensions/` in the address bar
3. Enable "Developer mode" in the top right corner
4. Click "Load unpacked"
5. Navigate to and select the `chrome_extension` folder
6. The extension should now be loaded and visible in your Chrome toolbar

### For Permanent Installation (Development)

For development purposes, you can also package the extension:

1. In Chrome, go to `chrome://extensions/`
2. Click "Pack extension"
3. Select the `chrome_extension` folder as the extension root directory
4. This will create a .crx file that can be installed

## Usage

1. Make sure the Flask webserver is running (`python run-webserver.py`)
2. Click the szurubooru-toolkit icon in the Chrome toolbar
3. Optionally enter:
   - Cookie file location (for authenticated downloads)
   - Download range (to limit the number of images)
4. Choose one of the import options:
   - **Import current tab**: Imports images from the currently active tab
   - **Import all tabs**: Imports images from all open tabs in the current window

## Configuration

The extension will remember your cookie file location and range settings between uses.

## Troubleshooting

- Make sure the Flask webserver is running on `http://localhost:5000`
- Check the browser console for any error messages
- Ensure you have the necessary permissions to access the URLs you're trying to import from
- For authenticated sites, make sure your cookie file is accessible and valid

## Compatibility

- Chrome 88 or later (Manifest V3)
- Compatible with Windows, Linux, and macOS 