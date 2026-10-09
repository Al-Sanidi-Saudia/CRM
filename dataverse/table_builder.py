"""Builds unmanaged solution packages that create or update a Dataverse table in the
"AlSanidi | Marketing" solution: columns, choices, lookups and their relationships,
an alternate key, the main form and the views.

The Dataverse XML format comes from the Meta tables in a solution export (the
"template"), so new tables match their conventions. The template needs:
  - sanidi_MetaCampaign: system columns, column formats, main form, views
  - sanidi_MetaAdSet:    a custom lookup and its relationship
  - sanidi_Meta_Ad:      a multiline text column
Each table spec lives next to its flow (e.g. snap-campaign/table_spec.py).

Field tuples: (logical name, display name, kind, extra, description)
  kind        extra
  text        max length
  multiline   -                     (stores JSON / long text)
  choice      [labels]              (local choice, values 1..n)
  multichoice (optionset name, [labels])  (shared global choice, values 1..n)
  bool, datetime, money, int, decimal -
  lookup      target table schema name (e.g. sanidi_SnapCampaign)
"""
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

CLASSIDS = {
    "text": "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}", "choice": "{3EF39988-22BB-4F0B-BBBE-64B5A3748AEE}",
    "multichoice": "{4AA28AB7-9C13-4F57-A73D-AD894D048B5F}", "bool": "{67FAC785-CD58-4F9F-ABB3-4B7DDC6ED5ED}",
    "datetime": "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}", "money": "{533B9E00-756B-4312-95A0-DC888637AC78}",
    "int": "{C6D124CA-7EDA-4a60-AEA9-7FB8D318B68F}", "decimal": "{C3EFE0C3-0EC6-42be-8349-CBD9079DFD8E}",
    "multiline": "{E0DECE4B-6FC8-4a8f-A065-082708572369}", "owner": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}",
    "lookup": "{270BD3DB-D9AF-4782-9025-509E298DEC0A}", "subgrid": "{E7A81278-8635-4d9e-8D4D-59480B391C5B}",
}

TEMPLATE_SCHEMA = "sanidi_MetaCampaign"
TEMPLATE_LOGICAL = TEMPLATE_SCHEMA.lower()

# Multi-select columns point at a global choice; the template solution has none, so the
# format (as exported by Dataverse) is kept here.
MULTISELECT_TEMPLATE = """<attribute PhysicalName="NAME">
              <Type>multiselectpicklist</Type>
              <Name>NAME</Name>
              <LogicalName>NAME</LogicalName>
              <RequiredLevel>none</RequiredLevel>
              <DisplayMask>ValidForAdvancedFind|ValidForForm|ValidForGrid</DisplayMask>
              <ImeMode>auto</ImeMode>
              <ValidForUpdateApi>1</ValidForUpdateApi>
              <ValidForReadApi>1</ValidForReadApi>
              <ValidForCreateApi>1</ValidForCreateApi>
              <IsCustomField>1</IsCustomField>
              <IsAuditEnabled>1</IsAuditEnabled>
              <IsSecured>0</IsSecured>
              <IntroducedVersion>1.0.0</IntroducedVersion>
              <IsCustomizable>1</IsCustomizable>
              <IsRenameable>1</IsRenameable>
              <CanModifySearchSettings>1</CanModifySearchSettings>
              <CanModifyRequirementLevelSettings>1</CanModifyRequirementLevelSettings>
              <CanModifyAdditionalSettings>1</CanModifyAdditionalSettings>
              <SourceType>0</SourceType>
              <IsGlobalFilterEnabled>0</IsGlobalFilterEnabled>
              <IsSortableEnabled>0</IsSortableEnabled>
              <CanModifyGlobalFilterSettings>1</CanModifyGlobalFilterSettings>
              <CanModifyIsSortableSettings>1</CanModifyIsSortableSettings>
              <IsDataSourceSecret>0</IsDataSourceSecret>
              <AutoNumberFormat></AutoNumberFormat>
              <IsSearchable>0</IsSearchable>
              <IsFilterable>0</IsFilterable>
              <IsRetrievable>0</IsRetrievable>
              <IsLocalizable>0</IsLocalizable>
              <OptionSetName>OPTIONSET</OptionSetName>
              <displaynames>
                <displayname description="" languagecode="1033" />
              </displaynames>
            </attribute>"""


