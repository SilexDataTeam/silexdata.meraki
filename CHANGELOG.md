# Silexdata Meraki Release Notes

**Topics**

- <a href="#v1-3-0">v1\.3\.0</a>
    - <a href="#minor-changes">Minor Changes</a>
    - <a href="#bugfixes">Bugfixes</a>
- <a href="#v1-2-0">v1\.2\.0</a>
    - <a href="#minor-changes-1">Minor Changes</a>

<a id="v1-3-0"></a>
## v1\.3\.0

<a id="minor-changes"></a>
### Minor Changes

* cisco\_meraki \- the inventory plugin is now licensed GPL\-3\.0\-or\-later\, as Ansible requires of plugins that run in the controller\. The rest of the collection stays Apache\-2\.0\.

<a id="bugfixes"></a>
### Bugfixes

* cisco\_meraki \- authenticate with the <code>meraki\_api\_key</code> set in the inventory source\. Only the <code>MERAKI\_DASHBOARD\_API\_KEY</code> environment variable was used before\.
* cisco\_meraki \- honor <code>strict</code> for <code>compose</code>\. An expression using an undefined variable failed the inventory even with <code>strict</code> set to false\.
* cisco\_meraki \- include every organization and network\. Only the first page the Dashboard API returned was used before\, which is at most 1000 networks per organization\.
* cisco\_meraki \- name the Dashboard API URL in the error when the API cannot be read\.
* cisco\_meraki \- query the <code>meraki\_base\_url</code> set in the inventory source\. The default Dashboard API URL was always used before\.
* cisco\_meraki \- report that the <code>meraki</code> Python library is required when it is not installed\, instead of failing to load the plugin\.
* cisco\_meraki \- use the inventory cache when <code>cache</code> is enabled\. It was never read or written before\.

<a id="v1-2-0"></a>
## v1\.2\.0

<a id="minor-changes-1"></a>
### Minor Changes

* cisco\_meraki \- include the status of isBoundToConfigTemplate in host variables
