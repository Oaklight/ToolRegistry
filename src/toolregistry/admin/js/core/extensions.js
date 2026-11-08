// ============== Extension Loader ==============
// The server mounts an extension's routes and validates its manifest before
// it starts.  This loader owns the browser half: fetch the manifest, add a
// navigation item and a panel, import the entry module, and call its
// register({container, api, i18n}) export.
//
// The contract version is checked here as well as on the server, so a shell
// cached from an older release refuses a manifest it cannot drive instead of
// mounting a module whose assumptions no longer hold.
const ADMIN_EXTENSION_API = 1;

const AdminExtensions = (() => {
    // name -> {manifest, unmount}
    const mounted = new Map();

    function assetUrl(path) {
        return new URL(path, document.baseURI).href;
    }

    function titleFor(manifest) {
        const titles = manifest.title || {};
        const values = Object.values(titles);
        return titles[currentLang] || titles.en || values[0] || manifest.name;
    }

    function navOrder(manifest) {
        const order = manifest.nav && manifest.nav.order;
        return Number.isFinite(order) ? order : 100;
    }

    function navGroup(manifest) {
        return (manifest.nav && manifest.nav.group) || '';
    }

    // A path in the manifest is relative to the panel API prefix; accept both
    // "/things" and "things" so an extension does not depend on one spelling.
    function normalizeSubpath(path) {
        if (!path || path === '/') return '';
        return path.charAt(0) === '/' ? path : '/' + path;
    }

    function makeApi(manifest) {
        const prefix = manifest.api_prefix;
        const call = (path, options) => api.request(prefix + normalizeSubpath(path), options);
        const write = (method, path, body) => call(path, {
            method,
            body: JSON.stringify(body || {}),
        });
        return {
            prefix,
            url: (path = '') => prefix + normalizeSubpath(path),
            request: call,
            get: (path) => call(path),
            post: (path, body) => write('POST', path, body),
            put: (path, body) => write('PUT', path, body),
            patch: (path, body) => write('PATCH', path, body),
            delete: (path) => call(path, { method: 'DELETE' }),
        };
    }

    function injectStyles(manifest) {
        (manifest.styles || []).forEach((path) => {
            const href = assetUrl(path);
            const present = Array.from(document.querySelectorAll('link[data-ext-name]'))
                .some((link) => link.dataset.extName === manifest.name
                    && link.getAttribute('href') === href);
            if (present) return;
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;
            link.dataset.extName = manifest.name;
            document.head.appendChild(link);
        });
    }

    function iconMarkup(manifest) {
        if (manifest.icon) return manifest.icon;
        return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            + 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            + '<rect x="3" y="3" width="7" height="7" rx="1"></rect>'
            + '<rect x="14" y="3" width="7" height="7" rx="1"></rect>'
            + '<rect x="3" y="14" width="7" height="7" rx="1"></rect>'
            + '<rect x="14" y="14" width="7" height="7" rx="1"></rect></svg>';
    }

    function navButton(manifest) {
        const label = titleFor(manifest);
        const button = document.createElement('button');
        button.className = 'console-item';
        button.dataset.tab = 'ext-' + manifest.name;
        button.dataset.extName = manifest.name;
        button.dataset.extOrder = String(navOrder(manifest));
        button.title = label;
        // The title is inserted as text.  The icon is SVG markup from the
        // same trusted package as the module, so it is the one part rendered
        // as HTML; the manifest validation keeps both fields well-formed.
        button.innerHTML = iconMarkup(manifest)
            + '<span class="console-item-label"></span>';
        button.querySelector('.console-item-label').textContent = label;
        button.addEventListener('click', () => switchTab('ext-' + manifest.name));
        return button;
    }

    function insertNav(manifest) {
        const nav = document.getElementById('console');
        if (!nav) return;
        const groupName = navGroup(manifest);
        let section = Array.from(nav.querySelectorAll('.console-ext'))
            .find((node) => node.dataset.extGroup === groupName);
        if (!section) {
            section = document.createElement('div');
            section.className = 'console-ext';
            section.dataset.extGroup = groupName;
            section.innerHTML = '<hr class="console-sep">'
                + '<div class="console-label"></div><div class="console-group"></div>';
            section.querySelector('.console-label').textContent =
                groupName || t('nav.extensions');
            const spacer = nav.querySelector('.console-spacer');
            if (spacer) nav.insertBefore(section, spacer);
            else nav.appendChild(section);
        }
        const group = section.querySelector('.console-group');
        group.appendChild(navButton(manifest));

        // Sort by nav.order, then name, so declaration order does not decide
        // where an extension lands in the console.
        const buttons = Array.from(group.querySelectorAll('.console-item'));
        buttons.sort((left, right) => (Number(left.dataset.extOrder)
            - Number(right.dataset.extOrder))
            || left.dataset.extName.localeCompare(right.dataset.extName));
        buttons.forEach((button) => group.appendChild(button));
    }

    function insertPanel(manifest) {
        const existing = document.getElementById('tab-ext-' + manifest.name);
        if (existing) return existing.querySelector('.ext-container');
        const panel = document.createElement('div');
        panel.id = 'tab-ext-' + manifest.name;
        panel.className = 'tab-content';
        panel.style.display = 'none';
        const container = document.createElement('div');
        container.className = 'ext-container';
        container.dataset.extName = manifest.name;
        panel.appendChild(container);
        const main = document.querySelector('main.main');
        if (main) main.appendChild(panel);
        return container;
    }

    function removeDom(name) {
        Array.from(document.querySelectorAll('[data-ext-name]')).forEach((element) => {
            if (element.dataset.extName === name) element.remove();
        });
        // Drop a group section whose last item is gone.
        Array.from(document.querySelectorAll('.console-ext')).forEach((section) => {
            if (!section.querySelector('.console-item')) section.remove();
        });
        const panel = document.getElementById('tab-ext-' + name);
        if (panel) panel.remove();
    }

    async function mount(manifest) {
        if (mounted.has(manifest.name)) return;
        if (manifest.requires_api !== ADMIN_EXTENSION_API) {
            throw new Error('extension "' + manifest.name + '" requires API '
                + manifest.requires_api + ', this panel provides ' + ADMIN_EXTENSION_API);
        }

        injectStyles(manifest);
        insertNav(manifest);
        const container = insertPanel(manifest);

        const module = await import(assetUrl(manifest.entry));
        if (typeof module.register !== 'function') {
            throw new Error('extension "' + manifest.name + '" has no register() export');
        }
        const extensionApi = makeApi(manifest);
        const i18n = {
            lang: currentLang,
            t: (key, params) => t(key, params),
        };
        await module.register({ container, api: extensionApi, i18n, manifest });
        mounted.set(manifest.name, {
            manifest,
            unmount: typeof module.unmount === 'function' ? module.unmount : null,
        });
    }

    async function unmount(name) {
        const entry = mounted.get(name);
        if (!entry) return;
        mounted.delete(name);
        try {
            if (entry.unmount) await entry.unmount();
        } catch (error) {
            console.warn('Admin extension unmount failed:', name, error);
        }
        removeDom(name);
    }

    async function load() {
        let data;
        try {
            data = await api.request('/api/extensions');
        } catch (error) {
            // The panel works without extensions; a failed manifest must not
            // take the rest of the UI down with it.
            console.warn('Admin extensions unavailable:', error);
            return;
        }
        if (!data || data.api_version !== ADMIN_EXTENSION_API) {
            console.warn('Admin extension manifest version mismatch:',
                data && data.api_version);
            return;
        }
        for (const manifest of data.extensions || []) {
            try {
                await mount(manifest);
            } catch (error) {
                console.error('Admin extension failed to load:',
                    manifest && manifest.name, error);
                if (manifest && manifest.name) removeDom(manifest.name);
            }
        }
        applyLanguage();
    }

    // A language switch rewrites the console labels; extension titles are not
    // in the shared I18N map, so they are relabelled here from the manifest.
    function applyLanguage() {
        Array.from(document.querySelectorAll('.console-item[data-ext-name]'))
            .forEach((button) => {
                const entry = mounted.get(button.dataset.extName);
                if (!entry) return;
                const label = titleFor(entry.manifest);
                button.title = label;
                const node = button.querySelector('.console-item-label');
                if (node) node.textContent = label;
            });
        Array.from(document.querySelectorAll('.console-ext')).forEach((section) => {
            const label = section.querySelector('.console-label');
            if (label) label.textContent = section.dataset.extGroup || t('nav.extensions');
        });
    }

    return { apiVersion: ADMIN_EXTENSION_API, load, unmount, applyLanguage };
})();

window.AdminExtensions = AdminExtensions;
