// Get the input elements
const inputCookieLocationBox = document.getElementById('inputCookieLocation');
const inputRangeBox = document.getElementById('inputRange');

// Restore the saved input when the popup is opened
browser.storage.sync.get(['savedInputs']).then(function(result) {
  const savedInputs = result.savedInputs;

  if (savedInputs) {
    inputCookieLocationBox.value = savedInputs.inputCookieLocation || '';
    inputRangeBox.value = savedInputs.inputRange || '';
  }
});

// Import current tab functionality
document.getElementById('importCurrentTabButton').addEventListener('click', function () {
  const userInputCookieLocation = inputCookieLocationBox.value;
  const userInputRange = inputRangeBox.value;

  // Save the input to storage
  browser.storage.sync.set({ 
    'savedInputs': { 
      inputCookieLocation: userInputCookieLocation, 
      inputRange: userInputRange 
    } 
  });

  browser.tabs.query({ active: true, currentWindow: true }).then(function (tabs) {
    const currentURL = tabs[0].url;
    browser.runtime.sendMessage({ 
      action: 'run_import_from_url', 
      url: currentURL, 
      inputCookieLocation: userInputCookieLocation, 
      inputRange: userInputRange 
    });
  });
});

// Import all tabs functionality
document.getElementById('importAllTabsButton').addEventListener('click', function () {
  const userInputCookieLocation = inputCookieLocationBox.value;
  const userInputRange = inputRangeBox.value;

  // Save the input to storage
  browser.storage.sync.set({ 
    'savedInputs': { 
      inputCookieLocation: userInputCookieLocation, 
      inputRange: userInputRange 
    } 
  });

  browser.tabs.query({ currentWindow: true }).then(function (tabs) {
    const urls = tabs.map(tab => tab.url);
    browser.runtime.sendMessage({ 
      action: 'run_import_from_all_tabs', 
      urls: urls, 
      inputCookieLocation: userInputCookieLocation, 
      inputRange: userInputRange 
    });
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