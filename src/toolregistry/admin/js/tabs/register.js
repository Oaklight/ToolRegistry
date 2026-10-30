// ============== Register (tool sources) ==============
//
// The panel is a thin skin over /api/sources/preview and /api/sources/register:
// preview lists what a source offers, and registration sends back exactly the
// names the operator ticked, so a source can never add a tool nobody asked for.
const REGISTER_KINDS = ['openapi', 'mcp', 'python'];

let _registerKind = 'openapi';
let _registerPreview = null;

function currentRegisterKind() {
    return REGISTER_KINDS.includes(_registerKind) ? _registerKind : 'openapi';
}

function refreshRegisterPanel() {
    // Re-render only when the panel is empty: switching away and back must
    // not discard a spec URL or the preview that was just loaded.
    const body = document.getElementById('register-body');
    if (!body || !body.querySelector('.register-form')) {
        renderRegisterForm();
    }
}

function setRegisterKind(kind) {
    if (!REGISTER_KINDS.includes(kind) || kind === _registerKind) return;
    _registerKind = kind;
    _registerPreview = null;
    renderRegisterForm();
}

function registerFieldsTemplate(kind) {
    if (kind === 'mcp') {
        return `
            <label class="form-label" data-i18n="register.url">Server URL</label>
            <input class="input" id="rf-url" placeholder="http://127.0.0.1:8000/mcp">
            <div class="form-hint" data-i18n="register.orCommand">or start a local server</div>
            <label class="form-label" data-i18n="register.command">Command</label>
            <input class="input" id="rf-command" placeholder="npx -y @modelcontextprotocol/server-filesystem /tmp">
        `;
    }
    if (kind === 'python') {
        return `
            <label class="form-label" data-i18n="register.module">Module</label>
            <input class="input" id="rf-module" placeholder="mypkg.tools">
            <label class="form-label" data-i18n="register.object">Class or function (optional)</label>
            <input class="input" id="rf-object" placeholder="leave empty for every public function">
        `;
    }
    return `
        <label class="form-label" data-i18n="register.specUrl">OpenAPI spec URL or path</label>
        <input class="input" id="rf-spec-url" placeholder="https://api.example.com/openapi.json">
        <label class="form-label" data-i18n="register.baseUrl">Base URL (optional)</label>
        <input class="input" id="rf-base-url" placeholder="defaults to servers[] in the spec">
    `;
}

function renderRegisterForm() {
    const body = document.getElementById('register-body');
    if (!body) return;
    const kind = currentRegisterKind();

    const seg = REGISTER_KINDS.map((id) => `
        <div class="${id === kind ? 'active' : ''}" role="radio" aria-checked="${id === kind}"
             tabindex="0" onclick="setRegisterKind('${id}')">
            <span>${escapeHtml(id.toUpperCase())}</span>
        </div>`).join('');

    body.innerHTML = `
        <div class="seg-control" role="radiogroup" aria-label="Source kind">${seg}</div>
        <div class="register-form">
            ${registerFieldsTemplate(kind)}
            <label class="form-label" data-i18n="register.namespace">Namespace (optional)</label>
            <input class="input" id="rf-namespace" placeholder="pets">
        </div>
        <div class="register-actions">
            <button class="btn btn-primary" onclick="previewRegisterSource()" id="register-preview-btn">
                <span data-i18n="register.preview">Preview tools</span>
            </button>
            <span class="form-hint" data-i18n="register.previewHint">Nothing is registered until you pick tools and confirm.</span>
        </div>
        <div id="register-preview"></div>
    `;
}

function readRegisterPayload() {
    const kind = currentRegisterKind();
    const value = (id) => (document.getElementById(id)?.value || '').trim();
    const payload = { kind };

    const namespace = value('rf-namespace');
    if (namespace) payload.namespace = namespace;

    if (kind === 'mcp') {
        const url = value('rf-url');
        const command = value('rf-command');
        if (url) payload.url = url;
        if (command) payload.command = command;
    } else if (kind === 'python') {
        payload.module = value('rf-module');
        const object = value('rf-object');
        if (object) payload.object = object;
    } else {
        payload.spec_url = value('rf-spec-url');
        const baseUrl = value('rf-base-url');
        if (baseUrl) payload.base_url = baseUrl;
    }
    return payload;
}

