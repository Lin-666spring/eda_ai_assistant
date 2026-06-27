/**
 * Message bridge between the plugin iframe and the LCEDA host.
 *
 * Uses window.postMessage() for bidirectional communication.
 * The iframe sends user commands (analyze BOM, DRC check, etc.) to the host,
 * and the host sends data (BOM, PCB, notifications) back to the iframe.
 */

// ── Message types ────────────────────────────────────────────

/** Messages FROM iframe TO host. */
export interface IframeToHost {
  command:
    | 'analyze-bom'
    | 'drc-check'
    | 'bom-health'
    | 'multi-agent-review'
    | 'import-current-bom'
    | 'resize-panel';
  payload?: unknown;
}

/** Messages FROM host TO iframe. */
export interface HostToIframe {
  type: 'bom-data' | 'pcb-data' | 'drc-result' | 'review-result' | 'notification';
  data: unknown;
}

// ── Listeners ────────────────────────────────────────────────

/**
 * Listen for messages from the iframe.
 * Must be called in the LCEDA extension host context.
 */
export function listenFromIframe(
  handler: (msg: IframeToHost) => void
): void {
  window.addEventListener('message', (event: MessageEvent) => {
    // Accept messages from any origin (iframe runs on file:// or about:blank).
    if (event.data && typeof event.data.command === 'string') {
      handler(event.data as IframeToHost);
    }
  });
}

/**
 * Send a message to the iframe.
 * @param iframe The iframe window (e.g., from SYS_IFrame API).
 */
export function sendToIframe(
  iframeWindow: Window | null,
  msg: HostToIframe
): void {
  if (iframeWindow) {
    iframeWindow.postMessage(msg, '*');
  }
}
