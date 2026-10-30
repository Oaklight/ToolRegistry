// ============== Sources ==============
// The panel can be opened focused on one source type, which is how the Tools
// and Namespaces panels link here; the filter is cleared from the banner.
let _sourceFocus = null;

function focusSources(type) {
    _sourceFocus = type || null;
    switchTab('sources');
    refreshSources();
}

function showToolsFromSourceButton(button) {
    const namespace = button.dataset.namespace || '';
    gotoTools({
        source: button.dataset.source || '',
        namespace: namespace === 'default' ? '' : namespace,
    });
}

function clearSourceFocus() {
    _sourceFocus = null;
    refreshSources();
}

async function refreshSources() {
    try {
        const data = await api.getSources();
        renderSources(data.sources || []);
    } catch (e) {
        document.getElementById('sources-body').innerHTML =
            `<div class="empty-state"><div class="text-error">${e.message}</div></div>`;
    }
}

function renderSources(sources) {
    const body = document.getElementById('sources-body');

    if (sources.length === 0) {
        body.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">${t('empty.sources')}</div>
                <div class="empty-state-text">${t('empty.sourcesHint')}</div>
            </div>`;
        return;
    }

    const visible = _sourceFocus ? sources.filter(src => src.type === _sourceFocus) : sources;
    const banner = _sourceFocus
        ? `<div class="source-focus">
               <span>${t('source.focused', { type: _sourceFocus })}</span>
               <button class="btn btn-secondary btn-sm" onclick="clearSourceFocus()">${t('source.clearFocus')}</button>
           </div>`
        : '';

    body.innerHTML = banner + (visible.length === 0
        ? `<div class="empty-state"><div class="empty-state-text">${t('source.noneFocused')}</div></div>`
        : visible.map(src => {
        const toolChips = src.tools.map(tn => {
            // Match the Tools tab: short names inside a namespace,
            // full name in the tooltip.
            let short = tn;
            if (src.namespace && src.namespace !== 'default') {
                for (const sep of ['-', '.']) {
                    const prefix = src.namespace + sep;
                    if (tn.startsWith(prefix)) {
                        short = tn.slice(prefix.length);
                        break;
                    }
                }
            }
            return `<button type="button" class="source-tool-chip" title="${escapeHtml(tn)}" onclick="showToolDetailModal('${escapeJs(tn)}')">${escapeHtml(short)}</button>`;
        }).join('');
        return `
        <div class="source-card">
            <div class="source-card-header">
                ${renderSourceBadge(src.type)}
                <button type="button" class="ns-link" onclick="gotoTools({ namespace: '${escapeJs(src.namespace)}' })" title="${t('ns.showTools')}">${escapeHtml(src.namespace)}</button>
                <span class="text-muted" style="font-size: var(--text-small); margin-left: auto;">${src.enabled_count}/${src.tool_count} ${t('stat.enabled').toLowerCase()}</span>
            </div>
            ${src.detail ? `<div class="source-detail">${escapeHtml(src.detail)}</div>` : ''}
            <div class="source-tools-list">${toolChips}</div>
            <div class="source-card-actions">
                <button class="btn btn-secondary btn-sm"
                        data-source="${escapeHtml(src.type)}"
                        data-namespace="${escapeHtml(src.namespace)}"
                        onclick="showToolsFromSourceButton(this)">${t('source.showTools', { count: src.tool_count })}</button>
                <button class="btn btn-secondary btn-sm"
                        data-kind="${escapeHtml(src.type)}"
                        data-detail="${escapeHtml(src.detail || '')}"
                        data-namespace="${escapeHtml(src.namespace)}"
                        onclick="openRegisterFromSource(this)">${t('source.registerMore')}</button>
            </div>
        </div>`;
    }).join(''));
}
