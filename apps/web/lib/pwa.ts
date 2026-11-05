/**
 * Inline script for <head>: registers the service worker after load (production builds
 * only, so dev reloads never serve stale files) and keeps the browser's install prompt
 * for the "Install app" button. Static text, no user input.
 */
const script = `(function(){
if(!("serviceWorker" in navigator))return;
window.addEventListener("load",function(){navigator.serviceWorker.register("/sw.js").catch(function(){});});
window.addEventListener("beforeinstallprompt",function(e){e.preventDefault();window.__anygetInstall=e;window.dispatchEvent(new Event("anyget:installable"));});
})();`;

export const pwaScript = process.env.NODE_ENV === "production" ? script : "";
