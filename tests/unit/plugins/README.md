<!--
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0
-->

# Unit tests

Unit tests mirror the layout of `plugins/`: a plugin at
`plugins/<plugin_type>/<name>.py` gets a unit test at
`tests/unit/plugins/<plugin_type>/test_<name>.py`. For example:

```text
plugins/modules/your_module.py  ->  tests/unit/plugins/modules/test_your_module.py
plugins/lookup/your_lookup.py   ->  tests/unit/plugins/lookup/test_your_lookup.py
```

## House style: `AnsibleExitJson` / `AnsibleFailJson` / `set_module_args`

For module unit tests, follow the pattern used across Silex Data collections
(see `silexdata.akamai`'s `tests/unit/plugins/modules/test_manage_akamai.py` for
a full worked example): patch `AnsibleModule.exit_json`/`fail_json` to instead
raise marker exceptions, inject module args via a `set_module_args()` helper
that writes to `basic._ANSIBLE_ARGS` (and sets `basic._ANSIBLE_PROFILE =
"legacy"` for ansible-core 2.19+ compatibility), then call the module's
`main()` and assert on the raised exception's payload.

Skeleton of the pattern:

```python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

from unittest.mock import MagicMock, patch

import pytest
from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes
from ansible_collections.<namespace>.<collection_name>.plugins.modules import your_module


class AnsibleExitJson(Exception):
    """Raised by the patched exit_json to halt module execution in tests."""


class AnsibleFailJson(Exception):
    """Raised by the patched fail_json to halt module execution in tests."""


def exit_json(*args, **kwargs):
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


def set_module_args(args):
    """Prepare module arguments the way Ansible would pass them on stdin."""
    serialized = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(serialized)
    basic._ANSIBLE_PROFILE = "legacy"


@pytest.fixture(autouse=True)
def patch_ansible_module(monkeypatch):
    monkeypatch.setattr(basic.AnsibleModule, "exit_json", exit_json)
    monkeypatch.setattr(basic.AnsibleModule, "fail_json", fail_json)


def test_main_fails_without_required_params():
    set_module_args({})
    with pytest.raises(AnsibleFailJson):
        your_module.main()
```

Mock any network/SDK calls with `unittest.mock.patch`/`MagicMock` rather than
making real requests; that is what the `expected-return-values.yml` live
integration test (gated on service availability) is for.
