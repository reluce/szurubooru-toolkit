// Get the input element
const inputCookieLocationBox = document.getElementById('inputCookieLocation');
const inputRangeBox = document.getElementById('inputRange');

// Restore the saved input when the popup is opened
chrome.storage.sync.get(['savedInputs'], function(result) {
  const savedInputs = result.savedInputs;

  if (result.savedInputs) {
    inputCookieLocationBox.value = savedInputs.inputCookieLocation;
    inputRangeBox.value = savedInputs.inputRange;
  }
});

document.getElementById('executeButton').addEventListener('click', function () {
  const userInputCookieLocation = inputCookieLocationBox.value;
  const userInputRange = inputRangeBox.value;

  // Save the input to storage
  chrome.storage.sync.set({ 'savedInputs': { inputCookieLocation: userInputCookieLocation, inputRange: userInputRange } });

  chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
    const currentURL = tabs[0].url;
    chrome.runtime.sendMessage({ action: 'run_import_from_url', url: currentURL, inputCookieLocation: userInputCookieLocation, inputRange: userInputRange });
  });
});
