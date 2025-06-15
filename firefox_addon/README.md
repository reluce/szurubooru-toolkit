# szurubooru-toolkit Firefox Add-on

This Firefox add-on allows you to import images from web pages directly to your szurubooru instance using the szurubooru-toolkit.

## Features

- Import current tab to szurubooru
- Import all open tabs to szurubooru
- Optional cookie file support for authenticated downloads
- Optional range specification for limiting downloads
- Dark mode support

## Installation

### Prerequisites

1. Make sure you have the szurubooru-toolkit Python package installed and configured
2. Start the Flask webserver by running: `python run-webserver.py` from the main repository directory

### Installing the Add-on in Firefox

1. Open Firefox
2. Navigate to `about:debugging` in the address bar
3. Click "This Firefox" in the left sidebar
4. Click "Load Temporary Add-on..."
5. Navigate to the `firefox_addon` folder and select the `manifest.json` file
6. The add-on should now be loaded and visible in your Firefox toolbar

### For Permanent Installation (Development)

For development purposes, you can also:

1. Navigate to `about:config` in Firefox
2. Search for `xpinstall.signatures.required` and set it to `false` (this disables signature verification)
3. Package the add-on as a .xpi file:
   ```bash
   cd firefox_addon
   zip -r ../szurubooru-toolkit-firefox.xpi *
   ```
4. Install the .xpi file through Firefox's Add-ons manager

## Usage

1. Make sure the Flask webserver is running (`python run-webserver.py`)
2. Click the szurubooru-toolkit icon in the Firefox toolbar
3. Optionally enter:
   - Cookie file location (for authenticated downloads)
   - Download range (to limit the number of images)
4. Choose one of the import options:
   - **Import current tab**: Imports images from the currently active tab
   - **Import all tabs**: Imports images from all open tabs in the current window

## Configuration

The add-on will remember your cookie file location and range settings between uses.

## Troubleshooting

- Make sure the Flask webserver is running on `http://localhost:5000`
- Check the browser console for any error messages
- Ensure you have the necessary permissions to access the URLs you're trying to import from
- For authenticated sites, make sure your cookie file is accessible and valid

## Compatibility

- Firefox 57.0 or later
- Compatible with Windows, Linux, and macOS 