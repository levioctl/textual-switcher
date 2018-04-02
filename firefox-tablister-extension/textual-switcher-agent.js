/*
connect to the API proxy
*/
var port = browser.runtime.connectNative("api_proxy_native_app");

/*
Listen (and respond) to messages from the API proxy.
*/
port.onMessage.addListener((message) => {
  console.log("Received from API proxy: " + message);

  if (message == "list_tabs") {
    // List tabs
    tabs = null
    chrome.tabs.query({},
      function(result) {
        // Filter results to interesting keys
        tabs = result.map(function(tab) {
                            return {title: tab['title'],
                                    id: tab['id'],
                                    url: tab['url'],
                                    favIconUrl: tab['favIconUrl']
                                   };
                          });
        console.log('Sending tab list');
        port.postMessage(tabs);
      });

  } else if (message.startsWith("move_to_tab:")) {
    tabId = parseInt(message.substring("move_to_tab:".length));
    console.log("Switching to tab " + tabId);
    chrome.tabs.update(tabId, {active: true});
  }
});
