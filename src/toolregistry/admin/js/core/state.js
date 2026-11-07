// ============== Configuration ==============
const API_BASE = window.location.origin + window.location.pathname.replace(/\/+$/, '');
// The bearer token lives in memory only.  A successful Bearer request makes
// the server set an HttpOnly session cookie, which carries the login across
// reloads without leaving a value in storage that page script can read.
let AUTH_TOKEN = '';
// Remove the value older builds persisted.
try {
    localStorage.removeItem('admin_token');
} catch (e) {
    // Private mode or blocked storage: nothing to clear.
}
let autoRefreshInterval = null;
let allTools = [];

// SVG icon helper
const SVG_CHEVRON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>';
