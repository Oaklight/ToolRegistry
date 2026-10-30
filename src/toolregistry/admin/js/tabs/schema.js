// ============== Schema Tab ==============
let _schemaLoaded = false;
let _activeSchemaSubTab = 'global';

function switchSchemaSubTab(subtab) {
    _activeSchemaSubTab = subtab;
    document.querySelectorAll('.schema-subtab').forEach(b => {
        b.classList.toggle('active', b.dataset.subtab === subtab);
    });
    document.querySelectorAll('.schema-subcontent').forEach(d => {
        d.style.display = 'none';
    });
    const subEl = document.getElementById('schema-sub-' + subtab);
    if (subEl) subEl.style.display = '';
    if (subtab === 'discover') {
        loadDiscover();
    } else {
        loadSchema(document.getElementById('schema-format-select').value);
    }
}

async function loadSchema(format) {
    const pre = document.getElementById('schema-content');
    const meta = document.getElementById('schema-meta');
    pre.textContent = t('misc.loading');
    meta.textContent = '';
    try {
        const data = await api.getSchema(format);
        pre.textContent = JSON.stringify(data.schema, null, 2);
        meta.textContent = t('schema.stats', {
            visible: data.count,
            deferred: data.deferred_count ?? 0,
            disabled: data.disabled_count ?? 0,
        }) + ' · ' + data.format;
        _schemaLoaded = true;
    } catch (e) {
        pre.textContent = e.message;
    }
}

async function loadDiscover() {
    const pre = document.getElementById('discover-content');
    const meta = document.getElementById('discover-meta');
    const warnDiv = document.getElementById('discover-warnings');
    pre.textContent = t('misc.loading');
    meta.textContent = '';
    warnDiv.innerHTML = '';
    try {
        const data = await api.getSchema('discover');
        pre.textContent = data.text || '(discover_tools not enabled)';
        meta.textContent = t('schema.discoverStats', {
            deferred: data.deferred_count ?? 0,
            disabled: data.disabled_count ?? 0,
        });
        // Warning banner for long-description tools without search_hint
        const warnings = (data.tools || []).filter(w => w.long && !w.has_search_hint);
        if (warnings.length > 0) {
            const items = warnings.map(w => {
                const safeId = 'sh-' + w.name.replace(/[^a-zA-Z0-9]/g, '_');
                return `<div style="display:flex;align-items:center;gap:6px;margin:4px 0;flex-wrap:wrap;">
                    <span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escapeHtml(w.description)}">
                        <strong>${escapeHtml(w.name)}</strong> <span style="opacity:0.7;">(${w.description.length} chars)</span>
                    </span>
                    <input type="text" id="${safeId}" placeholder="${t('schema.hintPlaceholder')}"
                        style="flex:1;min-width:160px;padding:2px 6px;font-size:0.8rem;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg-secondary);color:var(--text-primary);"
                        onkeydown="if(event.key==='Enter')saveSearchHint('${escapeHtml(w.name)}',document.getElementById('${safeId}'),true)">
                    <button class="btn btn-secondary btn-sm" onclick="saveSearchHint('${escapeHtml(w.name)}',document.getElementById('${safeId}'),true)">${t('btn.apply')}</button>
                </div>`;
            }).join('');
            warnDiv.innerHTML = `<div style="background:var(--bg-secondary);border:1px solid #f59e0b;border-radius:var(--radius-sm);padding:10px 14px;font-size:0.83rem;margin-bottom:10px;">
                <span style="color:#d97706;">&#9888;</span> ${t('schema.warnLong', {count: warnings.length})}
                <div style="margin-top:6px;">${items}</div>
            </div>`;
        }
    } catch (e) {
        pre.textContent = e.message;
    }
}

async function saveSearchHint(name, inputEl, reloadDiscover) {
    const value = inputEl.value.trim();
    try {
        const result = await api.updateToolMetadata(name, { search_hint: value });
        const saved = result && result.saved;
        showToast(saved ? t('schema.hintSaved', {name}) : t('schema.hintUpdated', {name}), 'success');
        if (reloadDiscover) loadDiscover();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function copySchemaContent(elementId) {
    const pre = document.getElementById(elementId);
    try {
        await navigator.clipboard.writeText(pre.textContent);
        showToast(t('toast.copied'), 'success');
    } catch (e) {
        showToast(t('toast.copyFailed'), 'error');
    }
}
