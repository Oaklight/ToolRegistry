// ============== Permissions ==============
async function refreshPermissions() {
    try {
        const data = await api.getPermissions();
        renderPermissions(data);
    } catch (e) {
        document.getElementById('permissions-body').innerHTML =
            `<div class="empty-state"><div class="text-error">${e.message}</div></div>`;
    }
}

function renderPermissions(data) {
    const body = document.getElementById('permissions-body');

    if (!data.has_policy) {
        body.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">${t('empty.permPolicy')}</div>
                <div class="empty-state-text">${t('empty.permPolicyHint')}</div>
            </div>`;
        return;
    }

    let html = '';

    // Status indicators
    html += `<div class="perm-status-card">
        <div class="perm-status-item">
            <span class="perm-dot perm-dot-active"></span>
            <span>${t('perm.policyActive')}</span>
        </div>
        <div class="perm-status-item">
            <span class="perm-dot ${data.has_handler ? 'perm-dot-active' : 'perm-dot-inactive'}"></span>
            <span>${data.has_handler ? t('perm.handlerRegistered') : t('perm.handlerNotSet')}</span>
        </div>
        <div class="perm-status-item">
            <span>${t('perm.fallback')}</span>
            <span class="badge badge-${data.fallback}">${data.fallback}</span>
        </div>
    </div>`;

    // Rules table
    if (data.rules.length > 0) {
        html += `<div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>${t('col.ruleName')}</th>
                        <th>${t('col.result')}</th>
                        <th>${t('col.reason')}</th>
                    </tr>
                </thead>
                <tbody>`;

        data.rules.forEach(rule => {
            html += `<tr>
                <td><span style="font-weight: 500;">${escapeHtml(rule.name)}</span></td>
                <td><span class="badge badge-${rule.result}">${rule.result}</span></td>
                <td class="text-muted" style="font-size: var(--text-body);">${escapeHtml(rule.reason || '—')}</td>
            </tr>`;
        });

        html += `</tbody></table></div>`;
    } else {
        html += `<p class="text-muted" style="font-size: var(--text-body);">${t('perm.noRules')}</p>`;
    }

    body.innerHTML = html;
}
