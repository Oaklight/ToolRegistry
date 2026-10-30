// ============== Namespaces ==============
async function refreshNamespaces() {
    try {
        const data = await api.getNamespaces();
        renderNamespaces(data.namespaces || []);
    } catch (e) {
        document.getElementById('namespaces-body').innerHTML =
            `<tr><td colspan="5" class="empty-state"><div class="text-error">${e.message}</div></td></tr>`;
    }
}

function renderNamespaces(namespaces) {
    const tbody = document.getElementById('namespaces-body');

    if (namespaces.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="7" class="empty-state">
                <div class="empty-state-icon">${t('empty.ns')}</div>
                <div class="empty-state-text">${t('empty.nsHint')}</div>
            </td></tr>`;
        return;
    }

    // Determine source type per namespace from tools data
    const nsSourceMap = {};
    allTools.forEach(tool => {
        const ns = tool.namespace || 'default';
        if (!nsSourceMap[ns]) nsSourceMap[ns] = new Set();
        nsSourceMap[ns].add(tool.source || 'native');
    });

    tbody.innerHTML = namespaces.map(ns => {
        const sources = nsSourceMap[ns.name] || new Set();
        const sourceBadges = [...sources].map(s => renderSourceBadge(s)).join(' ');
        return `
        <tr>
            <td><span style="font-weight: 500;">${escapeHtml(ns.name)}</span></td>
            <td>${sourceBadges || '<span class="text-muted" style="font-size: 0.75rem;">&mdash;</span>'}</td>
            <td>${ns.tool_count}</td>
            <td><span class="text-success">${ns.enabled_count}</span></td>
            <td><span class="text-error">${ns.disabled_count}</span></td>
            <td>${(ns.tags || []).length > 0 ? renderTagBadges(ns.tags) : '<span class="text-muted" style="font-size: 0.75rem;">&mdash;</span>'}</td>
            <td>
                ${ns.name === 'default' ? '<span class="text-muted" style="font-size: 0.75rem;">&mdash;</span>' : `<div style="display: flex; gap: 6px; flex-wrap: wrap;">
                    <button class="btn btn-success btn-sm" style="min-width: 90px; text-align: center;" onclick="enableNamespace('${escapeHtml(ns.name)}')">${t('btn.enableAll')}</button>
                    <button class="btn btn-danger btn-sm" style="min-width: 90px; text-align: center;" onclick="showDisableNamespaceModal('${escapeHtml(ns.name)}')">${t('btn.disableAll')}</button>
                </div>`}
            </td>
        </tr>`;
    }).join('');
}

function showDisableNamespaceModal(name) {
    showModal(t('modal.disableNs'), `
        <div class="form-group">
            <label class="form-label">${t('modal.nsLabel')}<strong>${escapeHtml(name)}</strong></label>
            <p class="text-muted text-sm mt-2">${t('modal.disableNsHint')}</p>
        </div>
        <div class="form-group">
            <label class="form-label">${t('label.reasonOptional')}</label>
            <input type="text" class="input" id="disable-ns-reason" placeholder="${t('label.enterReason')}">
        </div>
    `, async () => {
        const reason = document.getElementById('disable-ns-reason').value;
        await disableNamespace(name, reason);
    }, () => {
        refreshTools();
    });
}

async function enableNamespace(name) {
    try {
        await api.enableNamespace(name);
        showToast(t('toast.nsEnabled', {name}), 'success');
        refreshNamespaces();
        refreshTools();
        refreshStats();
    } catch (e) {
        showToast(e.message, 'error');
        refreshNamespaces();
        refreshTools();
    }
}

async function disableNamespace(name, reason) {
    try {
        await api.disableNamespace(name, reason);
        showToast(t('toast.nsDisabled', {name}), 'success');
        refreshNamespaces();
        refreshTools();
        refreshStats();
    } catch (e) {
        showToast(e.message, 'error');
    }
}
