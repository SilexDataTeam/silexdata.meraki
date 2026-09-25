# SPDX-FileCopyrightText: Silex Data Solutions
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the silexdata.meraki.cisco_meraki inventory plugin.

The plugin is driven only through parse(), the way ansible-inventory drives it,
and the expectations come from its DOCUMENTATION and changelog rather than from
its implementation. The Meraki SDK is replaced by a fake that keeps the real
SDK's documented contract - the key falls back to MERAKI_DASHBOARD_API_KEY, the
base URL defaults to https://api.meraki.com/api/v1, and paginated calls return
one page unless asked for more - so a failure here is the plugin's, not the
fake's.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os

import meraki
import pytest
from ansible.errors import AnsibleError
from ansible.inventory.data import InventoryData
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import inventory_loader
from meraki.exceptions import APIKeyError

PLUGIN = "silexdata.meraki.cisco_meraki"
DEFAULT_BASE_URL = "https://api.meraki.com/api/v1"
API_KEY_ENV = "MERAKI_DASHBOARD_API_KEY"
# The Dashboard API's default page size for GET /organizations/{id}/networks.
NETWORKS_PER_PAGE = 1000
# ... and for GET /organizations.
ORGANIZATIONS_PER_PAGE = 9000


def network(org_id, index, **overrides):
    """A network as GET /organizations/{id}/networks returns it."""
    data = {
        "id": f"N_{org_id}_{index}",
        "organizationId": org_id,
        "name": f"{org_id.lower()}-net-{index}",
        "productTypes": ["appliance", "switch"],
        "timeZone": "America/New_York",
        "tags": ["branch"],
        "enrollmentString": None,
        "url": f"https://n1.meraki.com/net-{index}/manage/usage/list",
        "notes": "",
        "isBoundToConfigTemplate": False,
    }
    data.update(overrides)
    return data


class FakeDashboard:
    """What the fake Dashboard API serves, and every call made to it."""

    def __init__(self):
        self.organizations = [{"id": "O1", "name": "Acme Corp"}]
        self.networks = {"O1": [network("O1", 1), network("O1", 2, isBoundToConfigTemplate=True)]}
        self.devices = {}
        self.clients = []
        self.calls = []


class FakeDashboardAPI:
    """Stands in for meraki.DashboardAPI, keeping its documented contract."""

    dashboard = None

    def __init__(self, api_key=None, base_url=DEFAULT_BASE_URL, **kwargs):
        # The real SDK falls back to the environment, and refuses to start
        # without a key at all.
        self.api_key = api_key or os.environ.get(API_KEY_ENV)
        if not self.api_key:
            raise APIKeyError()
        self.base_url = base_url
        self.kwargs = kwargs
        dashboard = self.dashboard
        dashboard.clients.append(self)
        self.organizations = _Organizations(dashboard)
        self.networks = _Networks(dashboard)


class _Organizations:
    def __init__(self, dashboard):
        self._dashboard = dashboard

    def getOrganizations(self, total_pages=1, direction="next", **kwargs):
        # Like getOrganizationNetworks, one page unless asked for more.
        self._dashboard.calls.append(("getOrganizations",))
        organizations = self._dashboard.organizations
        if total_pages in (-1, "all"):
            return list(organizations)
        return list(organizations[: int(total_pages) * int(kwargs.get("perPage", ORGANIZATIONS_PER_PAGE))])

    def getOrganizationNetworks(self, organizationId, total_pages=1, direction="next", **kwargs):
        # The SDK's default is total_pages=1: one page of perPage networks
        # unless the caller asks for more ("all" or -1 for every page).
        self._dashboard.calls.append(("getOrganizationNetworks", organizationId))
        networks = self._dashboard.networks.get(organizationId, [])
        if total_pages in (-1, "all"):
            return list(networks)
        return list(networks[: int(total_pages) * int(kwargs.get("perPage", NETWORKS_PER_PAGE))])


