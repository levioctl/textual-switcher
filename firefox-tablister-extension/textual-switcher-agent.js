/*
connect (and run) to the API proxy
*/
var port = browser.runtime.connectNative("api_proxy_native_app");

/*
Listen for messages from the API proxy.
*/
console.log('registering callback for receive')
port.onMessage.addListener((message) => {
  console.log("Received: " + message);
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
        console.log('sending tab list');
        port.postMessage(tabs);
      });
  } else if (message.startsWith("switch_tab:")) {
    tabId = parseInt(message.substring("switch_tab:".length, message.length - 1));
    console.log("switch to tab " + tabId);
  }
});

console.log('registering onClicked')
/*
On a click on the browser action, send the app a message.
*/
browser.browserAction.onClicked.addListener(() => {
  console.log("Sending:  ping");
  port.postMessage("ping");
});
