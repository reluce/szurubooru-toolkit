browser.runtime.onMessage.addListener(function (message, sender, sendResponse) {
  if (message.action === 'run_import_from_url') {
    const currentURL = message.url;
    const cookieLocation = message.inputCookieLocation || '';
    const range = message.inputRange || '';
    
    const url = 'http://localhost:5000/import-from-url?url=' + 
                encodeURIComponent(currentURL) + 
                '&cookies=' + encodeURIComponent(cookieLocation) + 
                '&range=' + encodeURIComponent(range);
    
    fetch(url, { method: 'POST' })
      .then(response => response.text())
      .then(result => {
        console.log('Import result:', result);
        // Optionally show a notification
        browser.notifications.create({
          type: 'basic',
          iconUrl: 'images/icon64.png',
          title: 'szurubooru-toolkit',
          message: 'Import completed for current tab'
        });
      })
      .catch(error => {
        console.error('Import error:', error);
        browser.notifications.create({
          type: 'basic',
          iconUrl: 'images/icon64.png',
          title: 'szurubooru-toolkit',
          message: 'Import failed: ' + error.message
        });
      });
  }
  
  if (message.action === 'run_import_from_all_tabs') {
    const urls = message.urls;
    const cookieLocation = message.inputCookieLocation || '';
    const range = message.inputRange || '';
    
    const url = 'http://localhost:5000/import-from-all-tabs?cookies=' + 
                encodeURIComponent(cookieLocation) + 
                '&range=' + encodeURIComponent(range);
    
    fetch(url, { 
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ urls: urls })
    })
      .then(response => response.text())
      .then(result => {
        console.log('Import all tabs result:', result);
        browser.notifications.create({
          type: 'basic',
          iconUrl: 'images/icon64.png',
          title: 'szurubooru-toolkit',
          message: `Import completed for ${urls.length} tabs`
        });
      })
      .catch(error => {
        console.error('Import all tabs error:', error);
        browser.notifications.create({
          type: 'basic',
          iconUrl: 'images/icon64.png',
          title: 'szurubooru-toolkit',
          message: 'Import failed: ' + error.message
        });
      });
  }
}); 