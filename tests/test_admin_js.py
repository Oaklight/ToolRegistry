"""Behavioural tests for the admin panel's JavaScript auth client.

The API client lives in ``js/core/api.js`` and is loaded as a plain script.
These tests run it under Node with stubbed ``fetch``, ``prompt`` and
``localStorage`` so the auth retry can be exercised without a browser.  They
skip when Node is unavailable; GitHub-hosted runners ship it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from importlib.resources import files

ADMIN_API_JS = (
    files("toolregistry.admin").joinpath("js/core/api.js").read_text(encoding="utf-8")
)

ADMIN_UI_JS = (
    files("toolregistry.admin").joinpath("js/core/ui.js").read_text(encoding="utf-8")
)

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is required")

_START = "let _authPromptPromise = null;"

_HARNESS = """
const vm = require('vm');
const fs = require('fs');

const code = fs.readFileSync(process.argv[2], 'utf8');
const scenario = process.argv[3];

const stored = {};
const calls = [];
let promptCount = 0;

globalThis.localStorage = {
  getItem: (k) => (Object.prototype.hasOwnProperty.call(stored, k) ? stored[k] : null),
  setItem: (k, v) => { stored[k] = String(v); },
  removeItem: (k) => { delete stored[k]; },
};
globalThis.prompt = () => {
  promptCount += 1;
  return scenario === 'wrong' ? 'wrong' : 'good';
};
globalThis.fetch = async (url, options = {}) => {
  const auth = (options.headers && options.headers.Authorization) || null;
  calls.push(auth);
  const ok = auth === 'Bearer good';
  return {
    status: ok ? 200 : 401,
    ok,
    async json() { return ok ? { ok: true } : { message: 'Unauthorized' }; },
  };
};
globalThis.updateConnectionStatus = () => {};
globalThis.t = (key) => key;
globalThis.AUTH_TOKEN = '';

if (scenario === 'stale' || scenario === 'wrong') {
  // A previous page may have left a token behind; the client must not read
  // storage for it.  The initial token is passed explicitly below.
  stored.admin_token = 'stale';
}

vm.runInContext(code, vm.createContext(globalThis));

const initialToken = (scenario === 'stale' || scenario === 'wrong') ? 'stale' : '';
const api = new globalThis.__AdminAPI('http://example', initialToken);

(async () => {
  let threw = null;
  try {
    await api.request('/probe');
  } catch (e) {
    threw = e.message;
  }
  console.log(JSON.stringify({
    calls,
    prompts: promptCount,
    stored: Object.prototype.hasOwnProperty.call(stored, 'admin_token')
      ? stored.admin_token
      : null,
    threw,
  }));
})();
"""


def _find_matching_brace(source: str, open_index: int) -> int:
    """Return the index of the brace closing the one at *open_index*.

    Skips braces inside strings, template literals and comments.
    """
    depth = 0
    state: str | None = None
    i = open_index
    while i < len(source):
        ch = source[i]
        if state is None:
            if ch in "\"'`":
                state = ch
            elif ch == "/" and source[i + 1 : i + 2] == "/":
                state = "//"
            elif ch == "/" and source[i + 1 : i + 2] == "*":
                state = "/*"
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        elif state in "\"'`":
            if ch == "\\":
                i += 1
            elif ch == state:
                state = None
        elif state == "//":
            if ch == "\n":
                state = None
        elif state == "/*":
            if ch == "*" and source[i + 1 : i + 2] == "/":
                state = None
                i += 1
        i += 1
    raise AssertionError("Unbalanced braces in the extracted admin API client")


def _auth_client_source() -> str:
    """Return the auth client module with ``AdminAPI`` exported for the harness."""
    start = ADMIN_API_JS.index(_START)
    class_open = ADMIN_API_JS.index("class AdminAPI {", start)
    brace = ADMIN_API_JS.index("{", class_open)
    end = _find_matching_brace(ADMIN_API_JS, brace)
    return ADMIN_API_JS[start : end + 1] + "\nglobalThis.__AdminAPI = AdminAPI;\n"


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        (
            "none",
            {
                "calls": [None, "Bearer good"],
                "prompts": 1,
                "stored": None,
                "threw": None,
            },
        ),
        (
            "stale",
            {
                "calls": ["Bearer stale", "Bearer good"],
                "prompts": 1,
                # The client must not replace the stale value; the prompt
                # result lives in memory and the server's HttpOnly cookie
                # carries it across reloads.
                "stored": "stale",
                "threw": None,
            },
        ),
        (
            "wrong",
            {
                "calls": ["Bearer stale", "Bearer wrong"],
                "prompts": 1,
                "stored": "stale",
                # The harness stubs t() as the identity, so the message is
                # the i18n key the client throws.
                "threw": "error.unauthorized",
            },
        ),
    ],
)
def test_auth_retry_carries_the_current_token(
    tmp_path: Path, scenario: str, expected: dict
) -> None:
    """A retry must send the token obtained by the prompt, not the rejected one."""
    code_path = tmp_path / "admin_api.js"
    code_path.write_text(_auth_client_source(), encoding="utf-8")
    harness = tmp_path / "harness.js"
    harness.write_text(_HARNESS, encoding="utf-8")

    result = subprocess.run(
        [NODE, str(harness), str(code_path), scenario],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


_HARNESS_RESPONSE_STATE = """
const vm = require('vm');
const fs = require('fs');

