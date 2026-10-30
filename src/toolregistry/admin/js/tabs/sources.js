// ============== Sources ==============
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

    body.innerHTML = sources.map(src => {
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
            return `<span class="source-tool-chip" title="${escapeHtml(tn)}">${escapeHtml(short)}</span>`;
        }).join('');
        return `
        <div class="source-card">
            <div class="source-card-header">
                ${renderSourceBadge(src.type)}
                <span style="font-weight: 500;">${escapeHtml(src.namespace)}</span>
                <span class="text-muted" style="font-size: 0.75rem; margin-left: auto;">${src.enabled_count}/${src.tool_count} ${t('stat.enabled').toLowerCase()}</span>
            </div>
            ${src.detail ? `<div class="source-detail">${escapeHtml(src.detail)}</div>` : ''}
            <div class="source-tools-list">${toolChips}</div>
        </div>`;
    }).join('');
}
