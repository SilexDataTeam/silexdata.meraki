<!--
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0
-->

# Sanity test ignore files

`ansible-test sanity` runs a fixed battery of checks (import checks, validate-modules,
pep8, license headers, etc.) per supported `ansible-core` version. When a check flags
something that is a deliberate, known-acceptable deviation for this collection (rather
than a bug to fix), the fix is a per-version ignore file:

```text
tests/sanity/ignore-<ansible-core-version>.txt
```

Each line has the form `<path> <rule>`, for example:

```text
plugins/modules/your_module.py validate-modules:missing-gplv3-license
```

Modules and other plugins are GPL-3.0-or-later here, so `validate-modules`'s
`missing-gplv3-license` check passes without an ignore entry. The exception is a
plugin derived from upstream code that keeps its upstream license (see
`.claude/rules/licensing.md`): that one needs an ignore line per supported
`ansible-core` version, annotated with the reason.

The ignore files themselves cannot carry a license header - `ansible-test`
rejects comment-only lines - so each `ignore-*.txt` needs a `.license` sidecar
next to it.

## Do not pre-create empty ignore files

Do **not** add `tests/sanity/ignore-*.txt` files to a new collection speculatively. Add
one only once you have actually run `ansible-test sanity` (e.g. via
`nox -e ansible_test_sanity` or `ansible-test sanity --docker -v`) against a given
`ansible-core` version and it reports a specific violation. Copy the exact `<path>
<rule>` line(s) it prints, for that specific `ansible-core` version's ignore file. An
empty or speculative ignore file just hides future real regressions.
