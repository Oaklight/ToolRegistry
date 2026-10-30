// ============== Logs ==============
async function refreshLogs() {
    try {
        const warningsOnly = document.getElementById('log-warnings-filter').checked;
        const params = {
            limit: document.getElementById('log-limit').value,
            tool_name: document.getElementById('log-tool-filter').value || undefined,
            status: document.getElementById('log-status-filter').value || undefined,
            has_warnings: warningsOnly ? 'true' : undefined
        };
        const data = await api.getLogs(params);
        renderLogs(data.entries || []);
    } catch (e) {
        document.getElementById('logs-body').innerHTML =
            `<tr><td colspan="5" class="empty-state"><div class="text-error">${e.message}</div></td></tr>`;
    }
}

async function refreshLogStats() {
    try {
        const data = await api.getLogStats();
        document.getElementById('log-stats-grid').innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${data.total_entries || 0}</div>
                <div class="stat-label">${t('stat.totalEntries')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value text-success">${data.by_status?.success || 0}</div>
                <div class="stat-label">${t('stat.successful')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value text-error">${data.by_status?.error || 0}</div>
                <div class="stat-label">${t('stat.errors')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: var(--text-secondary);">${data.by_status?.disabled || 0}</div>
                <div class="stat-label">${t('stat.rejected')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: var(--warning);">${data.by_status?.timeout || 0}</div>
                <div class="stat-label">${t('stat.timeouts')}</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${(data.avg_duration_ms || 0).toFixed(2)}ms</div>
                <div class="stat-label">${t('stat.avgDuration')}</div>
            </div>
        `;
    } catch (e) {
        document.getElementById('log-stats-grid').innerHTML =
            `<div class="stat-card"><div class="stat-label text-muted">${t('stat.loggingNotEnabled')}</div></div>`;
    }
}

function renderLogs(entries) {
    const tbody = document.getElementById('logs-body');

    if (entries.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="5" class="empty-state">
                <div class="empty-state-icon">${t('empty.logs')}</div>
                <div class="empty-state-text">${t('empty.logsHint')}</div>
            </td></tr>`;
        return;
    }

    tbody.innerHTML = entries.map((entry, idx) => {
        const statusClass = entry.status === 'success' ? 'badge-success' :
                           entry.status === 'error' ? 'badge-error' : 'badge-warning';
        const statusLabel = entry.status === 'disabled' ? t('log.rejected') :
                            entry.status === 'timeout' ? t('log.timeout') :
                            entry.status;
        const timestamp = new Date(entry.timestamp).toLocaleString();
        const duration = entry.duration_ms ? entry.duration_ms.toFixed(2) + 'ms' : '-';

        const warningCount = (entry.warnings || []).length;
        const warningBadge = warningCount > 0
            ? `<span class="badge badge-warn" title="${warningCount} warning${warningCount > 1 ? 's' : ''}">⚠ ${warningCount}</span>`
            : '';

        return `
            <tr class="log-row" onclick="toggleLogDetails(${idx})">
                <td><span class="expand-icon">${SVG_CHEVRON}</span></td>
                <td class="text-sm">${timestamp}</td>
                <td><span class="ident" style="font-weight: 500;">${escapeHtml(entry.tool_name)}</span></td>
                <td><span class="badge ${statusClass}">${statusLabel}</span>${warningBadge}</td>
                <td class="text-muted">${duration}</td>
            </tr>
            <tr>
                <td colspan="5" style="padding: 0;">
                    <div class="log-details" id="log-details-${idx}">
                        <div class="mb-2"><strong>${t('log.arguments')}</strong></div>
                        <pre>${escapeHtml(JSON.stringify(entry.arguments ?? {}, null, 2))}</pre>
                        ${entry.status === 'success' ? `
                            <div class="mb-2 mt-4"><strong>${t('log.result')}</strong></div>
                            <pre>${escapeHtml(JSON.stringify(entry.result, null, 2))}</pre>
                        ` : ''}
                        ${warningCount > 0 ? `
                            <div class="mb-2 mt-4"><strong>⚠ ${t('log.warnings')} (${warningCount})</strong></div>
                            <pre class="text-warning">${escapeHtml(entry.warnings.join('\n'))}</pre>
                        ` : ''}
                        ${entry.error ? `
                            <div class="mb-2 mt-4"><strong>${t('log.errorLabel')}</strong></div>
                            <pre class="text-error">${escapeHtml(entry.error)}</pre>
                        ` : ''}
                        ${entry.exception_type ? `
                            <div class="mb-2 mt-4"><strong>${t('log.exceptionType')}</strong></div>
                            <pre class="text-error">${escapeHtml(entry.exception_type)}</pre>
                        ` : ''}
                        ${entry.traceback ? `
                            <details class="mt-4">
                                <summary style="cursor:pointer;"><strong>${t('log.traceback')}</strong></summary>
                                <pre class="text-error" style="white-space:pre-wrap;">${escapeHtml(entry.traceback)}</pre>
                            </details>
                        ` : ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function toggleLogDetails(idx) {
    const details = document.getElementById('log-details-' + idx);
    const row = details.closest('tr').previousElementSibling;

    details.classList.toggle('active');
    row.classList.toggle('expanded');
}

function confirmClearLogs() {
    showModal(t('modal.clearLogs'), `
        <p>${t('confirm.clearLogs')}</p>
        <p class="text-muted text-sm mt-2">${t('confirm.clearLogsWarn')}</p>
    `, async () => {
        try {
            await api.clearLogs();
            showToast(t('toast.logsCleared'), 'success');
            refreshLogs();
            refreshLogStats();
        } catch (e) {
            showToast(e.message, 'error');
        }
    });
}
