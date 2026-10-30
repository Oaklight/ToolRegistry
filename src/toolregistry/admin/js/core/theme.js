// ============== Theme & console layout ==============
//
// The scheme and mode live on <html data-scheme data-mode>; the values they
// resolve to live in css/base.css.  Nothing here knows a colour: it only
// keeps the attributes, the stored preference and the controls in sync.
const SCHEMES = ['paper', 'slate'];
const MODES = ['light', 'dark'];

function currentScheme() {
    const value = document.documentElement.getAttribute('data-scheme');
    return SCHEMES.includes(value) ? value : SCHEMES[0];
}

function currentMode() {
    const value = document.documentElement.getAttribute('data-mode');
    return MODES.includes(value) ? value : MODES[0];
}

function applyTheme(scheme, mode) {
    const nextScheme = SCHEMES.includes(scheme) ? scheme : currentScheme();
    const nextMode = MODES.includes(mode) ? mode : currentMode();
    document.documentElement.setAttribute('data-scheme', nextScheme);
    document.documentElement.setAttribute('data-mode', nextMode);
    try {
        localStorage.setItem('toolregistry-scheme', nextScheme);
        localStorage.setItem('toolregistry-mode', nextMode);
    } catch (e) {
        // Private mode or blocked storage: the attribute still applies for
        // this page load, which is what the user asked for.
    }
    syncThemeControls();
}

function setScheme(scheme) {
    applyTheme(scheme, currentMode());
}

function setMode(mode) {
    applyTheme(currentScheme(), mode);
}

function toggleMode() {
    setMode(currentMode() === 'dark' ? 'light' : 'dark');
}

function syncThemeControls() {
    const select = document.getElementById('schemeSwitcher');
    if (select) select.value = currentScheme();
    const toggle = document.getElementById('modeToggle');
    if (toggle) {
        const next = currentMode() === 'dark' ? 'light' : 'dark';
        toggle.title = t(next === 'dark' ? 'theme.toDark' : 'theme.toLight');
        toggle.setAttribute('aria-label', toggle.title);
    }
}

// ---------- Console rail ----------
function consoleCollapsed() {
    return document.getElementById('app')?.dataset.console === 'collapsed';
}

function setConsoleCollapsed(collapsed) {
    const app = document.getElementById('app');
    if (!app) return;
    app.dataset.console = collapsed ? 'collapsed' : 'expanded';
    try {
        localStorage.setItem('toolregistry-console', collapsed ? 'collapsed' : 'expanded');
    } catch (e) {}
    const toggle = document.querySelector('.console-toggle');
    if (toggle) {
        const label = t(collapsed ? 'btn.expand' : 'btn.collapse');
        toggle.title = label;
        toggle.setAttribute('aria-label', label);
        const text = toggle.querySelector('.console-item-label');
        if (text) text.textContent = label;
    }
}

function toggleConsoleSize() {
    setConsoleCollapsed(!consoleCollapsed());
}

// Drawer behaviour for narrow viewports; on desktop this is inert because
// the CSS only binds .console-open below the 900px breakpoint.
function toggleConsole(force) {
    const app = document.getElementById('app');
    if (!app) return;
    const open = typeof force === 'boolean' ? force : !app.classList.contains('console-open');
    app.classList.toggle('console-open', open);
    const burger = document.getElementById('console-burger');
    if (burger) burger.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function initTheme() {
    const app = document.getElementById('app');
    if (app) {
        let stored = null;
        try {
            stored = localStorage.getItem('toolregistry-console');
        } catch (e) {}
        const boot = document.documentElement.getAttribute('data-console-boot');
        app.dataset.console = (stored || boot) === 'collapsed' ? 'collapsed' : 'expanded';
        document.documentElement.removeAttribute('data-console-boot');
    }
    syncThemeControls();
}