const code = fs.readFileSync(process.argv[2], 'utf8');
const scenario = process.argv[3];

const calls = [];
globalThis.localStorage = { getItem: () => null, setItem: () => {} };
globalThis.prompt = () => 'good';
globalThis.updateConnectionStatus = () => {};
globalThis.t = (key) => key;
globalThis.AUTH_TOKEN = '';

function reply(status, statusText, body) {
    return {
        status,
        ok: status >= 200 && status < 300,
        statusText,
        async json() {
            if (body instanceof Error) throw body;
            return body;
        },
    };
}

globalThis.fetch = async (url, options = {}) => {
    const auth = (options.headers && options.headers.Authorization) || null;
    calls.push(auth);
    if (scenario === 'forbidden') {
        return reply(403, 'Forbidden',
            { error: 'Forbidden', message: 'Cross-origin request rejected' });
    }
    if (scenario === 'unsupported') {
        return reply(415, 'Unsupported Media Type',
            { error: 'Unsupported Media Type',
              message: 'State-changing requests must use Content-Type: application/json' });
    }
    if (scenario === 'html_error') {
        // A proxy may answer with a non-JSON body; the status line is all
        // the client can report.
        return reply(415, 'Unsupported Media Type', new Error('not json'));
    }
    if (scenario === 'no_auth') {
        return reply(200, 'OK', { ok: true });
    }
    return reply(401, 'Unauthorized', { message: 'Unauthorized' });
};

vm.runInContext(code, vm.createContext(globalThis));

const api = new globalThis.__AdminAPI('http://example', '');

