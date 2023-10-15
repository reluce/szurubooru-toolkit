chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
  if (message.action === 'run_import_from_url') {
    const currentURL = message.url;
    const cookieLocation = message.inputCookieLocation;
    const range = message.inputRange;
    fetch('http://localhost:5000/import-from-url?url=' + encodeURIComponent(currentURL) + '&cookies=' + cookieLocation + '&range=' + range, { method: 'POST' })
      .then(response => response.text())
      .then(result => console.log(result))
      .catch(error => console.error(error));
  }
});
