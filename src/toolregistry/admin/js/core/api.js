// ============== API Client ==============
// Concurrent 401s share a single prompt so the browser does not stack
// dialogs; a rejected token gets exactly one retry (see request()).
let _authPromptPromise = null;
function promptForAdminToken() {
    if (!_authPromptPromise) {
        _authPromptPromise = Promise.resolve(prompt(t('misc.enterToken')))
            .then((value) => (value || '').trim())
            .finally(() => { _authPromptPromise = null; });
    }
    return _authPromptPromise;
}

class AdminAPI {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.token = token;
    }

    getHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        if (this.token) {
            headers['Authorization'] = 'Bearer ' + this.token;
        }
        return headers;
    }

    async request(path, options = {}, authRetried = false) {
        const requestToken = this.token;
        // Build headers per attempt and let the current token win:
        // spreading the caller's headers last would re-send the token
        // the server just rejected.  The caller's options are not
        // mutated, so the retry below starts from the same shape.
        const requestOptions = {
            ...options,
            headers: { ...options.headers, ...this.getHeaders() },
        };
        try {
            const response = await fetch(this.baseUrl + path, requestOptions);
            if (response.status === 401) {
                // A stored or freshly entered token that still gets 401
                // is final: never loop the prompt forever on a typo.
                if (authRetried) throw new Error('Unauthorized');
                // Another request may have obtained a token while this
                // one was in flight; reuse it instead of prompting.
                let token = this.token;
                if (!token || token === requestToken) {
                    token = await promptForAdminToken();
                    if (!token) throw new Error('Unauthorized');
                    localStorage.setItem('admin_token', token);
                    this.token = token;
                    AUTH_TOKEN = token;
                }
                return this.request(path, options, true);
            }
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || 'Request failed');
            }
            return data;
        } catch (error) {
            if (error.name === 'TypeError') {
                updateConnectionStatus(false);
                throw new Error('Connection failed');
            }
            throw error;
        }
    }

    async getTools() {
        return this.request('/api/tools');
    }

    async getTool(name) {
        return this.request('/api/tools/' + encodeURIComponent(name));
    }

    async enableTool(name) {
        return this.request('/api/tools/' + encodeURIComponent(name) + '/enable', { method: 'POST' });
    }

    async disableTool(name, reason = '') {
        return this.request('/api/tools/' + encodeURIComponent(name) + '/disable', {
            method: 'POST',
            body: JSON.stringify({ reason })
        });
    }

    async getNamespaces() {
        return this.request('/api/namespaces');
    }

    async enableNamespace(ns) {
        return this.request('/api/namespaces/' + encodeURIComponent(ns) + '/enable', { method: 'POST' });
    }

    async disableNamespace(ns, reason = '') {
        return this.request('/api/namespaces/' + encodeURIComponent(ns) + '/disable', {
            method: 'POST',
            body: JSON.stringify({ reason })
        });
    }

    async updateToolMetadata(name, metadata) {
        return this.request('/api/tools/' + encodeURIComponent(name) + '/metadata', {
            method: 'PATCH',
            body: JSON.stringify(metadata)
        });
    }

    async updateNamespaceMetadata(ns, metadata) {
        return this.request('/api/namespaces/' + encodeURIComponent(ns) + '/metadata', {
            method: 'PATCH',
            body: JSON.stringify(metadata)
        });
    }

    async getLogs(params = {}) {
        const query = new URLSearchParams();
        if (params.limit) query.set('limit', params.limit);
        if (params.tool_name) query.set('tool_name', params.tool_name);
        if (params.status) query.set('status', params.status);
        const queryStr = query.toString();
        return this.request('/api/logs' + (queryStr ? '?' + queryStr : ''));
    }

    async getLogStats() {
        return this.request('/api/logs/stats');
    }

    async clearLogs() {
        return this.request('/api/logs', { method: 'DELETE' });
    }

    async exportState() {
        return this.request('/api/state');
    }

    async importState(state) {
        return this.request('/api/state', {
            method: 'POST',
            body: JSON.stringify(state)
        });
    }

    async getPermissions() {
        return this.request('/api/permissions');
    }

    async getSources() {
        return this.request('/api/sources');
    }

    async previewSource(payload) {
        return this.request('/api/sources/preview', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    }

    async registerSource(payload) {
        return this.request('/api/sources/register', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    }

    async getDiscovery() {
        return this.request('/api/discovery');
    }

    async enableDiscovery() {
        return this.request('/api/discovery/enable', { method: 'POST' });
    }

    async disableDiscovery() {
        return this.request('/api/discovery/disable', { method: 'POST' });
    }

    async listOverrides() {
        return this.request('/api/overrides');
    }

    async overrideTool(name, changes) {
        return this.request('/api/tools/' + encodeURIComponent(name) + '/override', {
            method: 'POST',
            body: JSON.stringify(changes),
        });
    }

    async restoreOverride(name) {
        return this.request('/api/tools/' + encodeURIComponent(name) + '/override', {
            method: 'DELETE',
        });
    }

    async getConfig() {
        return this.request('/api/config');
    }

    async updateConfig(data) {
        return this.request('/api/config', {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async getInfo() {
        return this.request('/api/info');
    }

    async getSchema(format = 'openai-chat') {
        return this.request('/api/schema?format=' + encodeURIComponent(format));
    }
}

const api = new AdminAPI(API_BASE, AUTH_TOKEN);