(async () => {
    let threw = null;
    try {
        await api.request('/probe');
    } catch (e) {
        threw = e.message;
    }
    console.log(JSON.stringify({ authRequired: api.authRequired, threw, calls }));
})();
"""


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        (
            "no_auth",
            {"authRequired": False, "threw": None, "calls": [None]},
        ),
        (
            "protected",
            {
                "authRequired": True,
                "threw": "error.unauthorized",
                "calls": [None, "Bearer good"],
            },
        ),
        (
            "forbidden",
            {
                "authRequired": None,
                "threw": "Cross-origin request rejected",
                "calls": [None],
            },
        ),
        (
            "unsupported",
            {
                "authRequired": None,
                "threw": (
                    "State-changing requests must use Content-Type: application/json"
                ),
                "calls": [None],
            },
        ),
        (
            "html_error",
            {
                "authRequired": None,
                "threw": "415 Unsupported Media Type",
                "calls": [None],
            },
        ),
    ],
)
def test_response_state_and_error_messages(
    tmp_path: Path, scenario: str, expected: dict
) -> None:
    """403/415 messages reach the caller, and auth state is learned from a response."""
    code_path = tmp_path / "admin_api.js"
    code_path.write_text(_auth_client_source(), encoding="utf-8")
    harness = tmp_path / "harness_state.js"
    harness.write_text(_HARNESS_RESPONSE_STATE, encoding="utf-8")

    result = subprocess.run(
        [NODE, str(harness), str(code_path), scenario],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


def test_register_ui_copy_is_translated_and_wired() -> None:
    """The new Sources hints exist in both dictionaries and are used by the UI."""
    i18n = (
        files("toolregistry.admin")
        .joinpath("js/core/i18n.js")
        .read_text(encoding="utf-8")
    )
    for key in (
        "register.overridesKept",
        "register.stdioNeedsAuth",
        "register.privateHostsRefused",
    ):
        assert i18n.count(f"'{key}':") == 2, key

    register_js = (
        files("toolregistry.admin")
        .joinpath("js/tabs/register.js")
        .read_text(encoding="utf-8")
    )
    assert "preserved_overrides" in register_js
    assert "register.overridesKept" in register_js
    assert "register.stdioNeedsAuth" in register_js
    assert "updateStdioHint" in register_js
    assert "register.privateHostsRefused" in register_js
    assert "updatePrivateHostsHint" in register_js
    assert "register-private-hint" in register_js


_ESCAPE_HARNESS = """
const vm = require('vm');
const fs = require('fs');
const code = fs.readFileSync(process.argv[2], 'utf8');
const payloads = JSON.parse(process.argv[3]);
vm.runInContext(code, vm.createContext(globalThis));

const entities = { amp: '&', lt: '<', gt: '>', quot: '"', '#39': "'" };
const results = payloads.map((payload) => {
  const attr = escapeJsAttr(payload);
  // The HTML parser decodes entity references once before the handler is
  // compiled; this is the value the JS parser receives.
  const decoded = attr.replace(/&(amp|lt|gt|quot|#39);/g, (_, key) => entities[key]);
  globalThis.PWNED = 0;
  try {
    new Function(
      'showToolDetailModal',
      "showToolDetailModal('" + decoded + "')"
    )(() => {});
  } catch (error) {
    // A syntax error also proves the payload did not execute.
  }
  return { payload, attr, decoded, pwned: globalThis.PWNED };
});

const html = escapeHtml(
  ['&', '<', '>', String.fromCharCode(34), String.fromCharCode(39)].join('')
);
console.log(JSON.stringify({ results, html }));
"""


def _escape_helpers_source() -> str:
    """Return the escape helpers from ``ui.js`` for the Node harness."""
    start = ADMIN_UI_JS.index("// ============== Utilities ==============")
    end = ADMIN_UI_JS.index("// Prose that names a tool", start)
    return ADMIN_UI_JS[start:end]


@pytest.mark.parametrize(
    "payload",
    [
        "x&#39;);globalThis.PWNED=1;//",
        "x&quot;);globalThis.PWNED=1;//",
        "</script><img src=x onerror=globalThis.PWNED=1>",
        "x');globalThis.PWNED=1;//",
    ],
)
def test_inline_handler_escaping_survives_entity_decoding(
    tmp_path: Path, payload: str
) -> None:
    """A handler argument is parsed as HTML and then as JS; both layers escape.

    ``escapeJs`` alone leaves ``&#39;`` untouched, and the HTML parser turns it
    into a quote before the handler compiles. ``escapeJsAttr`` encodes the
    entity as well.
    """
    code_path = tmp_path / "ui_helpers.js"
    code_path.write_text(_escape_helpers_source(), encoding="utf-8")
    harness = tmp_path / "escape_harness.js"
    harness.write_text(_ESCAPE_HARNESS, encoding="utf-8")

    result = subprocess.run(
        [NODE, str(harness), str(code_path), json.dumps([payload])],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    entry = data["results"][0]
    assert entry["pwned"] == 0, entry
    assert "'" not in entry["attr"], entry
    assert '"' not in entry["attr"], entry
    assert data["html"] == "&amp;&lt;&gt;&quot;&#39;"