@dataclass
class RelatedGrid:
    section: str                # section name on the Related tab
    label: str
    target_logical: str         # child table
    relationship: str           # relationship schema name
    view_id: str                # child table view shown in the grid


@dataclass
class TableSpec:
    schema: str
    display: str
    plural: str
    description: str
    fields: list
    form: list                  # [(tab name, tab label, [(section name, label, [field names])])]
    active_view_first: list
    inactive_view: list
    key_field: str
    key_display: str
    optionsets: dict = field(default_factory=dict)   # name -> (display, [labels])
    related: list = field(default_factory=list)       # [RelatedGrid]

    @property
    def logical(self):
        return self.schema.lower()

    def gid(self, name):
        return "{%s}" % uuid.uuid5(uuid.NAMESPACE_URL, f"alsanidi/{self.logical}/{name}")

    def view_id(self, view_name):
        return view_id_for(self.logical, view_name)

    def relationship_name(self, lookup_field):
        target = next(f[3] for f in self.fields if f[0] == lookup_field).lower()
        return f"{self.logical}_{lookup_field.replace('sanidi_', '')}_{target}"


def view_id_for(logical, view_name):
    """ID of a view generated for another table (used by Related-tab grids)."""
    return "{%s}" % uuid.uuid5(uuid.NAMESPACE_URL, f"alsanidi/{logical}/view/{view_name}")


