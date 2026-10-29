"""Behavioural tests for the admin panel's JavaScript auth client.

The panel keeps its JavaScript inline in ``admin.html``.  These tests extract
the API client and run it under Node with stubbed ``fetch``, ``prompt`` and
``localStorage`` so the auth retry can be exercised without a browser.  They
skip when Node is unavailable; GitHub-hosted runners ship it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from toolregistry.admin.static import ADMIN_HTML

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
    """Extract ``promptForAdminToken`` and ``AdminAPI`` from the admin UI."""
    start = ADMIN_HTML.index(_START)
    class_open = ADMIN_HTML.index("class AdminAPI {", start)
    brace = ADMIN_HTML.index("{", class_open)
    end = _find_matching_brace(ADMIN_HTML, brace)
    return ADMIN_HTML[start : end + 1] + "\nglobalThis.__AdminAPI = AdminAPI;\n"


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        (
            "none",
            {
                "calls": [None, "Bearer good"],
                "prompts": 1,
                "stored": "good",
                "threw": None,
            },
        ),
        (
            "stale",
            {
                "calls": ["Bearer stale", "Bearer good"],
                "prompts": 1,
                "stored": "good",
                "threw": None,
            },
        ),
        (
            "wrong",
            {
                "calls": ["Bearer stale", "Bearer wrong"],
                "prompts": 1,
                "stored": "wrong",
                "threw": "Unauthorized",
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
