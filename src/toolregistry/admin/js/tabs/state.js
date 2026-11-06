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
    ).join('') || `<span class="text-muted" style="font-size: var(--text-small);">${t('misc.none')}</span>`;
    const enabledList = (config.enabled || []).map(e =>
        `<span class="source-tool-chip">${escapeHtml(e)}</span>`
    ).join('') || `<span class="text-muted" style="font-size: var(--text-small);">${t('misc.none')}</span>`;

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
                <span class="text-muted" style="font-size: var(--text-small); margin-left: 8px;">${t('config.saveHint')}</span>
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

// Refresh whatever section the console has open.  The rail replaced the old
// tab bar, so the selector has to read the console item, not `.tab`.
function refreshAll() {
    const active = document.querySelector('.console-item.active[data-tab]');
    switchTab(active ? active.dataset.tab : 'tools');
}

async function refreshSettings() {
    // The discovery card reads its own endpoint; it is rendered alongside the
    // registry settings because both describe the running registry.
    refreshDiscoveryCard();
    try {
        const info = await api.getInfo();
        renderRegistrySettings(info);
        renderAbout(info);
    } catch (e) {
        // ignore — info endpoint may not be available in all versions
    }
}

let _currentNameSep = '-';

function renderRegistrySettings(info) {
    const card = document.getElementById('registry-settings-card');
    if (!card) return;
    _currentNameSep = info.name_sep || '-';
    const select = document.getElementById('name-sep-select');
    // Only the hyphen is offered: OpenAI and Anthropic reject dots in tool
    // names.  A registry already on "." keeps the value listed while it is
    // live, so the operator can see why its tools are flagged and move off it.
    const choices = [['-', t('config.sepHyphen')]];
    if (_currentNameSep === '.') choices.push(['.', t('config.sepDotCurrent')]);
    select.innerHTML = choices
        .map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`)
        .join('');
    select.value = _currentNameSep;
    card.style.display = '';
}

//: Packages whose version the About card reports, in the order they matter.
const ABOUT_VERSIONS = ['toolregistry', 'toolregistry_server', 'toolregistry_hub'];

function renderAbout(info) {
    const body = document.getElementById('about-body');
    if (!body) return;
    const rows = ABOUT_VERSIONS
        .filter((key) => info[key])
        .map((key) => `
            <div class="meta-item">
                <span class="meta-label">${escapeHtml(key)}</span>
                <span class="meta-value ident">${escapeHtml(String(info[key]))}</span>
            </div>`)
        .join('');
    body.innerHTML = `
        <div class="metadata-grid">${rows}</div>
        <div class="about-links">
            <a class="btn btn-secondary btn-sm" href="https://github.com/Oaklight/ToolRegistry"
               target="_blank" rel="noopener noreferrer">
                <svg class="link-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.1 3.3 9.42 7.88 10.95.58.1.79-.25.79-.56v-2.02c-3.2.7-3.87-1.54-3.87-1.54-.52-1.33-1.28-1.68-1.28-1.68-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.56-.29-5.25-1.28-5.25-5.7 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.19a11.1 11.1 0 0 1 2.9-.39c.98 0 1.97.13 2.9.39 2.2-1.5 3.17-1.19 3.17-1.19.63 1.59.23 2.76.11 3.05.74.8 1.19 1.83 1.19 3.09 0 4.43-2.7 5.4-5.27 5.69.41.36.78 1.06.78 2.13v3.16c0 .31.21.67.8.56C20.2 21.42 23.5 17.1 23.5 12 23.5 5.65 18.35.5 12 .5z"/>
                </svg>${t('link.github')}
            </a>
            <a class="btn btn-secondary btn-sm" href="https://pypi.org/project/toolregistry/"
               target="_blank" rel="noopener noreferrer">
                <svg class="link-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/>
                    <path d="M12 22V12"/>
                    <path d="m3.3 7 7.7 4.7a2 2 0 0 0 2 0L20.7 7"/>
                </svg>${t('link.pypi')}
            </a>
            <a class="btn btn-secondary btn-sm" href="https://toolregistry.readthedocs.io"
               target="_blank" rel="noopener noreferrer">
                <svg class="link-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M12 7v14"/>
                    <path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>
                </svg>${t('link.docs')}
            </a>
        </div>`;
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
        } catch (e) {
            showToast(t('toast.configSaveFailed', { error: e.message }), 'error');
        }
    }, () => {
        document.getElementById('name-sep-select').value = _currentNameSep;
    });
}