def set_tag(block, tag, value):
    return re.sub(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{value}</{tag}>", block, count=1)


def set_labels(block, display, desc):
    """Replace the column's own display name and description (not its option set's)."""
    cut = block.rfind("</optionset>")
    head, tail = (block[:cut], block[cut:]) if cut >= 0 else ("", block)
    tail = re.sub(r"\s*<displaynames>.*?</displaynames>", "", tail, count=1, flags=re.S)
    tail = re.sub(r"\s*<Descriptions>.*?</Descriptions>", "", tail, count=1, flags=re.S)
    labels = (f'\n              <displaynames>\n                <displayname description="{escape(display)}" '
              f'languagecode="1033" />\n              </displaynames>\n              <Descriptions>\n'
              f'                <Description description="{escape(desc)}" languagecode="1033" />\n'
              f'              </Descriptions>\n            ')
    tail = re.sub(r"\s*</attribute>\s*$", lambda _: labels + "</attribute>", tail)
    return head + tail


def option_xml(values, indent):
    pad = " " * indent
    return "\n".join(
        f'{pad}<option value="{i}" ExternalValue="" IsHidden="0">\n'
        f'{pad}  <labels>\n{pad}    <label description="{escape(v)}" languagecode="1033" />\n'
        f'{pad}  </labels>\n{pad}  <Descriptions>\n'
        f'{pad}    <Description description="" languagecode="1033" />\n{pad}  </Descriptions>\n'
        f'{pad}</option>' for i, v in enumerate(values, start=1))


def rename(block, old_physical, new_logical):
    old_logical = re.search(r"<LogicalName>([^<]+)</LogicalName>", block).group(1)
    return block.replace(f'PhysicalName="{old_physical}"', f'PhysicalName="{new_logical}"') \
                .replace(f"<Name>{old_logical}</Name>", f"<Name>{new_logical}</Name>") \
                .replace(f"<LogicalName>{old_logical}</LogicalName>", f"<LogicalName>{new_logical}</LogicalName>")


class Template:
    def __init__(self, template_zip):
        self.zip = zipfile.ZipFile(template_zip)
        self.c = self.zip.read("customizations.xml").decode("utf-8-sig")
        self.solution = self.zip.read("solution.xml").decode("utf-8-sig")
        self.meta = self.entity("sanidi_MetaCampaign")
        self.attrs = self.attr_blocks(self.meta)
        adset = self.entity("sanidi_MetaAdSet")
        self.lookup = next(b for n, b in self.attr_blocks(adset).items()
                           if "<Type>lookup</Type>" in b and "<IsCustomField>1</IsCustomField>" in b)
        self.relationship = re.search(
            r'<EntityRelationship Name="sanidi_metaadset_metacampaignid_sanidi_metacampaign">.*?</EntityRelationship>',
            self.c, re.S).group(0)
        self.multiline = next(b for b in self.attr_blocks(self.entity("sanidi_Meta_Ad")).values()
                              if "<Type>ntext</Type>" in b and "<IsCustomField>1</IsCustomField>" in b)
        self.subgrid_cell = re.search(r'<cell [^>]*rowspan="10".*?</cell>', self.meta, re.S).group(0)

    def entity(self, schema):
        start = self.c.index(f">{schema}</Name>")
        return self.c[self.c.rindex("<Entity>", 0, start):self.c.index("</Entity>", start) + len("</Entity>")]

    @staticmethod
    def attr_blocks(xml):
        return {m.group(2): m.group(1) for m in
                re.finditer(r'(<attribute PhysicalName="([^"]+)">.*?</attribute>)', xml, re.S)}


def build_attribute(spec, t, f):
    name, display, kind, extra, desc = f
    src = {"text": "sanidi_accountid", "choice": "sanidi_bidstrategy", "bool": "sanidi_adsetbudgetsharingenabled",
           "datetime": "sanidi_starttime", "money": "sanidi_budgetremaining", "int": "sanidi_toplineid",
           "decimal": "sanidi_budgetremaining"}
    if kind == "multichoice":
        b = MULTISELECT_TEMPLATE.replace("NAME", name).replace("OPTIONSET", extra[0])
    elif kind == "multiline":
        b = rename(t.multiline, re.search(r'PhysicalName="([^"]+)"', t.multiline).group(1), name)
    elif kind == "lookup":
        b = rename(t.lookup, re.search(r'PhysicalName="([^"]+)"', t.lookup).group(1), name)
    elif f is spec.fields[0]:
        b = rename(t.attrs["sanidi_campaignname"], "sanidi_campaignname", name)   # primary name column
    else:
        b = rename(t.attrs[src[kind]], src[kind], name)
    b = set_labels(b, display, desc)
    if kind == "text":
        b = set_tag(set_tag(b, "MaxLength", extra), "Length", extra * 2)
    if kind in ("choice", "bool"):
        b = re.sub(r'<optionset Name="[^"]+">', f'<optionset Name="{spec.logical}_{name}">', b, count=1)
        b = re.sub(r'(<optionset .*?<displaynames>\s*<displayname description=")[^"]*',
                   lambda m: m.group(1) + escape(display), b, count=1, flags=re.S)
    if kind == "choice":
        b = re.sub(r"<options>.*?</options>", "<options>\n" + option_xml(extra, 18) + "\n                </options>",
                   b, count=1, flags=re.S)
    if kind == "decimal":
        b = b.replace("<Type>money</Type>", "<Type>decimal</Type>")
        b = re.sub(r"\s*<AccuracySource>[^<]*</AccuracySource>", "", b)
        b = set_tag(set_tag(set_tag(b, "MinValue", "-100000000000"), "MaxValue", "100000000000"), "Accuracy", "2")
    blocks = [b]
    if kind == "money":
        base = rename(t.attrs["sanidi_budgetremaining_Base"], "sanidi_budgetremaining_Base", f"{name}_base")
        base = base.replace(f'PhysicalName="{name}_base"', f'PhysicalName="{name}_Base"')
        base = set_labels(set_tag(base, "CalculationOf", name), f"{display} (Base)",
                          f"Value of the {display} in base currency.")
        blocks.append(base)
    return blocks


def relationship_xml(spec, t, lookup_field):
    target = next(f[3] for f in spec.fields if f[0] == lookup_field)
    name = spec.relationship_name(lookup_field)
    r = t.relationship
    r = r.replace("sanidi_metaadset_metacampaignid_sanidi_metacampaign", name)
    r = set_tag(r, "ReferencingEntityName", spec.schema)
    r = set_tag(r, "ReferencedEntityName", target)
    r = set_tag(r, "ReferencingAttributeName", lookup_field)
    r = r.replace("<NavigationPropertyName>sanidi_metacampaignid</NavigationPropertyName>",
                  f"<NavigationPropertyName>{lookup_field}</NavigationPropertyName>")
    display = next(f[1] for f in spec.fields if f[0] == lookup_field)
    return re.sub(r'<Description description="[^"]*"', f'<Description description="Parent {escape(display)}"', r, 1)


def form_xml(spec, t):
    by_name = {f[0]: f for f in spec.fields}
    tabs = []
    for tab_name, tab_label, sections in spec.form:
        width = f"{100 // len(sections)}%"
        cols = []
        for sec_name, sec_label, fields in sections:
            rows = []
            for f in fields:
                kind = "owner" if f == "ownerid" else by_name[f][2]
                label = "Owner" if f == "ownerid" else by_name[f][1]
                rows.append(f'<row><cell id="{spec.gid("cell/" + f)}"><labels><label description="{escape(label)}" '
                            f'languagecode="1033" /></labels><control id="{f}" classid="{CLASSIDS[kind]}" '
                            f'datafieldname="{f}" /></cell></row>')
            cols.append(f'<column width="{width}"><sections><section name="{sec_name}" showlabel="true" '
                        f'showbar="false" IsUserDefined="0" id="{spec.gid("section/" + sec_name)}" columns="1" '
                        f'labelwidth="200"><labels><label description="{escape(sec_label)}" languagecode="1033" />'
                        f'</labels><rows>{"".join(rows)}</rows></section></sections></column>')
        tabs.append(f'<tab name="{tab_name}" verticallayout="true" id="{spec.gid("tab/" + tab_name)}" '
                    f'IsUserDefined="1" expanded="true" showlabel="true"><labels><label '
                    f'description="{escape(tab_label)}" languagecode="1033" /></labels><columns>{"".join(cols)}'
                    f'</columns></tab>')
    if spec.related:
        sections = []
        for g in spec.related:
            cell = t.subgrid_cell
            cell = re.sub(r'<cell id="[^"]+"', f'<cell id="{spec.gid("cell/" + g.section)}"', cell, 1)
            cell = re.sub(r'description="[^"]*"', f'description="{escape(g.label)}"', cell)
            cell = re.sub(r'<control id="[^"]+"', f'<control id="{g.section}"', cell, 1)
            cell = re.sub(r'uniqueid="[^"]+"', f'uniqueid="{spec.gid("grid/" + g.section)}"', cell, 1)
            cell = set_tag(cell, "TargetEntityType", g.target_logical)
            cell = set_tag(cell, "ViewId", g.view_id)
            cell = set_tag(cell, "RelationshipName", g.relationship)
            sections.append(f'<section name="{g.section}" showlabel="false" showbar="false" IsUserDefined="0" '
                            f'id="{spec.gid("section/" + g.section)}" columns="1"><labels><label '
                            f'description="{escape(g.label)}" languagecode="1033" /></labels><rows><row>{cell}</row>'
                            + "<row />" * 9 + "</rows></section>")
        tabs.append(f'<tab name="related" verticallayout="true" id="{spec.gid("tab/related")}" IsUserDefined="1" '
                    f'expanded="true" showlabel="true"><labels><label description="Related" languagecode="1033" />'
                    f'</labels><columns><column width="100%"><sections>{"".join(sections)}</sections></column>'
                    f'</columns></tab>')
    return f"""<FormXml>
        <forms type="main">
          <systemform>
            <formid>{spec.gid("form/main")}</formid>
            <IntroducedVersion>1.0.0</IntroducedVersion>
            <FormPresentation>1</FormPresentation>
            <FormActivationState>1</FormActivationState>
            <form headerdensity="HighWithControls">
              <tabs>{"".join(tabs)}</tabs>
              <DisplayConditions Order="0" FallbackForm="true">
                <Everyone />
              </DisplayConditions>
            </form>
            <IsCustomizable>1</IsCustomizable>
            <CanBeDeleted>1</CanBeDeleted>
            <LocalizedNames>
              <LocalizedName description="Information" languagecode="1033" />
            </LocalizedNames>
            <Descriptions>
              <Description description="A form for this entity." languagecode="1033" />
            </Descriptions>
          </systemform>
        </forms>
      </FormXml>"""


def view_columns(spec, q, columns):
    pk = f"{spec.logical}id"
    widths = {spec.fields[0][0]: 300, "createdon": 125}
    cells = "".join(f'<cell name="{c}" width="{widths.get(c, 150)}" />' for c in columns)
    q = re.sub(r'<row name="result" id="[^"]+">.*?</row>', f'<row name="result" id="{pk}">{cells}</row>',
               q, count=1, flags=re.S)
    attrs = "".join(f'<attribute name="{c}" />' for c in [pk] + columns)
    q = re.sub(r'\s*<attribute name="[^"]+" />', "", q)
    return re.sub(r'(<entity name="[^"]+">)', rf"\g<1>{attrs}", q, count=1)


def saved_queries(spec, t):
    primary = spec.fields[0][0]
    names = {f[0] for f in spec.fields}
    out = []
    for q in re.findall(r"<savedquery>.*?</savedquery>", t.meta, re.S):
        name = re.search(r'<LocalizedName description="([^"]+)" languagecode="1033"', q).group(1)
        name = name.replace("Meta Campaigns", spec.plural).replace("Meta Campaign", spec.display)
        q = q.replace(TEMPLATE_LOGICAL, spec.logical).replace("Meta Campaigns", spec.plural) \
             .replace("Meta Campaign", spec.display).replace('"sanidi_campaignname"', f'"{primary}"')
        q = re.sub(r'<LocalizedName description="[^"]*" languagecode="1025" />\s*', "", q)
        q = re.sub(r"<savedqueryid>[^<]+</savedqueryid>", f"<savedqueryid>{spec.view_id(name)}</savedqueryid>", q)
        if name.startswith("Active"):
            q = view_columns(spec, q, spec.active_view_first +
                             [f[0] for f in spec.fields if f[0] not in spec.active_view_first])
        elif name.startswith("Inactive"):
            q = view_columns(spec, q, spec.inactive_view)
        else:
            keep = [c for c in re.findall(r'<cell name="([^"]+)"', q) if c in names or not c.startswith("sanidi_")]
            q = view_columns(spec, q, keep or [primary])
        out.append(q)
    return "<SavedQueries>\n        <savedqueries>\n          " + "\n          ".join(out) + \
           "\n        </savedqueries>\n      </SavedQueries>"


def optionset_xml(name, display, values):
    return f"""<optionset Name="{name}" localizedName="{escape(display)}">
      <OptionSetType>picklist</OptionSetType>
      <IsGlobal>1</IsGlobal>
      <IntroducedVersion>1.0.0</IntroducedVersion>
      <IsCustomizable>1</IsCustomizable>
      <ExternalTypeName></ExternalTypeName>
      <displaynames>
        <displayname description="{escape(display)}" languagecode="1033" />
      </displaynames>
      <Descriptions>
        <Description description="" languagecode="1033" />
      </Descriptions>
      <options>
{option_xml(values, 8)}
      </options>
    </optionset>"""


def entity_xml(spec, t):
    system = [b for n, b in t.attrs.items() if not n.startswith("sanidi_")]
    pk = rename(t.attrs[f"{TEMPLATE_SCHEMA}Id"], f"{TEMPLATE_SCHEMA}Id", f"{spec.logical}id") \
        .replace(f'PhysicalName="{spec.logical}id"', f'PhysicalName="{spec.schema}Id"')
    pk = re.sub(r"<displaynames>.*?</displaynames>",
                f'<displaynames>\n                <displayname description="{spec.display}" languagecode="1033" />\n'
                f"              </displaynames>", pk, count=1, flags=re.S)
    custom = [b for f in spec.fields for b in build_attribute(spec, t, f)]
    attributes = "<attributes>\n            " + "\n            ".join(system + [pk] + custom) + "\n          </attributes>"
    e = t.meta
    head = e[:e.index("<attributes>")]
    head = re.sub(r"<LocalizedNames>.*?</Descriptions>",
                  f'<LocalizedNames>\n            <LocalizedName description="{spec.display}" languagecode="1033" />\n'
                  f'          </LocalizedNames>\n          <LocalizedCollectionNames>\n'
                  f'            <LocalizedCollectionName description="{spec.plural}" languagecode="1033" />\n'
                  f'          </LocalizedCollectionNames>\n          <Descriptions>\n'
                  f'            <Description description="{escape(spec.description)}" languagecode="1033" />\n'
                  f"          </Descriptions>", head, count=1, flags=re.S)
    info_tail = e[e.index("</attributes>") + len("</attributes>"):e.index("</EntityInfo>")]
    info_tail = re.sub(r"\s*<EntityKeys>.*?</EntityKeys>", "", info_tail, flags=re.S)
    info_tail = set_tag(info_tail, "EntitySetName", f"{spec.logical}s")
    key = f"""<EntityKeys>
            <EntityKey>
              <Name>{spec.schema}_{spec.key_display.replace(' ', '')}Key</Name>
              <LogicalName>{spec.logical}_{spec.key_field.replace('sanidi_', '')}key</LogicalName>
              <IntroducedVersion>1.0.0</IntroducedVersion>
              <IsCustomizable>1</IsCustomizable>
              <EntityKeyAttributes>
                <AttributeName>{spec.key_field}</AttributeName>
              </EntityKeyAttributes>
              <displaynames>
                <displayname description="{spec.key_display} Key" languagecode="1033" />
              </displaynames>
            </EntityKey>
          </EntityKeys>
          """
    ribbon = re.search(r"<RibbonDiffXml>.*?</RibbonDiffXml>", e, re.S).group(0)
    entity = (head + attributes + "\n          " + key + info_tail.lstrip() + "</EntityInfo>\n      "
              + form_xml(spec, t) + "\n      " + saved_queries(spec, t) + "\n      " + ribbon + "\n    </Entity>")
    return entity.replace(TEMPLATE_SCHEMA, spec.schema).replace(TEMPLATE_LOGICAL, spec.logical) \
                 .replace("Meta Campaigns", spec.plural).replace("Meta Campaign", spec.display)


def solution_xml(template_solution, root_components):
    """solution.xml for AlSanidi | Marketing, taking the publisher block from the template export."""
    publisher = re.search(r"<Publisher>.*?</Publisher>", template_solution, re.S).group(0)
    roots = "\n      ".join(root_components)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ImportExportXml version="9.2" SolutionPackageVersion="9.2" languagecode="1033" generatedBy="CrmLive" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <SolutionManifest>
    <UniqueName>AlSanidiMarketing</UniqueName>
    <LocalizedNames>
      <LocalizedName description="AlSanidi | Marketing" languagecode="1033" />
    </LocalizedNames>
    <Descriptions />
    <Version>1.0.0</Version>
    <Managed>0</Managed>
    {publisher}
    <RootComponents>
      {roots}
    </RootComponents>
    <MissingDependencies />
  </SolutionManifest>
</ImportExportXml>
"""


def build_package(spec, template_zip, out):
    t = Template(template_zip)
    entity = entity_xml(spec, t)

    system_rels = [f"business_unit_{TEMPLATE_LOGICAL}", f"lk_{TEMPLATE_LOGICAL}_createdby",
                   f"lk_{TEMPLATE_LOGICAL}_modifiedby", f"owner_{TEMPLATE_LOGICAL}", f"team_{TEMPLATE_LOGICAL}",
                   f"TransactionCurrency_{TEMPLATE_SCHEMA}", f"user_{TEMPLATE_LOGICAL}"]
    rels = [re.search(rf'<EntityRelationship Name="{n}">.*?</EntityRelationship>', t.c, re.S).group(0)
            .replace(TEMPLATE_SCHEMA, spec.schema).replace(TEMPLATE_LOGICAL, spec.logical) for n in system_rels]
    rels += [relationship_xml(spec, t, f[0]) for f in spec.fields if f[2] == "lookup"]
    optionsets = [optionset_xml(n, d, v) for n, (d, v) in spec.optionsets.items()]

    root_open = re.match(r".*?<ImportExportXml[^>]*>", t.c, re.S).group(0)
    customizations = (f"{root_open}\n  <Entities>\n    {entity}\n  </Entities>\n  <Roles />\n  <Workflows />\n"
                      f"  <FieldSecurityProfiles />\n  <Templates />\n  <EntityMaps />\n  <EntityRelationships>\n    "
                      + "\n    ".join(rels) + "\n  </EntityRelationships>\n  <OrganizationSettings />\n"
                      + "  <optionsets>\n    " + "\n    ".join(optionsets) + "\n  </optionsets>\n"
                      "  <CustomControls />\n  <EntityDataProviders />\n  <Languages>\n    <Language>1033</Language>\n"
                      "  </Languages>\n</ImportExportXml>\n")

    roots = [f'<RootComponent type="1" schemaName="{spec.logical}" behavior="0" />'] + \
            [f'<RootComponent type="9" schemaName="{n}" behavior="0" />' for n in spec.optionsets]
    solution = solution_xml(t.solution, roots)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", t.zip.read("[Content_Types].xml"))
        z.writestr("solution.xml", solution)
        z.writestr("customizations.xml", customizations)
    print(f"Wrote {out}: {spec.schema}, {len(spec.fields)} columns, {len(rels)} relationships, "
          f"{len(optionsets)} global choices")
