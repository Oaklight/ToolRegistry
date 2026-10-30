// ============== State Management ==============
async function exportState() {
    try {
        const state = await api.exportState();
        const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'toolregistry-state-' + new Date().toISOString().slice(0, 10) + '.json';
        a.click();
        URL.revokeObjectURL(url);
        showToast(t('toast.stateExported'), 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function handleImportFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    try {
        const text = await file.text();
        const state = JSON.parse(text);

        const disabled = state && typeof state === 'object' ? state.disabled : undefined;
        if (
            !state ||
            typeof state !== 'object' ||
            Array.isArray(state) ||
            (disabled !== undefined &&
                (typeof disabled !== 'object' || disabled === null || Array.isArray(disabled)))
        ) {
            showToast(t('toast.invalidState'), 'error');
            event.target.value = '';
            return;
        }

        showModal(t('modal.importState'), `
            <p>${t('confirm.importState')}</p>
            <p class="text-muted text-sm mt-2">${t('confirm.importOverwrite')}</p>
            <div class="mt-4">
                <strong>${t('confirm.disabledItems', {count: Object.keys(state.disabled || {}).length})}</strong>
            </div>
        `, async () => {
            try {
                await api.importState(state);
                showToast(t('toast.stateImported'), 'success');
                refreshAll();
            } catch (e) {
                showToast(e.message, 'error');
            }
        });
    } catch (e) {
        showToast(t('toast.invalidJson'), 'error');
    }

    event.target.value = '';
}


// ============== Config ==============
async function refreshConfig() {
    try {
        const config = await api.getConfig();
        document.getElementById('config-card').style.display = '';
        renderConfig(config);
    } catch (e) {
        // 404 means no config loaded — hide the card
        document.getElementById('config-card').style.display = 'none';
    }
}

function renderConfig(config) {
    const body = document.getElementById('config-body');
    const disabledList = (config.disabled || []).map(d =>
        `<span class="source-tool-chip">${escapeHtml(d)}</span>`
    ).join('') || `<span class="text-muted" style="font-size: 0.75rem;">${t('misc.none')}</span>`;
    const enabledList = (config.enabled || []).map(e =>
        `<span class="source-tool-chip">${escapeHtml(e)}</span>`
    ).join('') || `<span class="text-muted" style="font-size: 0.75rem;">${t('misc.none')}</span>`;

    body.innerHTML = `
        <div class="config-section">
            <div class="metadata-grid">
                <div class="meta-item"><span class="meta-label">${t('config.mode')}</span><span class="meta-value"><strong>${escapeHtml(config.mode)}</strong></span></div>
                <div class="meta-item"><span class="meta-label">${t('config.filePath')}</span><span class="meta-value" style="word-break: break-all;">${config.source ? escapeHtml(config.source) : `<span class="text-muted">${t('misc.none')}</span>`}</span></div>
            </div>
            <div class="meta-item mt-2">
                <span class="meta-label">${config.mode === 'denylist' ? t('config.disabled') : t('config.enabled')}</span>
                <div style="margin-top: 4px; display: flex; flex-wrap: wrap; gap: 4px;">
                    ${config.mode === 'denylist' ? disabledList : enabledList}
                </div>
            </div>
            ${config.source ? `<div class="mt-2">
                <button class="btn btn-primary btn-sm" onclick="saveCurrentStateToConfig()">${t('btn.saveToConfig')}</button>
                <span class="text-muted" style="font-size: 0.75rem; margin-left: 8px;">${t('config.saveHint')}</span>
            </div>` : ''}
        </div>`;
}

async function saveCurrentStateToConfig() {
    try {
        const state = await api.exportState();
        const disabled = Object.keys(state.disabled || {});
        const result = await api.updateConfig({ disabled });
        if (result.saved) {
            showToast(t('toast.configSaved'), 'success');
            refreshConfig();
        } else {
            showToast(t('toast.configSavedMemory'), 'success');
        }
    } catch (e) {
        showToast(t('toast.configSaveFailed', {error: e.message}), 'error');
    }
}

function refreshAll() {
    const activeTab = document.querySelector('.tab.active').dataset.tab;
    switchTab(activeTab);
}

async function showVersionInfo() {
    const versionFields = ['toolregistry', 'toolregistry_server', 'toolregistry_hub'];
    const linkFields = ['name_sep'];
    try {
        const data = await api.getInfo();
        const vRows = versionFields
            .filter(k => data[k] !== undefined)
            .map(k => `<tr>
                <td style="padding:5px 12px 5px 0;color:var(--text-muted);white-space:nowrap;font-size:0.85rem;">${escapeHtml(k)}</td>
                <td style="padding:5px 0;font-family:monospace;font-size:0.85rem;">${escapeHtml(String(data[k]))}</td>
            </tr>`).join('');
        const extraRows = Object.entries(data)
            .filter(([k]) => !versionFields.includes(k))
            .map(([k, v]) => `<tr>
                <td style="padding:5px 12px 5px 0;color:var(--text-muted);white-space:nowrap;font-size:0.85rem;">${escapeHtml(k)}</td>
                <td style="padding:5px 0;font-family:monospace;font-size:0.85rem;">${escapeHtml(String(v))}</td>
            </tr>`).join('');
        document.getElementById('version-modal-body').innerHTML = `
            <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
                ${vRows}${extraRows}
            </table>
            <div style="display:flex;gap:10px;justify-content:center;padding-top:14px;border-top:1px solid var(--border);">
                <a href="https://github.com/Oaklight/toolregistry-hub" target="_blank" rel="noopener"
                    class="btn btn-secondary btn-sm" style="text-decoration:none;">
                    <svg style="width:14px;height:14px;vertical-align:middle;margin-right:4px;" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.1 3.3 9.42 7.88 10.95.58.1.79-.25.79-.56v-2.02c-3.2.7-3.87-1.54-3.87-1.54-.52-1.33-1.28-1.68-1.28-1.68-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.19a11.1 11.1 0 0 1 2.9-.39c.98 0 1.97.13 2.9.39 2.2-1.5 3.17-1.19 3.17-1.19.63 1.59.23 2.76.11 3.05.74.8 1.19 1.83 1.19 3.09 0 4.43-2.7 5.4-5.27 5.69.41.36.78 1.06.78 2.13v3.16c0 .31.21.67.8.56C20.2 21.42 23.5 17.1 23.5 12 23.5 5.65 18.35.5 12 .5z"/>
                    </svg>${t('link.github')}
                </a>
                <a href="https://hub.docker.com/r/oaklight/toolregistry-hub-server" target="_blank" rel="noopener"
                    class="btn btn-secondary btn-sm" style="text-decoration:none;">
                    <svg style="width:14px;height:14px;vertical-align:middle;margin-right:4px;" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M13.983 11.078h2.119a.186.186 0 0 0 .186-.185V9.006a.186.186 0 0 0-.186-.186h-2.119a.185.185 0 0 0-.185.185v1.888c0 .102.083.185.185.185m-2.954-5.43h2.118a.186.186 0 0 0 .186-.186V3.574a.186.186 0 0 0-.186-.185h-2.118a.185.185 0 0 0-.185.185v1.888c0 .102.082.185.185.185m0 2.716h2.118a.187.187 0 0 0 .186-.186V6.29a.186.186 0 0 0-.186-.185h-2.118a.185.185 0 0 0-.185.185v1.887c0 .102.082.185.185.186m-2.93 0h2.12a.186.186 0 0 0 .184-.186V6.29a.185.185 0 0 0-.185-.185H8.1a.185.185 0 0 0-.185.185v1.887c0 .102.083.185.185.186m-2.964 0h2.119a.186.186 0 0 0 .185-.186V6.29a.185.185 0 0 0-.185-.185H5.136a.186.186 0 0 0-.186.185v1.887c0 .102.084.185.186.186m5.893 2.715h2.118a.186.186 0 0 0 .186-.185V9.006a.186.186 0 0 0-.186-.186h-2.118a.185.185 0 0 0-.185.185v1.888c0 .102.082.185.185.185m-2.93 0h2.12a.185.185 0 0 0 .184-.185V9.006a.185.185 0 0 0-.184-.186h-2.12a.185.185 0 0 0-.185.185v1.888c0 .102.083.185.185.185m-2.964 0h2.119a.185.185 0 0 0 .185-.185V9.006a.185.185 0 0 0-.185-.186h-2.12a.186.186 0 0 0-.186.186v1.887c0 .102.084.185.186.185m-2.92 0h2.12a.186.186 0 0 0 .184-.185V9.006a.185.185 0 0 0-.184-.186h-2.12a.185.185 0 0 0-.185.185v1.888c0 .102.083.185.185.185M23.763 9.89c-.065-.051-.672-.51-1.954-.51-.338.001-.676.03-1.01.087-.248-1.7-1.653-2.53-1.716-2.566l-.344-.199-.226.327c-.284.438-.49.922-.612 1.43-.23.97-.09 1.882.403 2.661-.595.332-1.55.413-1.744.42H.751a.751.751 0 0 0-.75.748 11.376 11.376 0 0 0 .692 4.062c.545 1.428 1.355 2.48 2.41 3.124 1.18.723 3.1 1.137 5.275 1.137.983.003 1.963-.086 2.93-.266a12.248 12.248 0 0 0 3.823-1.389c.98-.567 1.86-1.288 2.61-2.136 1.252-1.418 1.998-2.997 2.553-4.4h.221c1.372 0 2.215-.549 2.68-1.009.309-.293.55-.65.707-1.046l.098-.288z"/>
                    </svg>${t('link.docker')}
                </a>
                <a href="https://toolregistry.readthedocs.io" target="_blank" rel="noopener"
                    class="btn btn-secondary btn-sm" style="text-decoration:none;">
                    <svg style="width:14px;height:14px;vertical-align:middle;margin-right:4px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                    </svg>${t('link.docs')}
                </a>
            </div>`;
        document.getElementById('version-modal-overlay').classList.add('active');
        applyI18n();
    } catch (e) {
        showToast('Failed to fetch version info', 'error');
    }
}

function closeVersionModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('version-modal-overlay').classList.remove('active');
}


// ============== Registry Settings (name_sep) ==============
async function refreshRegistrySettings() {
    try {
        const info = await api.getInfo();
        renderRegistrySettings(info);
    } catch (e) {
        // ignore — info endpoint may not be available in all versions
    }
}

let _currentNameSep = '-';

function renderRegistrySettings(info) {
    const card = document.getElementById('registry-settings-card');
    if (!card) return;
    _currentNameSep = info.name_sep || '-';
    document.getElementById('name-sep-select').value = _currentNameSep;
    card.style.display = '';
}

function saveNameSep() {
    const sep = document.getElementById('name-sep-select').value;
    if (sep === _currentNameSep) return;

    // The registry setter re-keys every namespaced tool, so this is a
    // breaking rename, not a setting for future registrations.
    showModal(t('modal.changeNameSep'), `
        <p>${t('confirm.nameSepChange', { from: _currentNameSep, to: sep })}</p>
        <p class="text-muted text-sm mt-2">${t('confirm.nameSepWarn')}</p>
    `, async () => {
        try {
            await api.updateConfig({ name_sep: sep });
            _currentNameSep = sep;
            showToast(t('toast.configSavedMemory'), 'success');
            refreshAll();
            refreshRegistrySettings();
        } catch (e) {
            showToast(t('toast.configSaveFailed', { error: e.message }), 'error');
        }
    }, () => {
        document.getElementById('name-sep-select').value = _currentNameSep;
    });
}
