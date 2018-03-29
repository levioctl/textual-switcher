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
});

console.log('registering onClicked')
/*
On a click on the browser action, send the app a message.
*/
browser.browserAction.onClicked.addListener(() => {
  console.log("Sending:  ping");
  port.postMessage("ping");
});
