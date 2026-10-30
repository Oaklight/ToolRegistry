// ============== Tools ==============
let _overrideNames = new Set();

async function refreshTools() {
    try {
        const data = await api.getTools();
        allTools = data.tools || [];
        // Overrides are a separate record; failing to fetch them must not
        // hide the tool list, so the badge simply stays absent.
        try {
            const listing = await api.listOverrides();
            _overrideNames = new Set((listing.overrides || []).map((o) => o.name));
        } catch (e) {
            _overrideNames = new Set();
        }
        updateConnectionStatus(true);
        updateNamespaceFilter(allTools);
        // Re-apply the active search/filters: rendering allTools here
        // left the controls showing a query that no longer applied.
        filterTools();
    } catch (e) {
        document.getElementById('tools-body').innerHTML =
            `<tr><td colspan="7" class="empty-state"><div class="text-error">${e.message}</div></td></tr>`;
    }
}

// Tag color mapping for known ToolTag values
const TAG_CLASSES = {
    'read_only': 'badge-tag-read_only',
    'destructive': 'badge-tag-destructive',
    'slow': 'badge-tag-slow',
    'network': 'badge-tag-network',
    'privileged': 'badge-tag-privileged',
    'file_system': 'badge-tag-file_system',
};

function normalizeTagKey(tag) {
    // Strip "ToolTag." prefix and lowercase for matching
    const key = tag.replace(/^ToolTag\./i, '').toLowerCase();
    return key;
}

// OpenAI and Anthropic accept [A-Za-z0-9_-] only (64 chars max); Gemini also
// allows dots.  A name outside that set is stored as-is, so the row says so.
function isProviderSafeName(name) {
    return /^[A-Za-z0-9_-]{1,64}$/.test(name || '');
}

function sourceBadgeButton(source, visible) {
    if (!visible) return '';
    return `<button type="button" class="source-badge-link" onclick="focusSources('${escapeJs(source)}')"
        title="${t('source.showInPanel')}">${escapeHtml(source)}</button>`;
}

function renderSourceBadge(source) {
    if (!source) return '';
    const cls = 'badge-source badge-source-' + source;
    return `<span class="${cls}">${escapeHtml(source)}</span>`;
}

function renderTagBadges(tags, systemOnly) {
    if (!tags || tags.length === 0) return '';
    let filtered = tags;
    if (systemOnly) {
        filtered = tags.filter(tag => !!TAG_CLASSES[normalizeTagKey(tag)]);
    }
    // Sort: system tags first, then custom tags
    const sorted = [...filtered].sort((a, b) => {
        const aIsSystem = !!TAG_CLASSES[normalizeTagKey(a)];
        const bIsSystem = !!TAG_CLASSES[normalizeTagKey(b)];
        if (aIsSystem && !bIsSystem) return -1;
        if (!aIsSystem && bIsSystem) return 1;
        return a.localeCompare(b);
    });
    return sorted.map(tag => {
        const key = normalizeTagKey(tag);
        const cls = TAG_CLASSES[key] || 'badge-tag-custom';
        const label = TAG_CLASSES[key] ? key : tag;
        return `<span class="badge-tag ${cls}">${escapeHtml(label)}</span>`;
    }).join('');
}

function renderMetaIcons(tool) {
    let icons = '';
    if (tool.locality && tool.locality !== 'any') {
        const cls = tool.locality === 'local' ? 'badge-locality-local' : 'badge-locality-remote';
        icons += `<span class="badge-locality ${cls}" title="Locality: ${tool.locality}">${tool.locality}</span>`;
    }
    if (tool.is_async) {
        icons += `<span class="meta-icon" title="Async">async</span>`;
    }
    return icons ? `<span class="tool-meta-icons">${icons}</span>` : '';
}