class _Networks:
    def __init__(self, dashboard):
        self._dashboard = dashboard

    def getNetworkDevices(self, networkId):
        self._dashboard.calls.append(("getNetworkDevices", networkId))
        return list(self._dashboard.devices.get(networkId, []))


@pytest.fixture
def dashboard(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    fake = FakeDashboard()
    monkeypatch.setattr(FakeDashboardAPI, "dashboard", fake)
    monkeypatch.setattr(meraki, "DashboardAPI", FakeDashboardAPI)
    return fake


@pytest.fixture
def load(tmp_path):
    """Parse an inventory source written from `lines`; return the inventory."""

    def _load(lines, name="inventory.meraki.yml", cache=False):
        source = tmp_path / name
        source.write_text(f"---\nplugin: {PLUGIN}\n" + "".join(line + "\n" for line in lines))
        inventory = InventoryData()
        plugin = inventory_loader.get(PLUGIN)
        plugin.parse(inventory, DataLoader(), str(source), cache=cache)
        # What InventoryManager does after every parse(): persist the cache,
        # tolerating a plugin that has no cache loaded.
        try:
            plugin.update_cache_if_changed()
        except AttributeError:
            pass
        return inventory

    return _load


def hosts_of(inventory, group):
    return sorted(host.name for host in inventory.groups[group].get_hosts())


def hostvars(inventory, host):
    return inventory.get_host(host).get_vars()


# verify_file ----------------------------------------------------------------


@pytest.mark.parametrize("name", ["inventory.meraki.yml", "inventory.meraki.yaml", "meraki.yml"])
def test_a_meraki_source_is_accepted(tmp_path, name):
    source = tmp_path / name
    source.write_text(f"---\nplugin: {PLUGIN}\n")
    assert inventory_loader.get(PLUGIN).verify_file(str(source))


@pytest.mark.parametrize("name", ["inventory.yml", "meraki.json", "hosts"])
def test_other_sources_are_left_to_other_plugins(tmp_path, name):
    source = tmp_path / name
    source.write_text(f"---\nplugin: {PLUGIN}\n")
    assert not inventory_loader.get(PLUGIN).verify_file(str(source))


# meraki_api_key / meraki_base_url -------------------------------------------


def test_the_api_key_in_the_source_authenticates(dashboard, load):
    load(["meraki_api_key: key-from-the-source"])
    assert [c.api_key for c in dashboard.clients] == ["key-from-the-source"]


def test_the_api_key_in_the_environment_authenticates(dashboard, load, monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "key-from-the-environment")
    load([])
    assert [c.api_key for c in dashboard.clients] == ["key-from-the-environment"]


def test_a_source_without_an_api_key_is_refused(dashboard, load):
    with pytest.raises(Exception) as caught:
        load([])
    assert "meraki_api_key" in str(caught.value)
    assert not dashboard.calls


def test_the_base_url_in_the_source_is_queried(dashboard, load, monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "key")
    load(["meraki_base_url: https://api.meraki.ca/api/v1"])
    assert [c.base_url for c in dashboard.clients] == ["https://api.meraki.ca/api/v1"]


def test_the_default_base_url_is_the_global_dashboard(dashboard, load, monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "key")
    load([])
    assert [c.base_url for c in dashboard.clients] == [DEFAULT_BASE_URL]


# Networks, organizations and groups ------------------------------------------


@pytest.fixture
def keyed(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "key")


def test_every_network_becomes_a_host_in_its_organization_group(dashboard, load, keyed):
    dashboard.organizations.append({"id": "O2", "name": "Beta Labs"})
    dashboard.networks["O2"] = [network("O2", 1)]
    inventory = load([])
    assert hosts_of(inventory, "net_meraki_organization_acmecorp") == ["o1-net-1", "o1-net-2"]
    assert hosts_of(inventory, "net_meraki_organization_betalabs") == ["o2-net-1"]


def test_host_vars_describe_the_network_and_its_organization(dashboard, load, keyed):
    inventory = load([])
    bound = hostvars(inventory, "o1-net-2")
    assert bound["id"] == "N_O1_2"
    assert bound["org_id"] == "O1"
    assert bound["org_name"] == "Acme Corp"
    assert bound["tags"] == ["branch"]
    # 1.2.0: "include the status of isBoundToConfigTemplate in host variables".
    assert bound["is_bound_to_config_template"] is True
    assert hostvars(inventory, "o1-net-1")["is_bound_to_config_template"] is False


def test_every_network_of_a_large_organization_is_included(dashboard, load, keyed):
    # One more network than a single page of the Dashboard API holds.
    dashboard.networks["O1"] = [network("O1", i) for i in range(NETWORKS_PER_PAGE + 1)]
    inventory = load([])
    assert len(hosts_of(inventory, "net_meraki_organization_acmecorp")) == NETWORKS_PER_PAGE + 1


def test_want_organization_false_adds_no_organization_groups(dashboard, load, keyed):
    inventory = load(["want_organization: false"])
    assert "net_meraki_organization_acmecorp" not in inventory.groups
    assert sorted(inventory.hosts) == ["o1-net-1", "o1-net-2"]


def test_group_prefix_names_the_organization_groups(dashboard, load, keyed):
    inventory = load(["group_prefix: site_"])
    assert hosts_of(inventory, "site_organization_acmecorp") == ["o1-net-1", "o1-net-2"]
    assert "net_meraki_organization_acmecorp" not in inventory.groups


def test_group_parent_holds_the_organization_groups(dashboard, load, keyed):
    inventory = load(["group_parent: meraki"])
    children = [g.name for g in inventory.groups["meraki"].child_groups]
    assert children == ["net_meraki_organization_acmecorp"]


def test_devices_are_not_fetched_by_default(dashboard, load, keyed):
    inventory = load([])
    assert not [c for c in dashboard.calls if c[0] == "getNetworkDevices"]
    assert "devices" not in hostvars(inventory, "o1-net-1")


def test_want_devices_adds_each_networks_devices(dashboard, load, keyed):
    dashboard.devices["N_O1_1"] = [{"serial": "Q2XX-XXXX-XXXX", "model": "MX68"}]
    inventory = load(["want_devices: true"])
    assert hostvars(inventory, "o1-net-1")["devices"] == [{"serial": "Q2XX-XXXX-XXXX", "model": "MX68"}]
    assert hostvars(inventory, "o1-net-2")["devices"] == []


# constructed ------------------------------------------------------------------


def test_keyed_groups_group_hosts_by_their_variables(dashboard, load, keyed):
    inventory = load(["keyed_groups:", "  - key: tags", "    prefix: tag"])
    assert hosts_of(inventory, "tag_branch") == ["o1-net-1", "o1-net-2"]


def test_compose_sets_variables_from_expressions(dashboard, load, keyed):
    inventory = load(["compose:", "  site_timezone: time_zone"])
    assert hostvars(inventory, "o1-net-1")["site_timezone"] == "America/New_York"


def test_compose_tolerates_an_undefined_variable_unless_strict(dashboard, load, keyed):
    # constructed: strict defaults to false, which skips an expression that
    # cannot be evaluated instead of failing the whole inventory.
    inventory = load(["compose:", "  site_owner: owner.name"])
    assert "site_owner" not in hostvars(inventory, "o1-net-1")


def test_compose_fails_on_an_undefined_variable_when_strict(dashboard, load, keyed):
    with pytest.raises(AnsibleError):
        load(["strict: true", "compose:", "  site_owner: owner.name"])


# inventory_cache --------------------------------------------------------------


def test_a_cached_inventory_is_served_without_calling_the_api(dashboard, load, keyed, tmp_path):
    cache = [
        "cache: true",
        "cache_plugin: ansible.builtin.jsonfile",
        f"cache_connection: {tmp_path / 'cache'}",
    ]
    first = load(cache, cache=True)
    calls = len(dashboard.calls)
    second = load(cache, cache=True)
    assert len(dashboard.calls) == calls, "the second parse queried the API instead of the cache"
    assert sorted(second.hosts) == sorted(first.hosts)
