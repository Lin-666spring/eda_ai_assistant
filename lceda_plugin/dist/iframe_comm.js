/**
 * Message bridge between the plugin iframe and the LCEDA host.
 *
 * Uses window.postMessage() for bidirectional communication.
 * The iframe sends user commands (analyze BOM, DRC check, etc.) to the host,
 * and the host sends data (BOM, PCB, notifications) back to the iframe.
 */
// ── Listeners ────────────────────────────────────────────────
/**
 * Listen for messages from the iframe.
 * Must be called in the LCEDA extension host context.
 */
export function listenFromIframe(handler) {
    window.addEventListener('message', (event) => {
        // Accept messages from any origin (iframe runs on file:// or about:blank).
        if (event.data && typeof event.data.command === 'string') {
            handler(event.data);
        }
    });
}
/**
 * Send a message to the iframe.
 * @param iframe The iframe window (e.g., from SYS_IFrame API).
 */
export function sendToIframe(iframeWindow, msg) {
    if (iframeWindow) {
        iframeWindow.postMessage(msg, '*');
    }
}
//# sourceMappingURL=iframe_comm.js.map