function renderMetaToggle(toolName, field, checked, disabled) {
    const dis = disabled ? 'disabled' : '';
    const cls = disabled ? 'meta-checkbox meta-checkbox-disabled' : 'meta-checkbox';
    const title = disabled ? t('misc.nativeThought') : '';
    return `<label class="${cls}" style="justify-content: center;" ${title ? `title="${title}"` : ''}>
        <input type="checkbox" ${checked ? 'checked' : ''} ${dis}
            onclick="event.stopPropagation()"
            onchange="toggleToolMeta('${escapeHtml(toolName)}', '${field}', this.checked)">
    </label>`;
}

function renderPermissionBadge(perm) {
    if (!perm) return '<span class="placeholder-dash">&mdash;</span>';
    const cls = 'badge-' + perm.result;
    const basis = perm.rule_name ? `${perm.rule_name}: ${perm.reason}` : (perm.reason || '');
    // The API evaluates the policy with {} arguments, so parameter-
    // dependent rules may decide differently for a real call.
    const title = (basis ? basis + ' — ' : '') + t('perm.emptyArgsNote');
    return `<span class="${cls}" title="${escapeHtml(title)}">${perm.result}</span>`;
}

function renderTools(tools, filtersActive = false) {
    const tbody = document.getElementById('tools-body');

    if (tools.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="7" class="empty-state">
                <div class="empty-state-icon">${filtersActive ? t('empty.filteredTools') : t('empty.tools')}</div>
                <div class="empty-state-text">${filtersActive ? t('empty.filteredToolsHint') : t('empty.toolsHint')}</div>
                ${filtersActive ? `<button class="btn btn-secondary btn-sm" style="margin-top:12px;" onclick="clearToolFilters()">${t('btn.clearFilters')}</button>` : ''}
            </td></tr>`;
        return;
    }

    // Group: standalone tools (no namespace) go under "default", rest by namespace
    const nsMap = {};
    tools.forEach(t => {
        const ns = t.namespace || 'default';
        if (!nsMap[ns]) nsMap[ns] = [];
        nsMap[ns].push(t);
    });

    let html = '';

    // Render all groups (default first, then sorted)
    const nsKeys = Object.keys(nsMap).sort((a, b) => {
        if (a === 'default') return -1;
        if (b === 'default') return 1;
        return a.localeCompare(b);
    });

    nsKeys.forEach(ns => {
        const children = nsMap[ns];
        const allEnabled = children.every(t => t.enabled);
        const allThink = children.every(t => t.think_augment);
        const anyThink = children.some(t => t.think_augment);
        const allDefer = children.every(t => t.defer);
        const anyDefer = children.some(t => t.defer);
        const nsId = 'ns-' + ns.replace(/[^a-zA-Z0-9_]/g, '_');
        const isDefault = ns === 'default';
        const nsSources = [...new Set(children.map(t => t.source))];
        const nsSourceBadge = nsSources.length === 1 ? renderSourceBadge(nsSources[0]) : '';
        html += `
        <tr class="ns-row" onclick="toggleNsGroup('${nsId}')">
            <td><span class="ns-chevron">${SVG_CHEVRON}</span></td>
            <td>
                <button type="button" class="ns-link" onclick="event.stopPropagation(); toggleNsGroup('${nsId}')" title="${t('ns.toggleGroup')}">${escapeHtml(ns)}</button>
                ${nsSourceBadge ? `<button type="button" class="source-badge-link" onclick="event.stopPropagation(); focusSources('${escapeJs(nsSources[0])}')" title="${t('source.showInPanel')}">${escapeHtml(nsSources[0])}</button>` : ''}
                <span class="text-muted" style="margin-left: 8px; font-size: 0.6875rem;">${children.length > 1 ? t('misc.toolCountPlural', {count: children.length}) : t('misc.toolCount', {count: children.length})}</span>
            </td>
            <td class="col-think" onclick="event.stopPropagation()">
                <label class="meta-checkbox" style="justify-content: center;" title="${t('misc.thinkAugmentedAll')}">
                    <input type="checkbox" ${allThink ? 'checked' : ''} data-indeterminate="${anyThink && !allThink}"
                        onchange="toggleNamespaceMeta('${escapeHtml(ns)}', 'think_augment', this.checked)">
                </label>
            </td>
            <td class="col-defer" onclick="event.stopPropagation()">
                <label class="meta-checkbox" style="justify-content: center;" title="${t('misc.deferredAll')}">
                    <input type="checkbox" ${allDefer ? 'checked' : ''} data-indeterminate="${anyDefer && !allDefer}"
                        onchange="toggleNamespaceMeta('${escapeHtml(ns)}', 'defer', this.checked)">
                </label>
            </td>
            <td class="col-permission"></td>
            <td>
                ${isDefault ? '' : `<label class="toggle-switch toggle-ns" title="${allEnabled ? t('misc.clickToDisableAll') : t('misc.clickToEnableAll')}" onclick="event.stopPropagation()">
                    <input type="checkbox" ${allEnabled ? 'checked' : ''}
                        onchange="toggleNamespace('${escapeHtml(ns)}', this.checked)">
                    <span class="toggle-slider"></span>
                </label>`}
            </td>
            <td class="col-reason"></td>
        </tr>`;

        children.forEach(tool => {
            const shortName = (!isDefault && (tool.name.startsWith(ns + '-') || tool.name.startsWith(ns + '.')))
                ? tool.name.slice(ns.length + 1) : tool.name;
            const tagBadges = renderTagBadges(tool.tags, true);
            const metaIcons = renderMetaIcons(tool);
            const permBadge = renderPermissionBadge(tool.permission);
            const sourceBadge = nsSources.length > 1 ? renderSourceBadge(tool.source) : '';
            const nameWarning = isProviderSafeName(tool.name)
                ? ''
                : `<span class="badge-name-warning" title="${t('tools.unsafeNameHint')}">!</span>`;
            html += `
        <tr class="ns-child-row" data-ns-group="${nsId}">
            <td></td>
            <td>
                <span class="ns-child-name-link" onclick="event.stopPropagation(); showToolDetailModal('${escapeHtml(tool.name)}')">${escapeHtml(shortName)}</span>
                ${nameWarning}
                ${_overrideNames.has(tool.name) ? `<span class="badge-override">${t('override.badge')}</span>` : ''}
                <span class="tool-badges">${tagBadges}</span>
                ${sourceBadgeButton(tool.source, nsSources.length > 1)}
                ${metaIcons}
            </td>
            <td class="col-think" onclick="event.stopPropagation()">${renderMetaToggle(tool.name, 'think_augment', tool.think_augment, false)}</td>
            <td class="col-defer" onclick="event.stopPropagation()">${renderMetaToggle(tool.name, 'defer', tool.defer, false)}</td>
            <td>${permBadge}</td>
            <td>
                <label class="toggle-switch" title="${tool.enabled ? t('misc.clickToDisable') : t('misc.clickToEnable')}">
                    <input type="checkbox" ${tool.enabled ? 'checked' : ''}
                        onchange="toggleTool('${escapeHtml(tool.name)}', this.checked)">
                    <span class="toggle-slider"></span>
                </label>
            </td>
            <td class="col-reason"><span class="col-reason-text" title="${escapeHtml(tool.reason || '')}">${tool.reason ? escapeHtml(tool.reason) : '<span class="placeholder-dash">&mdash;</span>'}</span></td>
        </tr>`;
        });
    });

    tbody.innerHTML = html;
    // Namespace checkboxes are tri-state: some children on means
    // indeterminate, which can only be set from script.
    tbody.querySelectorAll('input[data-indeterminate="true"]').forEach(cb => {
        cb.indeterminate = true;
    });
    // Keep whatever expand/collapse state the operator chose; a refresh used
    // to force every group open again.
    if (_allExpanded) expandAllGroups();
    else collapseAllGroups();
}

function toggleNsGroup(nsId) {
    const rows = document.querySelectorAll(`[data-ns-group="${nsId}"]`);
    const parentRow = rows.length > 0 ? rows[0].previousElementSibling : null;
    // Walk up to find the .ns-row
    let nsRow = parentRow;
    while (nsRow && !nsRow.classList.contains('ns-row')) {
        nsRow = nsRow.previousElementSibling;
    }
    if (!nsRow) return;

    const isExpanded = nsRow.classList.toggle('expanded');
    rows.forEach(row => row.classList.toggle('visible', isExpanded));
}

let _allExpanded = true;

function expandAllGroups() {
    document.querySelectorAll('.ns-row').forEach(row => row.classList.add('expanded'));
    document.querySelectorAll('.ns-child-row').forEach(row => row.classList.add('visible'));
    _allExpanded = true;
    updateToggleBtn();
}

function collapseAllGroups() {
    document.querySelectorAll('.ns-row').forEach(row => row.classList.remove('expanded'));
    document.querySelectorAll('.ns-child-row').forEach(row => row.classList.remove('visible'));
    _allExpanded = false;
    updateToggleBtn();
}

function toggleAllGroups() {
    if (_allExpanded) { collapseAllGroups(); } else { expandAllGroups(); }
}

function updateToggleBtn() {
    const btn = document.getElementById('toggle-expand-btn');
    const icon = document.getElementById('toggle-expand-icon');
    if (!btn || !icon) return;
    if (_allExpanded) {
        btn.title = t('misc.collapseAll');
        icon.innerHTML = '<path d="M4 7l4-4 4 4"/><path d="M4 13l4-4 4 4"/>';
    } else {
        btn.title = t('misc.expandAll');
        icon.innerHTML = '<path d="M4 3l4 4 4-4"/><path d="M4 9l4 4 4-4"/>';
    }
}

function filterTools() {
    const search = document.getElementById('tool-search').value.toLowerCase();
    const namespace = document.getElementById('namespace-filter').value;
    const status = document.getElementById('status-filter').value;
    const tag = document.getElementById('tag-filter').value;
    const locality = document.getElementById('locality-filter').value;
    const source = document.getElementById('source-filter').value;

    const filtered = allTools.filter(tool => {
        const matchSearch = tool.name.toLowerCase().includes(search);
        const matchNamespace = !namespace || (tool.namespace || 'default') === namespace;
        const matchStatus = !status ||
            (status === 'enabled' && tool.enabled) ||
            (status === 'disabled' && !tool.enabled);
        const matchTag = !tag || (tool.tags && tool.tags.includes(tag));
        const matchLocality = !locality || tool.locality === locality;
        const matchSource = !source || tool.source === source;
        return matchSearch && matchNamespace && matchStatus && matchTag && matchLocality && matchSource;
    });

    const filtersActive = Boolean(search || namespace || status || tag || locality || source);
    renderTools(filtered, filtersActive);
}

function clearToolFilters() {
    ['tool-search', 'namespace-filter', 'status-filter', 'tag-filter', 'locality-filter', 'source-filter']
        .forEach(id => { document.getElementById(id).value = ''; });
    filterTools();
}

function updateNamespaceFilter(tools) {
    const namespaces = [...new Set(tools.map(t => t.namespace || 'default'))].sort((a, b) => {
        if (a === 'default') return -1;
        if (b === 'default') return 1;
        return a.localeCompare(b);
    });
    const select = document.getElementById('namespace-filter');
    const currentValue = select.value;

    select.innerHTML = `<option value="">${t('filter.allNamespaces')}</option>` +
        namespaces.map(ns => `<option value="${escapeHtml(ns)}">${escapeHtml(ns)}</option>`).join('');

    select.value = currentValue;

    // Update tag filter
    const allTags = [...new Set(tools.flatMap(t => t.tags || []))].sort();
    const tagSelect = document.getElementById('tag-filter');
    const currentTag = tagSelect.value;
    tagSelect.innerHTML = `<option value="">${t('filter.allTags')}</option>` +
        allTags.map(tag => `<option value="${escapeHtml(tag)}">${escapeHtml(tag)}</option>`).join('');
    tagSelect.value = currentTag;
}

function showDisableToolModal(name) {
    showModal(t('modal.disableTool'), `
        <div class="form-group">
            <label class="form-label">${t('modal.toolLabel')}<strong>${escapeHtml(name)}</strong></label>
        </div>
        <div class="form-group">
            <label class="form-label">${t('label.reasonOptional')}</label>
            <input type="text" class="input" id="disable-reason" placeholder="${t('label.enterReason')}">
        </div>
    `, async () => {
        const reason = document.getElementById('disable-reason').value;
        await disableTool(name, reason);
    }, () => {
        // On cancel, revert the toggle visually
        refreshTools();
    });
}

async function toggleTool(name, checked) {
    if (checked) {
        await enableTool(name);
    } else {
        showDisableToolModal(name);
    }
}

async function toggleNamespace(ns, checked) {
    if (checked) {
        await enableNamespace(ns);
    } else {
        showDisableNamespaceModal(ns);
    }
}

async function toggleToolMeta(name, field, value) {
    try {
        await api.updateToolMetadata(name, { [field]: value });
        showToast(t('toast.metaUpdated', {field, name, state: value ? t('meta.enabled') : t('meta.disabled')}), 'success');
        refreshTools();
    } catch (e) {
        showToast(e.message, 'error');
        refreshTools();
    }
}

async function toggleNamespaceMeta(ns, field, value) {
    try {
        await api.updateNamespaceMetadata(ns, { [field]: value });
        showToast(t('toast.nsMetaUpdated', {field, name: ns, state: value ? t('meta.enabled') : t('meta.disabled')}), 'success');
        refreshTools();
    } catch (e) {
        showToast(e.message, 'error');
        refreshTools();
    }
}

async function enableTool(name) {
    try {
        await api.enableTool(name);
        showToast(t('toast.toolEnabled', {name}), 'success');
        refreshTools();
        refreshStats();
    } catch (e) {
        showToast(e.message, 'error');
        refreshTools();
    }
}

async function disableTool(name, reason) {
    try {
        await api.disableTool(name, reason);
        showToast(t('toast.toolDisabled', {name}), 'success');
        refreshTools();
        refreshStats();
    } catch (e) {
        showToast(e.message, 'error');
    }
}


// ============== Stats ==============
async function refreshStats() {
    try {
        const data = await api.getTools();
        const tools = data.tools || [];
        const enabled = tools.filter(t => t.enabled).length;
        const disabled = tools.filter(t => !t.enabled).length;
        const namespaces = new Set(tools.map(t => t.namespace).filter(Boolean)).size;
        const deferred = tools.filter(t => t.defer);

        try {
            const info = await api.getInfo();
            _discoverEnabled = !!info.discover_enabled;
        } catch (e) {
            _discoverEnabled = false;
        }
        renderDeferredWarning(deferred.length);

        // Each card links to where its number comes from: the tools list
        // filtered by status, or the namespaces panel.
        document.getElementById('stats-grid').innerHTML = `
            <button type="button" class="stat-card" onclick="showToolsByStatus('')" title="${t('stat.showAll')}">
                <div class="stat-value">${tools.length}</div>
                <div class="stat-label">${t('stat.totalTools')}</div>
            </button>
            <button type="button" class="stat-card" onclick="showToolsByStatus('enabled')" title="${t('stat.showEnabled')}">
                <div class="stat-value text-success">${enabled}</div>
                <div class="stat-label">${t('stat.enabled')}</div>
            </button>
            <button type="button" class="stat-card" onclick="showToolsByStatus('disabled')" title="${t('stat.showDisabled')}">
                <div class="stat-value text-error">${disabled}</div>
                <div class="stat-label">${t('stat.disabled')}</div>
            </button>
            <button type="button" class="stat-card" onclick="showNamespaceSummary()" title="${t('stat.showNamespaces')}">
                <div class="stat-value">${namespaces}</div>
                <div class="stat-label">${t('stat.namespaces')}</div>
            </button>
        `;
    } catch (e) {
        document.getElementById('stats-grid').innerHTML =
            `<div class="stat-card"><div class="stat-label text-error">${e.message}</div></div>`;
    }
}


// Every section links into this one through gotoTools: the overview cards,
// the Namespaces counts, the Sources cards and the Register result all land
// here with the filter that explains the number they came from.
function setFilterValue(id, value, allowNewOption) {
    const select = document.getElementById(id);
    if (!select) return;
    if (allowNewOption && value && value !== '') {
        if (![...select.options].some((option) => option.value === value)) {
            select.add(new Option(value, value));
        }
    }
    select.value = value || '';
}

function gotoTools(filters = {}) {
    switchTab('tools');
    setFilterValue('namespace-filter', filters.namespace, true);
    setFilterValue('source-filter', filters.source, true);
    setFilterValue('status-filter', filters.status);
    const search = document.getElementById('tool-search');
    if (search) search.value = filters.search || '';
    filterTools();
}

function showToolsByStatus(status) {
    gotoTools({ status });
}

// The overview's namespace card is the namespace view now that the panel has
// folded into this list: it collapses every group, leaving the namespace rows
// as the summary.
function showNamespaceSummary() {
    switchTab('tools');
    setFilterValue('namespace-filter', '');
    setFilterValue('status-filter', '');
    const search = document.getElementById('tool-search');
    if (search) search.value = '';
    _allExpanded = false;
    filterTools();
}

function showToolsForNamespace(namespace, status) {
    gotoTools({ namespace, status });
}


// ============== Tool Detail Modal ==============
async function showToolDetailModal(toolName) {
    try {
        const tool = await api.getTool(toolName);
        document.getElementById('detail-title').textContent = tool.name;

        // The override record is not part of the tool payload; ask for it so
        // the modal can offer Restore only when there is something to restore.
        let overridden = false;
        try {
            const listing = await api.listOverrides();
            overridden = (listing.overrides || []).some((o) => o.name === tool.name);
        } catch (e) {
            overridden = false;
        }

        const meta = tool.metadata || {};
        const systemTags = (meta.tags || []);
        const customTags = (meta.custom_tags || []);

        let html = '';

        const perm = tool.permission;
        const permHtml = perm
            ? `<span class="badge-${perm.result}">${perm.result}</span>${perm.rule_name ? ` <span class="text-muted" style="font-size: 0.75rem;">(${escapeHtml(perm.rule_name)})</span>` : ''}`
            : `<span class="text-muted">${t('detail.noPolicy')}</span>`;

        // Basic info
        html += `<div class="detail-section">
            <div class="detail-section-title">${t('detail.basicInfo')}</div>
            <div class="metadata-grid">
                <div class="meta-item"><span class="meta-label">${t('detail.name')}</span><span class="meta-value">${escapeHtml(tool.name)}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.namespace')}</span><span class="meta-value">${escapeHtml(tool.namespace || 'default')}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.methodName')}</span><span class="meta-value">${escapeHtml(tool.method_name || tool.name)}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.source')}</span><span class="meta-value">${renderSourceBadge(meta.source || 'native')}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.status')}</span><span class="meta-value">${tool.enabled ? `<span class="text-success">${t('stat.enabled')}</span>` : `<span class="text-error">${t('stat.disabled')}</span>`}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.permission')}</span><span class="meta-value">${permHtml}</span></div>
            </div>
            ${meta.source_detail ? `<div class="meta-item mt-2"><span class="meta-label">${t('detail.sourceDetail')}</span><span class="meta-value" style="word-break: break-all;">${escapeHtml(meta.source_detail)}</span></div>` : ''}
            ${tool.reason ? `<div class="meta-item mt-2"><span class="meta-label">${t('detail.disableReason')}</span><span class="meta-value text-error">${escapeHtml(tool.reason)}</span></div>` : ''}
            ${perm && perm.reason ? `<div class="meta-item mt-2"><span class="meta-label">${t('detail.permReason')}</span><span class="meta-value">${escapeHtml(perm.reason)}</span></div>` : ''}
            <div class="mt-2"><span class="meta-label">${t('detail.description')}</span><p style="font-size: 0.8125rem; margin-top: 4px;">${escapeHtml(tool.description || '')}</p></div>
        </div>`;

        // Metadata
        html += `<div class="detail-section">
            <div class="detail-section-title">${t('detail.metadata')}</div>
            <div class="metadata-grid">
                <div class="meta-item"><span class="meta-label">${t('detail.locality')}</span><span class="meta-value">${meta.locality || 'any'}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.async')}</span><span class="meta-value">${meta.is_async ? t('meta.yes') : t('meta.no')}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.concurrencySafe')}</span><span class="meta-value">${meta.is_concurrency_safe !== false ? t('meta.yes') : t('meta.no')}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.thinkAugment')}</span><span class="meta-value"><label class="meta-checkbox"><input type="checkbox" ${meta.think_augment ? 'checked' : ''} onchange="toggleToolMeta('${escapeHtml(tool.name)}', 'think_augment', this.checked)"></label></span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.timeout')}</span><span class="meta-value">${meta.timeout != null ? meta.timeout + 's' : 'None'}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.maxResultSize')}</span><span class="meta-value">${meta.max_result_size != null ? meta.max_result_size + ' chars' : 'None'}</span></div>
                <div class="meta-item"><span class="meta-label">${t('detail.deferred')}</span><span class="meta-value"><label class="meta-checkbox"><input type="checkbox" ${meta.defer ? 'checked' : ''} onchange="toggleToolMeta('${escapeHtml(tool.name)}', 'defer', this.checked)"></label></span></div>
                <div class="meta-item" style="grid-column:1/-1;"><span class="meta-label">${t('detail.searchHint')}</span><span class="meta-value" style="display:flex;gap:4px;align-items:center;margin-top:2px;">
                    <input type="text" id="sh-modal-${escapeHtml(tool.name)}" value="${escapeHtml(meta.search_hint || '')}" placeholder="${t('detail.searchHintPlaceholder')}"
                        style="flex:1;padding:3px 7px;font-size:0.8rem;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-secondary);color:var(--text-primary);"
                        onkeydown="if(event.key==='Enter')saveSearchHint('${escapeHtml(tool.name)}',this,false)">
                    <button class="btn btn-secondary btn-sm" onclick="saveSearchHint('${escapeHtml(tool.name)}',document.getElementById('sh-modal-${escapeHtml(tool.name)}'),false)">${t('btn.apply')}</button>
                </span></div>
            </div>
            ${systemTags.length > 0 ? `<div class="mt-2"><span class="meta-label">${t('detail.tags')}</span><div style="margin-top: 4px;">${renderTagBadges(systemTags)}</div></div>` : ''}
            ${customTags.length > 0 ? `<div class="mt-2"><span class="meta-label">${t('detail.customTags')}</span><div style="margin-top: 4px;">${renderTagBadges(customTags)}</div></div>` : ''}
            ${meta.extra && Object.keys(meta.extra).length > 0 ? `<div class="mt-2"><span class="meta-label">${t('detail.extra')}</span><pre style="margin-top: 4px; background: var(--bg-primary); padding: 8px; border-radius: var(--radius-sm); font-size: 0.75rem;">${escapeHtml(JSON.stringify(meta.extra, null, 2))}</pre></div>` : ''}
        </div>`;

        // Schema (collapsible)
        html += `<div class="detail-section">
            <div class="schema-toggle" onclick="this.classList.toggle('expanded'); this.nextElementSibling.classList.toggle('visible');">
                <span class="expand-icon">${SVG_CHEVRON}</span>
                <span class="detail-section-title" style="margin-bottom: 0;">${t('detail.schema')}</span>
            </div>
            <div class="schema-content">
                <pre style="background: var(--bg-sunken); color: var(--text-primary); border: 1px solid var(--border); padding: 12px; border-radius: var(--radius-sm); font-size: 0.75rem; overflow-x: auto; white-space: pre-wrap; font-family: var(--font-mono);">${escapeHtml(JSON.stringify(tool.schema, null, 2))}</pre>
            </div>
        </div>`;

        html += `<div class="detail-section">
            <div class="detail-section-title">${t('override.title')}
                ${overridden ? `<span class="badge-tag-slow" style="margin-left: 6px;">${t('override.badge')}</span>` : ''}
            </div>
            <div class="register-actions">
                <button class="btn btn-secondary btn-sm" onclick="openOverrideModal('${escapeHtml(tool.name)}')">${t('override.edit')}</button>
                ${overridden ? `<button class="btn btn-danger btn-sm" onclick="restoreToolOverride('${escapeHtml(tool.name)}')">${t('override.restore')}</button>` : ''}
            </div>
        </div>`;

        document.getElementById('detail-body').innerHTML = html;
        document.getElementById('detail-overlay').classList.add('active');
    } catch (e) {
        showToast(t('toast.detailFailed', {error: e.message}), 'error');
    }
}

function closeDetailModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('detail-overlay').classList.remove('active');
}


// A deferred tool is left out of the schema, and only discover_tools can
// bring it back.  With discovery off, nothing registers that tool, so the
// defer flag makes the tool unreachable rather than deferred.
function renderDeferredWarning(deferredCount) {
    const box = document.getElementById('deferred-warning');
    if (!box) return;
    if (deferredCount === 0 || _discoverEnabled) {
        box.style.display = 'none';
        box.innerHTML = '';
        return;
    }
    box.style.display = '';
    box.innerHTML = `<strong>${t('discovery.offTitle', { count: deferredCount })}</strong>
        <span>${t('discovery.offHint')}</span>`;
}

// ============== Tool override ==============
// An override swaps the registered definition for an edited copy and keeps
// the displaced one, so Restore puts the source's own definition back.
async function openOverrideModal(name) {
    let tool;
    try {
        tool = await api.getTool(name);
    } catch (e) {
        showToast(e.message, 'error');
        return;
    }
    const meta = tool.metadata || {};
    const tags = (meta.tags || [])
        .map((tag) => normalizeTagKey(tag))
        .join(', ');
    const customTags = (meta.custom_tags || []).join(', ');

    const content = `
        <div class="form-group">
            <label class="form-label" for="ov-description">${t('override.description')}</label>
            <textarea id="ov-description" class="input" rows="4"
                style="width:100%;resize:vertical;">${escapeHtml(tool.description || '')}</textarea>
        </div>
        <div class="form-group">
            <label class="form-label" for="ov-tags">${t('override.tags')}</label>
            <input id="ov-tags" class="input" style="width:100%;" value="${escapeHtml(tags)}">
        </div>
        <div class="form-group">
            <label class="form-label" for="ov-custom-tags">${t('override.customTags')}</label>
            <input id="ov-custom-tags" class="input" style="width:100%;" value="${escapeHtml(customTags)}">
        </div>
    `;

    showModal(t('override.title'), content, async () => {
        const changes = {};
        const description = document.getElementById('ov-description')?.value ?? '';
        if (description !== (tool.description || '')) changes.description = description;

        const tagList = (document.getElementById('ov-tags')?.value || '')
            .split(',').map((value) => value.trim()).filter(Boolean);
        const currentTags = (meta.tags || []).map((tag) => normalizeTagKey(tag));
        if (tagList.slice().sort().join(',') !== currentTags.slice().sort().join(',')) {
            changes.tags = tagList;
        }

        const customList = (document.getElementById('ov-custom-tags')?.value || '')
            .split(',').map((value) => value.trim()).filter(Boolean);
        if (customList.slice().sort().join(',') !== (meta.custom_tags || []).slice().sort().join(',')) {
            changes.custom_tags = customList;
        }

        if (Object.keys(changes).length === 0) return;
        try {
            await api.overrideTool(name, changes);
            showToast(t('override.saved'), 'success');
            refreshTools();
            showToolDetailModal(name);
        } catch (e) {
            showToast(e.message, 'error');
        }
    });
}

async function restoreToolOverride(name) {
    try {
        await api.restoreOverride(name);
        showToast(t('override.restored'), 'success');
        refreshTools();
        showToolDetailModal(name);
    } catch (e) {
        showToast(e.message, 'error');
    }
}
