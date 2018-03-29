/*
connect (and run) to the API proxy
*/
var port = browser.runtime.connectNative("api_proxy_native_app");

/*
Listen for messages from the API proxy.
*/
console.log('registering callback for receive')
port.onMessage.addListener((response) => {
  console.log("Received: " + response);
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
});

console.log('registering onClicked')
/*
On a click on the browser action, send the app a message.
*/
browser.browserAction.onClicked.addListener(() => {
  console.log("Sending:  ping");
  port.postMessage("ping");
});