function registerError(message) {
    const box = document.getElementById('register-preview');
    if (box) {
        box.innerHTML = `<div class="register-error">${escapeHtml(message)}</div>`;
    }
    showToast(message, 'error');
}

async function previewRegisterSource() {
    const button = document.getElementById('register-preview-btn');
    if (button) button.disabled = true;
    try {
        const payload = readRegisterPayload();
        const result = await api.previewSource(payload);
        _registerPreview = result;
        renderRegisterPreview(result);
    } catch (e) {
        _registerPreview = null;
        registerError(e.message);
    } finally {
        if (button) button.disabled = false;
    }
}

function renderRegisterPreview(result) {
    const box = document.getElementById('register-preview');
    if (!box) return;
    if (!result.tools || result.tools.length === 0) {
        box.innerHTML = `<div class="empty-state"><div data-i18n="register.empty">This source offers no tools.</div></div>`;
        applyI18n();
        return;
    }

    const rows = result.tools.map((tool, index) => `
        <tr>
            <td style="width: 36px;">
                <label class="meta-checkbox">
                    <input type="checkbox" class="register-pick" data-name="${escapeHtml(tool.name)}"
                           ${tool.registered ? '' : 'checked'}>
                </label>
            </td>
            <td>
                <div class="mono" style="font-size: 0.8125rem;">${escapeHtml(tool.name)}</div>
                ${tool.registered ? '<span class="badge-source badge-source-native">registered</span>' : ''}
            </td>
            <td class="text-muted" style="font-size: 0.75rem;">${escapeHtml((tool.description || '').slice(0, 160))}</td>
            <td style="text-align: right; font-variant-numeric: tabular-nums;">${tool.parameter_count ?? ''}</td>
        </tr>`).join('');

    box.innerHTML = `
        <div class="register-summary">
            <span>${t('register.found', { count: result.count })}</span>
            ${result.already_registered ? `<span class="text-muted">${t('register.already', { count: result.already_registered })}</span>` : ''}
            <span class="register-summary-actions">
                <button class="btn btn-secondary btn-sm" onclick="setAllRegisterPicks(true)" data-i18n="register.selectAll">Select all</button>
                <button class="btn btn-secondary btn-sm" onclick="setAllRegisterPicks(false)" data-i18n="register.selectNone">Select none</button>
            </span>
        </div>
        <div class="table-container">
            <table>
                <thead><tr>
                    <th></th>
                    <th data-i18n="register.colName">Tool</th>
                    <th data-i18n="register.colDescription">Description</th>
                    <th style="text-align:right" data-i18n="register.colParams">Params</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
        <div class="register-actions">
            <button class="btn btn-primary" id="register-confirm-btn" onclick="confirmRegisterSelection()">
                <span data-i18n="register.confirm">Register selected</span>
            </button>
            <span class="form-hint" id="register-selection-count"></span>
        </div>
    `;
    document.querySelectorAll('.register-pick').forEach((box) => {
        box.addEventListener('change', updateRegisterSelectionCount);
    });
    applyI18n();
    updateRegisterSelectionCount();
}

function setAllRegisterPicks(checked) {
    document.querySelectorAll('.register-pick').forEach((box) => {
        box.checked = checked;
    });
    updateRegisterSelectionCount();
}

function selectedRegisterNames() {
    return [...document.querySelectorAll('.register-pick')]
        .filter((box) => box.checked)
        .map((box) => box.dataset.name);
}

function updateRegisterSelectionCount() {
    const label = document.getElementById('register-selection-count');
    if (label) label.textContent = t('register.selected', { count: selectedRegisterNames().length });
}

async function confirmRegisterSelection() {
    const selected = selectedRegisterNames();
    if (selected.length === 0) {
        showToast(t('register.nothingSelected'), 'error');
        return;
    }
    const button = document.getElementById('register-confirm-btn');
    if (button) button.disabled = true;
    try {
        const payload = readRegisterPayload();
        payload.selected = selected;
        const result = await api.registerSource(payload);
        showToast(t('register.done', { count: result.count }), 'success');
        refreshTools();
        refreshSources();
        // Re-preview so the "already registered" markers are accurate.
        previewRegisterSource();
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        if (button) button.disabled = false;
    }
}
