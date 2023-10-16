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

// Function to toggle between light and dark mode styles
function toggleMode() {
  const darkMode = window.matchMedia('(prefers-color-scheme: dark)');
  const body = document.body;

  if (darkMode.matches) {
    // User prefers dark mode
    body.classList.add('dark-mode');
  } else {
    // User prefers light mode or default mode
    body.classList.remove('dark-mode');
  }
}

// Call the toggleMode function when the popup is loaded
toggleMode();

// Add an event listener to react to changes in the system settings
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', toggleMode);
