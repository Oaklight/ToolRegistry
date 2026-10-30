// ============== UI Helpers ==============
// Whether the registry has tool discovery enabled.  It decides whether a
// deferred tool is retrievable at all, so the Tools and Schema sections both
// read it; ui.js owns the value.
let _discoverEnabled = false;

function setDiscoverEnabled(enabled) {
    _discoverEnabled = !!enabled;
}

function updateConnectionStatus(connected) {
    const dot = document.getElementById('status-dot');
    const indicator = document.getElementById('status-indicator');
    if (connected) {
        dot.classList.remove('disconnected');
        indicator.title = t('status.connected');
    } else {
        dot.classList.add('disconnected');
        indicator.title = t('status.disconnected');
    }
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;

    toast.innerHTML = `
        <span class="toast-dot"></span>
        <div class="toast-content">
            <div class="toast-message">${message}</div>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('hiding');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

let _modalOnCancel = null;

function showModal(title, content, onConfirm, onCancel) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = content;
    document.getElementById('modal-overlay').classList.add('active');
    _modalOnCancel = onCancel || null;

    const confirmBtn = document.getElementById('modal-confirm');
    confirmBtn.onclick = () => {
        _modalOnCancel = null;
        if (onConfirm) onConfirm();
        closeModal();
    };
}

function closeModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('modal-overlay').classList.remove('active');
    if (_modalOnCancel) {
        _modalOnCancel();
        _modalOnCancel = null;
    }
}

function switchTab(tabName) {
    // Update console items
    document.querySelectorAll('.console-item[data-tab]').forEach(item => {
        const active = item.dataset.tab === tabName;
        item.classList.toggle('active', active);
        if (active) item.setAttribute('aria-current', 'page');
        else item.removeAttribute('aria-current');
    });

    // A picked section closes the drawer on narrow viewports.
    toggleConsole(false);

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.style.display = content.id === 'tab-' + tabName ? 'block' : 'none';
    });

    // Load data for the tab
    if (tabName === 'tools') {
        refreshTools();
        refreshStats();
    } else if (tabName === 'logs') {
        refreshLogs();
        refreshLogStats();
    } else if (tabName === 'sources') {
        refreshSources();
    } else if (tabName === 'permissions') {
        refreshPermissions();
    } else if (tabName === 'state') {
        refreshConfig();
        refreshRegistrySettings();
    } else if (tabName === 'schema') {
        api.getInfo().then(info => {
            const enabled = !!info.discover_enabled;
            // The sub-tab stays visible when discovery is off: hiding it is
            // what made "where are discover_tools and call_deferred?" hard to
            // answer.  It opens with the explanation instead.
            const discoverBtn = document.getElementById('schema-subtab-discover');
            if (discoverBtn) {
                discoverBtn.classList.toggle('disabled', !enabled);
                discoverBtn.title = enabled ? '' : t('discovery.offHint');
            }
            setDiscoverEnabled(enabled);
            switchSchemaSubTab(_activeSchemaSubTab);
        }).catch(() => switchSchemaSubTab(_activeSchemaSubTab));
    }
}

// ============== Utilities ==============
// Values interpolated into an inline handler need JS escaping, not HTML
// escaping: a namespace or tool name may contain a quote.
function escapeJs(value) {
    return String(value)
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\"')
        .replace(/\r?\n/g, '\\n');
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
