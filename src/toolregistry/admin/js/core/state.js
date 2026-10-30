// ============== Configuration ==============
const API_BASE = window.location.origin + window.location.pathname.replace(/\/+$/, '');
let AUTH_TOKEN = localStorage.getItem('admin_token') || '';
let autoRefreshInterval = null;
let allTools = [];

// SVG icon helper
const SVG_CHEVRON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>';
