"""Builds unmanaged solution packages holding one "child sync" cloud flow for the
"AlSanidi | Marketing" solution.

A child sync flow runs when a parent row (e.g. Snap Campaign) is added or modified,
lists the parent's children from the Snap connector (e.g. its ad squads), maps choice
labels to option values, and uses List rows on the child's Snap ID to update the
existing row or add a new one, linked to the parent. Children that no longer come back
from Snap are left in place.

Expression helpers follow the conventions shared by the Snap flows:
  choice      -> option value looked up by Snap label in the Choice_maps compose
  multichoice -> Select + Query (drop unknown labels) joined as "1,3,..."
  money/decimal -> Snap micro value / 1,000,000
  multiline   -> JSON text of the value
"""
import json
import re
import uuid
import zipfile
from dataclasses import dataclass, field

from table_builder import solution_xml

SNAP_API = "shared_sanidi-5fsnap-5f43b530b23a0dc933"
SNAP_CONNREF = "sanidi_snapconnection"
DATAVERSE_API = "shared_commondataserviceforapps"
DATAVERSE_CONNREF = "sanidi_sharedcommondataserviceforapps_79822"

CONTENT_TYPES = ('<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/'
                 '2006/content-types"><Default Extension="xml" ContentType="application/octet-stream" />'
                 '<Default Extension="json" ContentType="application/octet-stream" /></Types>')


@dataclass
class ChildSyncFlow:
    name: str                   # flow display name, e.g. "Get Snap Ad Squads"
    key: str                    # stable ID seed, e.g. "get-snap-ad-squads"
    fields: list                # child table FIELDS (see table_builder.py)
    source: dict                # child column -> path in the Snap object
    noun: str                   # action name stem, e.g. "ad_squad"
    nouns: str                  # e.g. "ad_squads"
    child_set: str              # e.g. "sanidi_snapadsquads"
    child_key: str              # e.g. "sanidi_adsquadid"
    child_pk: str               # e.g. "sanidi_snapadsquadid"
    lookup: str                 # child lookup column to the parent, e.g. "sanidi_snapcampaign"
    parent_entity: str          # e.g. "sanidi_snapcampaign"
    parent_label: str           # trigger name stem, e.g. "Snap_Campaign"
    parent_set: str             # e.g. "sanidi_snapcampaigns"
    parent_pk: str              # e.g. "sanidi_snapcampaignid"
    parent_snap_id: str         # parent column holding the Snap ID, e.g. "sanidi_campaignid"
    list_operation: str         # Snap connector operation, e.g. "ListAdSquadsByCampaign"
    list_parameter: str         # e.g. "campaign_id"
    list_key: str               # response array, e.g. "adsquads"
    item_key: str               # object inside each array item, e.g. "adsquad"
    extra_labels: dict = field(default_factory=dict)   # column -> {alternative Snap label: option value}
    overrides: dict = field(default_factory=dict)      # column -> f(snap_expr) returning a flow expression

    @property
    def flow_id(self):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"alsanidi/flows/{self.key}"))

    @property
    def item(self):
        return self.noun[0].upper() + self.noun[1:]

    def src(self, path):
        return f"outputs('{self.item}')" + "".join(f"?['{p}']" for p in path)

    def choice_maps(self):
        maps = {}
        for name, _, kind, extra, _ in self.fields:
            if kind in ("choice", "multichoice"):
                labels = extra[1] if kind == "multichoice" else extra
                maps[name] = {label: i for i, label in enumerate(labels, start=1)}
                maps[name].update(self.extra_labels.get(name, {}))
        return maps

    @staticmethod
    def known(name):
        return f"Known_{name.replace('sanidi_', '')}"

    def value_expr(self, f):
        name, _, kind, _, _ = f
        s = self.src(self.source[name])
        if name in self.overrides:
            return self.overrides[name](s)
        if kind == "choice":
            return f"@outputs('Choice_maps')?['{name}']?[string({s})]"
        if kind == "multichoice":
            k = self.known(name)
            return f"@if(empty(body('{k}')), null, join(body('{k}'), ','))"
        if kind in ("money", "decimal"):
            return f"@if(equals({s}, null), null, div(float({s}), 1000000))"
        if kind == "multiline":
            return f"@if(equals({s}, null), null, string({s}))"
        return f"@{s}"

    def definition(self):
        assert set(self.source) | {self.lookup} == {f[0] for f in self.fields}, "every column needs a source"
        loop = f"For_each_{self.noun}"
        find, cond = f"Find_existing_{self.noun}", f"If_{self.noun}_exists"
        columns = {f"item/{f[0]}": self.value_expr(f) for f in self.fields if f[0] != self.lookup}
        columns[f"item/{self.lookup}@odata.bind"] = \
            f"/{self.parent_set}(@{{triggerOutputs()?['body/{self.parent_pk}']}})"

        actions = {self.item: {"type": "Compose", "inputs": f"@items('{loop}')?['{self.item_key}']", "runAfter": {}}}
        previous = self.item
        for name, _, kind, _, _ in self.fields:
            if kind != "multichoice":
                continue
            values = f"{self.known(name)}_values"
            actions[values] = {"type": "Select", "runAfter": {previous: ["Succeeded"]},
                               "inputs": {"from": f"@coalesce({self.src(self.source[name])}, json('[]'))",
                                          "select": f"@outputs('Choice_maps')?['{name}']?[item()]"}}
            actions[self.known(name)] = {"type": "Query", "runAfter": {values: ["Succeeded"]},
                                         "inputs": {"from": f"@body('{values}')",
                                                    "where": "@not(equals(item(), null))"}}
            previous = self.known(name)
        actions[find] = {**dataverse("ListRecords", {
            "entityName": self.child_set, "$select": self.child_pk,
            "$filter": f"{self.child_key} eq '@{{{self.src(['id'])}}}'", "$top": 1}),
            "runAfter": {previous: ["Succeeded"]}}
        actions[cond] = {
            "type": "If", "runAfter": {find: ["Succeeded"]},
            "expression": {"and": [{"greater": [f"@length(outputs('{find}')?['body/value'])", 0]}]},
            "actions": {f"Update_{self.noun}": {**dataverse("UpdateOnlyRecord", {
                "entityName": self.child_set,
                "recordId": f"@first(outputs('{find}')?['body/value'])?['{self.child_pk}']",
                **columns}), "runAfter": {}}},
            "else": {"actions": {f"Add_{self.noun}": {**dataverse("CreateRecord", {
                "entityName": self.child_set, **columns}), "runAfter": {}}}}}

        return {
            "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/"
                       "workflowdefinition.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                           "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
            "triggers": {f"When_a_{self.parent_label}_is_added_or_modified": {
                "type": "OpenApiConnectionWebhook",
                "inputs": {
                    "parameters": {"subscriptionRequest/message": 4,
                                   "subscriptionRequest/entityname": self.parent_entity,
                                   "subscriptionRequest/scope": 4},
                    "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE_API}",
                             "connectionName": DATAVERSE_API, "operationId": "SubscribeWebhookTrigger"},
                    "authentication": "@parameters('$authentication')"}}},
            "actions": {
                "Choice_maps": {"type": "Compose", "inputs": self.choice_maps(), "runAfter": {},
                                "description": "Snap value -> Dataverse option value for every choice column"},
                f"List_{self.nouns}": {
                    "type": "OpenApiConnection", "runAfter": {"Choice_maps": ["Succeeded"]},
                    "inputs": {"parameters": {self.list_parameter: f"@triggerOutputs()?['body/{self.parent_snap_id}']"},
                               "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{SNAP_API}",
                                        "operationId": self.list_operation, "connectionName": SNAP_API}}},
                loop: {
                    "type": "Foreach",
                    "foreach": f"@coalesce(outputs('List_{self.nouns}')?['body/{self.list_key}'], json('[]'))",
                    "runAfter": {f"List_{self.nouns}": ["Succeeded"]}, "actions": actions},
            },
        }

    def flow_json(self):
        return {"properties": {
            "connectionReferences": {
                SNAP_API: {"runtimeSource": "embedded", "connection": {"connectionReferenceLogicalName": SNAP_CONNREF},
                           "api": {"name": SNAP_API, "logicalName": "sanidi_snap"}},
                DATAVERSE_API: {"runtimeSource": "embedded",
                                "connection": {"connectionReferenceLogicalName": DATAVERSE_CONNREF},
                                "api": {"name": DATAVERSE_API}}},
            "definition": self.definition(),
            "templateName": ""},
            "schemaVersion": "1.0.0.0"}

    def build(self, template_zip, out):
        src_zip = zipfile.ZipFile(template_zip)
        c = src_zip.read("customizations.xml").decode("utf-8-sig")
        root_open = re.match(r".*?<ImportExportXml[^>]*>", c, re.S).group(0)
        json_file = f"/Workflows/{re.sub(r'[^A-Za-z0-9]', '', self.name)}-{self.flow_id.upper()}.json"
        customizations = f"""{root_open}
  <Entities />
  <Roles />
  <Workflows>
    <Workflow WorkflowId="{{{self.flow_id}}}" Name="{self.name}">
      <JsonFileName>{json_file}</JsonFileName>
      <Type>1</Type>
      <Subprocess>0</Subprocess>
      <Category>5</Category>
      <Mode>0</Mode>
      <Scope>4</Scope>
      <OnDemand>0</OnDemand>
      <TriggerOnCreate>0</TriggerOnCreate>
      <TriggerOnDelete>0</TriggerOnDelete>
      <AsyncAutodelete>0</AsyncAutodelete>
      <SyncWorkflowLogOnFailure>0</SyncWorkflowLogOnFailure>
      <StateCode>1</StateCode>
      <StatusCode>2</StatusCode>
      <RunAs>1</RunAs>
      <IsTransacted>1</IsTransacted>
      <IntroducedVersion>1.0.0</IntroducedVersion>
      <IsCustomizable>1</IsCustomizable>
      <BusinessProcessType>0</BusinessProcessType>
      <IsCustomProcessingStepAllowedForOtherPublishers>1</IsCustomProcessingStepAllowedForOtherPublishers>
      <ModernFlowType>0</ModernFlowType>
      <PrimaryEntity>none</PrimaryEntity>
      <LocalizedNames>
        <LocalizedName languagecode="1033" description="{self.name}" />
      </LocalizedNames>
    </Workflow>
  </Workflows>
  <FieldSecurityProfiles />
  <Templates />
  <EntityMaps />
  <EntityRelationships />
  <OrganizationSettings />
  <optionsets />
  <CustomControls />
  <EntityDataProviders />
  <Languages>
    <Language>1033</Language>
  </Languages>
</ImportExportXml>
"""
        solution = solution_xml(src_zip.read("solution.xml").decode("utf-8-sig"),
                                [f'<RootComponent type="29" id="{{{self.flow_id}}}" behavior="0" />'])
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", CONTENT_TYPES)
            z.writestr("solution.xml", solution)
            z.writestr("customizations.xml", customizations)
            z.writestr(json_file.lstrip("/"), json.dumps(self.flow_json(), indent=2))
        print(f"Wrote {out}: flow {self.name} {self.flow_id}, {len(self.fields)} mapped columns")


def dataverse(operation, params):
    return {"type": "OpenApiConnection", "inputs": {
        "parameters": params,
        "host": {"apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE_API}",
                 "operationId": operation, "connectionName": DATAVERSE_API}}}
