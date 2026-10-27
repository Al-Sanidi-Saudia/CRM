"""Builds marketing auto numbering in UAT, inside a patch of the AlSanidi | Marketing solution.

  python3 deploy.py            # dry run: what would be created / changed
  python3 deploy.py --apply    # create what is missing, update forms and scripts, register the plug-in, publish

Run migrate_channels.py --apply first: it moves existing data off the channel options this removes.
Safe to re-run: existing components are kept and only missing pieces are added.

- Patch "AlSanidi | Marketing | Auto Numbering" (1.0.1.0) of AlSanidiMarketing. Production runs AlSanidiMarketing
  1.0.0 managed, so the managed patch layers only these changes on top of it; flows, connection references and
  environment variables are not touched. Everything below is created in or added to the patch.
- Table sanidi_autonumbersetting (organization owned): campaign prefix, channel codes, current year, last campaign
  number. One row; the plug-in creates it with the defaults (MC, M, S, T, G) if it is missing.
- Campaign: Description, 4 read-only channel numbers, 4 hidden last-advertisement-number counters. Name is no longer
  required on the form (the plug-in sets it).
- Global choice sanidi_socialmediachannel: Meta (1), Snap (5), TikTok (4), Google Ads (6), in that order.
- Forms: Name read-only on Campaign (main, quick create) and Advertisement (main); Description under Name;
  channel numbers in the Social Media Channel section. Form scripts from webresources/.
- Plug-in Sanidi.Marketing.Plugins.AutoNumbering (build plugin/ first: dotnet build -c Release) with 3 steps.
- Site map: a Settings group at the end of the General area of AlSanidi | Marketing.
"""
import base64
import re
import sys
import time
import urllib.error
import uuid
from pathlib import Path
from xml.sax.saxutils import quoteattr

HERE = Path(__file__).parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "scripts"))
from dv import Dataverse  # noqa: E402

PARENT = "AlSanidiMarketing"
PATCH_NAME = "AlSanidi | Marketing | Auto Numbering"
PATCH_VERSION = "1.0.1.0"
APP = "sanidi_AlSanidiMarketing"
GENERAL_AREA = 'Id="area_93dfabcb"'
CHOICE = "sanidi_socialmediachannel"
SETTINGS = "sanidi_autonumbersetting"
CAMPAIGN = "sanidi_campaign"
ADVERTISEMENT = "sanidi_advertisement"
ASSEMBLY = "Sanidi.Marketing.Plugins"
ASSEMBLY_VERSION = "1.0.0.0"
PUBLIC_KEY_TOKEN = "1b1744d78384526e"
PLUGIN_TYPE = "Sanidi.Marketing.Plugins.AutoNumbering"
DLL = HERE / "plugin" / "bin" / "Release" / "net462" / f"{ASSEMBLY}.dll"
SCRIPTS = ["sanidi_/scripts/campaign.form.js", "sanidi_/scripts/advertisement.form.js"]
NS = uuid.UUID("5b0d3f7e-61a4-4c1b-9d0e-2f8a6c4e7b91")
TEXT_CLASS = "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}"
MEMO_CLASS = "{E0DECE4B-6FC8-4a8f-A065-082708572369}"

# (value, English, Arabic) in display order. Brand names stay in Latin script in Arabic, like the old options.
CHANNELS = [(1, "Meta", "Meta"), (5, "Snap", "Snap"), (4, "TikTok", "TikTok"), (6, "Google Ads", "Google Ads")]

# Campaign channel columns: (channel, number column, counter column)
CHANNEL_COLUMNS = [
    ("Meta", "ميتا", "sanidi_metanumber", "sanidi_lastmetaadnumber", "sanidi_metacampaign"),
    ("Snap", "سناب", "sanidi_snapnumber", "sanidi_lastsnapadnumber", "sanidi_snapcampaign"),
    ("TikTok", "تيك توك", "sanidi_tiktoknumber", "sanidi_lasttiktokadnumber", "sanidi_tiktokcampaign"),
    ("Google Ads", "إعلانات جوجل", "sanidi_googleadsnumber", "sanidi_lastgoogleadsadnumber",
     "sanidi_googleadscampaign"),
]

# Existing campaign columns changed for this release: Name (no longer required, the plug-in sets it) and
# Start Date / End Date (made Recommended instead of required in UAT).
CHANGED_CAMPAIGN_COLUMNS = ["sanidi_name", "sanidi_startdate", "sanidi_enddate"]

STEPS = [  # (name, message, table, filtering attributes)
    ("AutoNumbering: Create of sanidi_campaign", "Create", CAMPAIGN, None),
    ("AutoNumbering: Update of sanidi_campaign (channels)", "Update", CAMPAIGN, CHOICE),
    ("AutoNumbering: Create of sanidi_advertisement", "Create", ADVERTISEMENT, None),
]

# Solution component types
ENTITY, ATTRIBUTE, OPTIONSET, FORM, WEBRESOURCE, SITEMAP = 1, 2, 9, 60, 61, 62
PLUGIN_ASSEMBLY, PLUGIN_STEP = 91, 92


def label(en, ar):
    return {"@odata.type": "Microsoft.Dynamics.CRM.Label", "LocalizedLabels": [
        {"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": en, "LanguageCode": 1033},
        {"@odata.type": "Microsoft.Dynamics.CRM.LocalizedLabel", "Label": ar, "LanguageCode": 1025}]}


def required(level):
    return {"Value": level, "CanBeChanged": True, "ManagedPropertyLogicalName": "canmodifyrequirementlevelsettings"}


def text(schema, en, ar, desc_en, desc_ar, length, level="None"):
    return {"@odata.type": "Microsoft.Dynamics.CRM.StringAttributeMetadata", "SchemaName": schema,
            "DisplayName": label(en, ar), "Description": label(desc_en, desc_ar), "RequiredLevel": required(level),
            "MaxLength": length, "FormatName": {"Value": "Text"}}


def whole(schema, en, ar, desc_en, desc_ar):
    return {"@odata.type": "Microsoft.Dynamics.CRM.IntegerAttributeMetadata", "SchemaName": schema,
            "DisplayName": label(en, ar), "Description": label(desc_en, desc_ar), "RequiredLevel": required("None"),
            "MinValue": 0, "MaxValue": 2147483647, "Format": "None"}


# ---------------------------------------------------------------------------------------------------------------
# Patch

def find_patch(dv):
    parent = dv.first(f"solutions?$select=solutionid,version&$filter=uniquename eq '{PARENT}'")
    patch = dv.first(f"solutions?$select=uniquename,version,friendlyname&$filter=_parentsolutionid_value eq "
                     f"{parent['solutionid']} and friendlyname eq '{PATCH_NAME}'")
    return parent, patch


def deploy_patch(dv, apply):
    parent, patch = find_patch(dv)
    print(f"patch: {patch['uniquename'] + ' ' + patch['version'] if patch else 'create'} "
          f"(parent {PARENT} {parent['version']})")
    if patch or not apply:
        return patch["uniquename"] if patch else None
    dv.request("POST", "CloneAsPatch", {"ParentSolutionUniqueName": PARENT, "DisplayName": PATCH_NAME,
                                       "VersionNumber": PATCH_VERSION})
    patch = find_patch(dv)[1]
    print(f"  created {patch['uniquename']}")
    return patch["uniquename"]


def add_component(dv, solution, component_type, component_id, subcomponents=False):
    """Tables are added without their columns and forms (only the changed ones are added separately)."""
    dv.request("POST", "AddSolutionComponent", idempotent=True, body={
        "ComponentId": component_id, "ComponentType": component_type, "SolutionUniqueName": solution,
        "AddRequiredComponents": False,
        "DoNotIncludeSubcomponents": component_type == ENTITY and not subcomponents})


# ---------------------------------------------------------------------------------------------------------------
# Metadata

def metadata_retry(dv, method, path, body, solution, exists):
    """Metadata writes sometimes fail transiently; retry only after checking the change isn't there."""
    for attempt in range(4):
        try:
            return dv.request(method, path, body, solution=solution)
        except (RuntimeError, urllib.error.URLError, ConnectionError, TimeoutError) as e:
            text_ = str(e).lower()
            # "Cannot start another [EntityCustomization]": metadata changes run one at a time per environment.
            transient = not isinstance(e, RuntimeError) or "unexpected error" in text_ or "cannot start another" in text_
            if attempt == 3 or not transient:
                raise
            time.sleep(10 * (attempt + 1))
            if exists():
                return None


def attributes(dv, table):
    return {a["LogicalName"]: a["MetadataId"] for a in dv.get(
        f"EntityDefinitions(LogicalName='{table}')/Attributes?$select=LogicalName,MetadataId")["value"]}


def table_exists(dv, table):
    return dv.first(f"EntityDefinitions?$select=LogicalName&$filter=LogicalName eq '{table}'") is not None


def settings_columns():
    return [
        ("sanidi_campaignprefix", text("sanidi_CampaignPrefix", "Campaign Prefix", "بادئة الحملة",
                                       "Starts every campaign number, e.g. MC in MC-2026-01.",
                                       "تبدأ بها أرقام الحملات، مثل MC في MC-2026-01.", 10, "ApplicationRequired")),
        ("sanidi_metacode", text("sanidi_MetaCode", "Meta Code", "رمز ميتا",
                                 "Added to the campaign number for Meta, e.g. M in MC-2026-01-M.",
                                 "يضاف إلى رقم الحملة لقناة ميتا، مثل M في MC-2026-01-M.", 5, "ApplicationRequired")),
        ("sanidi_snapcode", text("sanidi_SnapCode", "Snap Code", "رمز سناب",
                                 "Added to the campaign number for Snap, e.g. S in MC-2026-01-S.",
                                 "يضاف إلى رقم الحملة لقناة سناب، مثل S في MC-2026-01-S.", 5, "ApplicationRequired")),
        ("sanidi_tiktokcode", text("sanidi_TikTokCode", "TikTok Code", "رمز تيك توك",
                                   "Added to the campaign number for TikTok, e.g. T in MC-2026-01-T.",
                                   "يضاف إلى رقم الحملة لقناة تيك توك، مثل T في MC-2026-01-T.", 5,
                                   "ApplicationRequired")),
        ("sanidi_googleadscode", text("sanidi_GoogleAdsCode", "Google Ads Code", "رمز إعلانات جوجل",
                                      "Added to the campaign number for Google Ads, e.g. G in MC-2026-01-G.",
                                      "يضاف إلى رقم الحملة لقناة إعلانات جوجل، مثل G في MC-2026-01-G.", 5,
                                      "ApplicationRequired")),
        ("sanidi_currentyear", text("sanidi_CurrentYear", "Current Year", "السنة الحالية",
                                    "Year of the last campaign number. When the year changes, numbering restarts at 01.",
                                    "سنة آخر رقم حملة. عند تغير السنة يبدأ الترقيم من 01.", 4)),
        ("sanidi_lastcampaignnumber", whole("sanidi_LastCampaignNumber", "Last Campaign Number", "آخر رقم حملة",
                                            "Counter of the last campaign numbered in the current year.",
                                            "عداد آخر حملة تم ترقيمها في السنة الحالية.")),
        ("sanidi_lastnumberissuedon", {
            "@odata.type": "Microsoft.Dynamics.CRM.DateTimeAttributeMetadata", "SchemaName": "sanidi_LastNumberIssuedOn",
            "DisplayName": label("Last Number Issued On", "تاريخ آخر رقم"),
            "Description": label("When the last campaign or advertisement number was issued.",
                                 "وقت إصدار آخر رقم حملة أو إعلان."),
            "RequiredLevel": required("None"), "Format": "DateAndTime",
            "DateTimeBehavior": {"Value": "UserLocal"}}),
    ]


def campaign_columns():
    out = [("sanidi_description", {
        "@odata.type": "Microsoft.Dynamics.CRM.MemoAttributeMetadata", "SchemaName": "sanidi_Description",
        "DisplayName": label("Description", "الوصف"),
        "Description": label("What the campaign is about, written by the marketing manager.",
                             "وصف الحملة يكتبه مدير التسويق."),
        "RequiredLevel": required("None"), "MaxLength": 4000, "Format": "TextArea"})]
    for en, ar, number, counter, _ in CHANNEL_COLUMNS:
        schema = number.replace("sanidi_", "")
        out.append((number, text("sanidi_" + schema[0].upper() + schema[1:], f"{en} Number", f"رقم {ar}",
                                 f"Campaign number for {en}, e.g. MC-2026-01-{en[0]}. Set automatically.",
                                 f"رقم الحملة لقناة {ar}. يُعبأ تلقائيًا.", 100)))
        schema = counter.replace("sanidi_", "")
        out.append((counter, whole("sanidi_" + schema[0].upper() + schema[1:], f"Last {en} Ad Number",
                                   f"آخر رقم إعلان {ar}",
                                   f"Counter of the last {en} advertisement numbered in this campaign.",
                                   f"عداد آخر إعلان {ar} تم ترقيمه في هذه الحملة.")))
    return out


def settings_entity():
    name = text("sanidi_Name", "Name", "الاسم", "Name of the numbering settings.", "اسم إعدادات الترقيم.", 100,
                "ApplicationRequired")
    name["IsPrimaryName"] = True
    return {"@odata.type": "Microsoft.Dynamics.CRM.EntityMetadata", "SchemaName": SETTINGS,
            "DisplayName": label("Auto Numbering Setting", "إعداد الترقيم التلقائي"),
            "DisplayCollectionName": label("Auto Numbering Settings", "إعدادات الترقيم التلقائي"),
            "Description": label("Prefix, channel codes and counters for campaign and advertisement numbers. "
                                 "Keep one active row.",
                                 "البادئة ورموز القنوات والعدادات لأرقام الحملات والإعلانات. يُستخدم سجل نشط واحد."),
            "OwnershipType": "OrganizationOwned", "HasActivities": False, "HasNotes": False, "IsActivity": False,
            "Attributes": [name]}


def deploy_columns(dv, patch, table, columns, apply):
    existing = attributes(dv, table) if table_exists(dv, table) else {}
    todo = [(n, m) for n, m in columns if n not in existing]
    print(f"{table}: {len(todo)} columns to add" + (f" ({', '.join(n for n, _ in todo)})" if todo else ""))
    if not apply:
        return
    path = f"EntityDefinitions(LogicalName='{table}')/Attributes"
    for name, metadata in todo:
        metadata_retry(dv, "POST", path, metadata, patch,
                       lambda: dv.first(f"{path}?$select=LogicalName&$filter=LogicalName eq '{name}'"))


def deploy_settings_table(dv, patch, apply):
    exists = table_exists(dv, SETTINGS)
    print(f"{SETTINGS}: table {'exists' if exists else 'create'}")
    if apply and not exists:
        metadata_retry(dv, "POST", "EntityDefinitions", settings_entity(), patch,
                       lambda: table_exists(dv, SETTINGS))
        print("  created")
        time.sleep(20)  # a brand-new table rejects columns for a short while
    deploy_columns(dv, patch, SETTINGS, settings_columns(), apply)


def deploy_campaign_name(dv, patch, apply):
    path = f"EntityDefinitions(LogicalName='{CAMPAIGN}')/Attributes(LogicalName='sanidi_name')"
    attr = dv.get(f"{path}?$select=RequiredLevel,MetadataId")
    level = attr["RequiredLevel"]["Value"]
    print(f"{CAMPAIGN}.sanidi_name: required level {level}" + (" -> None" if level != "None" else ""))
    if apply and level != "None":
        full = {k: v for k, v in dv.get(f"{path}/Microsoft.Dynamics.CRM.StringAttributeMetadata").items()
                if not k.startswith("@odata")}
        full["@odata.type"] = "Microsoft.Dynamics.CRM.StringAttributeMetadata"
        full["RequiredLevel"]["Value"] = "None"
        dv.request("PUT", path, full, solution=patch, headers={"MSCRM.MergeLabels": "true"})


# ---------------------------------------------------------------------------------------------------------------
# Choice

def deploy_choice(dv, patch, apply):
    choice = dv.get(f"GlobalOptionSetDefinitions(Name='{CHOICE}')")
    options = {o["Value"]: o for o in choice["Options"]}
    labels = {v: {l["LanguageCode"]: l["Label"] for l in o["Label"]["LocalizedLabels"]} for v, o in options.items()}
    relabel = [(v, en, ar) for v, en, ar in CHANNELS if labels.get(v) != {1033: en, 1025: ar}]
    extra = sorted(set(options) - {v for v, *_ in CHANNELS})
    order = [v for v, *_ in CHANNELS]
    reorder = [v for v in options if v in order] != order
    print(f"choice {CHOICE}: relabel {[en for _, en, _ in relabel] or 'none'}; "
          f"{'reorder; ' if reorder else ''}"
          f"{'options still to remove ' + str(extra) + ' (run migrate_channels.py --apply)' if extra else 'no extra options'}")
    if not apply:
        return choice["MetadataId"]
    for value, en, ar in relabel:
        dv.request("POST", "UpdateOptionValue", idempotent=True, body={
            "OptionSetName": CHOICE, "Value": value, "Label": label(en, ar), "MergeLabels": False,
            "SolutionUniqueName": patch})
    if reorder:
        dv.request("POST", "OrderOption", idempotent=True, body={
            "OptionSetName": CHOICE, "Values": order + extra, "SolutionUniqueName": patch})
    return choice["MetadataId"]


# ---------------------------------------------------------------------------------------------------------------
# Forms

def gid(*parts):
    return "{" + str(uuid.uuid5(NS, "/".join(parts))) + "}"


def lbl(en, ar):
    return (f'<labels><label description={quoteattr(en)} languagecode="1033" />'
            f'<label description={quoteattr(ar)} languagecode="1025" /></labels>')


def row(form, field, en, ar, classid, disabled, visible=True, rowspan=1):
    """A cell taller than one row needs an empty <row /> for each extra row, or it covers the rows after it."""
    hidden = "" if visible else ' visible="false"'
    return (f'<row><cell id="{gid(form, field)}" locklevel="0" colspan="1" rowspan="{rowspan}"{hidden}>{lbl(en, ar)}'
            f'<control id="{field}" classid="{classid}" datafieldname="{field}" '
            f'disabled="{"true" if disabled else "false"}" /></cell></row>' + "<row />" * (rowspan - 1))


def section_bounds(xml, field):
    """Start and end of the <rows> of the section holding field."""
    at = xml.find(f'datafieldname="{field}"')
    return xml.rfind("<rows>", 0, at), xml.find("</rows>", at)


def description_spacers(xml):
    """Description spans 3 rows; versions 1.0.1.0 shipped it without the 2 empty rows after it, so it hid the
    next 2 rows (Start/End Date on the main form, Type/Start Date on quick create)."""
    end = row_end(xml, "sanidi_description")
    rest = xml[end:]
    if rest.startswith("<row /><row />"):
        return xml
    return xml[:end] + "<row /><row />" + rest


def drop_duplicate_rows(xml, field):
    """Keeps the first row bound to field in its section and removes later single-cell rows bound to it."""
    start, end = section_bounds(xml, field)
    rows = re.findall(r"<row\s*/>|<row>.*?</row>", xml[start + len("<rows>"):end], re.S)
    seen, kept = False, []
    for r in rows:
        if f'datafieldname="{field}"' in r and r.count("<cell") == 1:
            if seen:
                continue
            seen = True
        kept.append(r)
    return xml[:start + len("<rows>")] + "".join(kept) + xml[end:]


def row_start(xml, field):
    """Start of the <row> holding the first control bound to field."""
    at = xml.find(f'datafieldname="{field}"')
    if at < 0:
        raise SystemExit(f"{field} not found on the form")
    return xml.rfind("<row>", 0, at)


def row_end(xml, field):
    at = xml.find(f'datafieldname="{field}"')
    return xml.find("</row>", at) + len("</row>")


def name_read_only(xml):
    start = xml.find('<control id="sanidi_name"')
    end = xml.find("/>", start)
    control = xml[start:end]
    if 'disabled="true"' in control:
        return xml
    control = control.replace('disabled="false"', "").rstrip() + ' disabled="true" '
    return xml[:start] + control + xml[end:]


def edit_campaign_form(key, xml, numbers):
    xml = name_read_only(xml)
    if 'datafieldname="sanidi_description"' not in xml:
        at = row_end(xml, "sanidi_name")
        xml = xml[:at] + row(key, "sanidi_description", "Description", "الوصف", MEMO_CLASS, False, rowspan=3) + xml[at:]
    xml = description_spacers(xml)
    for field in ("sanidi_startdate", "sanidi_enddate", "sanidi_type"):
        xml = drop_duplicate_rows(xml, field)
    if numbers:
        for en, ar, number, _, lookup in CHANNEL_COLUMNS:
            if f'datafieldname="{number}"' in xml:
                continue
            at = row_start(xml, lookup)
            xml = xml[:at] + row(key, number, f"{en} Number", f"رقم {ar}", TEXT_CLASS, True, visible=False) + xml[at:]
    return xml


FORMS = [  # (key, table, form type, name, edit)
    ("campaign-main", CAMPAIGN, 2, "Information", lambda k, x: edit_campaign_form(k, x, True)),
    ("campaign-quick", CAMPAIGN, 7, "Campaign Quick Create", lambda k, x: edit_campaign_form(k, x, False)),
    ("advertisement-main", ADVERTISEMENT, 2, "Information", lambda k, x: name_read_only(x)),
]


def deploy_forms(dv, patch, apply):
    ids = []
    for key, table, form_type, name, edit in FORMS:
        form = dv.first(f"systemforms?$select=formid,formxml&$filter=objecttypecode eq '{table}' and type eq "
                        f"{form_type} and name eq '{name}'")
        new = edit(key, form["formxml"])
        print(f"form {table} '{name}': {'update' if new != form['formxml'] else 'up to date'}")
        ids.append(form["formid"])
        if apply and new != form["formxml"]:
            dv.request("PATCH", f"systemforms({form['formid']})", {"formxml": new}, solution=patch)
    return ids


INT_CLASS = "{C6D124CA-7EDA-4a60-AEA9-7FB8D318B68F}"
DATETIME_CLASS = "{5B773807-9FB2-42db-97C3-7A91EFF8ADFF}"
SETTINGS_SECTIONS = [  # (key, English, Arabic, [(column, English, Arabic, classid)])
    ("numbering", "Campaign Numbering", "ترقيم الحملات", [
        ("sanidi_name", "Name", "الاسم", TEXT_CLASS),
        ("sanidi_campaignprefix", "Campaign Prefix", "بادئة الحملة", TEXT_CLASS),
        ("sanidi_currentyear", "Current Year", "السنة الحالية", TEXT_CLASS),
        ("sanidi_lastcampaignnumber", "Last Campaign Number", "آخر رقم حملة", INT_CLASS),
        ("sanidi_lastnumberissuedon", "Last Number Issued On", "تاريخ آخر رقم", DATETIME_CLASS)]),
    ("channels", "Channel Codes", "رموز القنوات", [
        ("sanidi_metacode", "Meta Code", "رمز ميتا", TEXT_CLASS),
        ("sanidi_snapcode", "Snap Code", "رمز سناب", TEXT_CLASS),
        ("sanidi_tiktokcode", "TikTok Code", "رمز تيك توك", TEXT_CLASS),
        ("sanidi_googleadscode", "Google Ads Code", "رمز إعلانات جوجل", TEXT_CLASS)]),
]
SETTINGS_VIEW = ["sanidi_name", "sanidi_campaignprefix", "sanidi_currentyear", "sanidi_lastcampaignnumber",
                 "sanidi_metacode", "sanidi_snapcode", "sanidi_tiktokcode", "sanidi_googleadscode"]


def settings_form_xml():
    sections = "".join(
        f'<section name="{key}" showlabel="true" showbar="false" IsUserDefined="0" id="{gid("settings", key)}" '
        f'columns="1" labelwidth="160">{lbl(en, ar)}<rows>'
        + "".join(row("settings", c, cen, car, cls, False) for c, cen, car, cls in cells)
        + "</rows></section>"
        for key, en, ar, cells in SETTINGS_SECTIONS)
    return (f'<form><tabs><tab name="general" verticallayout="true" id="{gid("settings", "tab")}" IsUserDefined="1" '
            f'expanded="true" showlabel="false">{lbl("General", "عام")}<columns><column width="50%"><sections>'
            f'{sections}</sections></column></columns></tab></tabs></form>')


def settings_view_xml(otc, view_id, active):
    attrs = "".join(f'<attribute name="{c}" />' for c in [SETTINGS + "id"] + SETTINGS_VIEW)
    fetch = (f'<fetch version="1.0" mapping="logical" savedqueryid="{view_id}"><entity name="{SETTINGS}">{attrs}'
             f'<order attribute="sanidi_name" descending="false" /><filter type="and">'
             f'<condition attribute="statecode" operator="eq" value="{0 if active else 1}" /></filter></entity></fetch>')
    cells = "".join(f'<cell name="{c}" width="{200 if c == "sanidi_name" else 120}" />' for c in SETTINGS_VIEW)
    layout = (f'<grid name="resultset" jump="sanidi_name" select="1" icon="1" preview="1" object="{otc}">'
              f'<row name="result" id="{SETTINGS}id">{cells}</row></grid>')
    return fetch, layout


def deploy_settings_ui(dv, patch, apply):
    if not table_exists(dv, SETTINGS):
        print("settings form / views: after the table is created")
        return
    otc = dv.get(f"EntityDefinitions(LogicalName='{SETTINGS}')?$select=ObjectTypeCode")["ObjectTypeCode"]
    form = dv.first(f"systemforms?$select=formid,formxml&$filter=objecttypecode eq '{SETTINGS}' and type eq 2")
    views = dv.get(f"savedqueries?$select=savedqueryid,name,isdefault,layoutxml&$filter=returnedtypecode eq "
                   f"'{SETTINGS}' and querytype eq 0")["value"]
    # Dataverse rewrites saved form XML, so check that every column is on the form instead of comparing text.
    form_changed = any(f'datafieldname="{c}"' not in form["formxml"]
                       for _, _, _, cells in SETTINGS_SECTIONS for c, *_ in cells)
    print(f"settings form: {'update' if form_changed else 'up to date'}")
    for view in views:
        fetch, layout = settings_view_xml(otc, view["savedqueryid"], view["isdefault"])
        changed = view["layoutxml"] != layout
        print(f"settings view '{view['name']}': {'update' if changed else 'up to date'}")
        if apply and changed:
            dv.request("PATCH", f"savedqueries({view['savedqueryid']})", {"fetchxml": fetch, "layoutxml": layout},
                       solution=patch)
    if apply and form_changed:
        dv.request("PATCH", f"systemforms({form['formid']})", {"formxml": settings_form_xml()}, solution=patch)


def deploy_scripts(dv, patch, apply):
    ids = []
    for name in SCRIPTS:
        content = base64.b64encode((REPO / "webresources" / name).read_bytes()).decode()
        wr = dv.first(f"webresourceset?$select=webresourceid,content&$filter=name eq '{name}'")
        changed = wr["content"] != content
        print(f"web resource {name}: {'update' if changed else 'up to date'}")
        ids.append(wr["webresourceid"])
        if apply and changed:
            dv.request("PATCH", f"webresourceset({wr['webresourceid']})", {"content": content}, solution=patch)
    return ids


# ---------------------------------------------------------------------------------------------------------------
# Plug-in

def deploy_plugin(dv, patch, apply):
    if not DLL.exists():
        raise SystemExit(f"{DLL} not found: run 'dotnet build -c Release' in {HERE / 'plugin'}")
    content = base64.b64encode(DLL.read_bytes()).decode()
    assembly = dv.first(f"pluginassemblies?$select=pluginassemblyid,version,content&$filter=name eq '{ASSEMBLY}'")
    print(f"plug-in assembly {ASSEMBLY}: "
          f"{'create' if not assembly else 'update' if assembly['content'] != content else 'up to date'}")
    if not apply:
        steps = [n for n, *_ in STEPS
                 if not dv.first(f"sdkmessageprocessingsteps?$select=name&$filter=name eq '{n}'")]
        print(f"plug-in steps to register: {steps or 'none'}")
        return None, []
    body = {"name": ASSEMBLY, "content": content, "isolationmode": 2, "sourcetype": 0, "culture": "neutral",
            "version": ASSEMBLY_VERSION, "publickeytoken": PUBLIC_KEY_TOKEN,
            "description": "Auto numbering of marketing campaigns and advertisements."}
    if not assembly:
        dv.request("POST", "pluginassemblies", body, solution=patch, idempotent=False)
        assembly = dv.first(f"pluginassemblies?$select=pluginassemblyid&$filter=name eq '{ASSEMBLY}'")
    elif assembly["content"] != content:
        dv.request("PATCH", f"pluginassemblies({assembly['pluginassemblyid']})", {"content": content,
                   "version": ASSEMBLY_VERSION}, solution=patch)
    assembly_id = assembly["pluginassemblyid"]

    plugin_type = dv.first(f"plugintypes?$select=plugintypeid&$filter=typename eq '{PLUGIN_TYPE}'")
    if not plugin_type:
        dv.request("POST", "plugintypes", {
            "typename": PLUGIN_TYPE, "name": PLUGIN_TYPE, "friendlyname": "AutoNumbering",
            "description": "Numbers campaigns, campaign channels and advertisements.",
            "pluginassemblyid@odata.bind": f"/pluginassemblies({assembly_id})"}, solution=patch, idempotent=False)
        plugin_type = dv.first(f"plugintypes?$select=plugintypeid&$filter=typename eq '{PLUGIN_TYPE}'")

    step_ids = []
    for name, message, table, filtering in STEPS:
        step = dv.first(f"sdkmessageprocessingsteps?$select=sdkmessageprocessingstepid&$filter=name eq '{name}'")
        if not step:
            message_id = dv.first(f"sdkmessages?$select=sdkmessageid&$filter=name eq '{message}'")["sdkmessageid"]
            filter_id = dv.first(f"sdkmessagefilters?$select=sdkmessagefilterid&$filter=primaryobjecttypecode eq "
                                 f"'{table}' and _sdkmessageid_value eq {message_id}")["sdkmessagefilterid"]
            body = {"name": name, "stage": 20, "mode": 0, "rank": 1, "supporteddeployment": 0,
                    "asyncautodelete": False, "description": name,
                    "eventhandler_plugintype@odata.bind": f"/plugintypes({plugin_type['plugintypeid']})",
                    "sdkmessageid@odata.bind": f"/sdkmessages({message_id})",
                    "sdkmessagefilterid@odata.bind": f"/sdkmessagefilters({filter_id})"}
            if filtering:
                body["filteringattributes"] = filtering
            dv.request("POST", "sdkmessageprocessingsteps", body, solution=patch, idempotent=False)
            step = dv.first(f"sdkmessageprocessingsteps?$select=sdkmessageprocessingstepid&$filter=name eq '{name}'")
            print(f"  registered step {name}")
        step_ids.append(step["sdkmessageprocessingstepid"])
    return assembly_id, step_ids


# ---------------------------------------------------------------------------------------------------------------
# App

def deploy_app(dv, patch, apply):
    app = dv.first(f"appmodules?$select=appmoduleid,name&$filter=uniquename eq '{APP}'")
    sitemap = dv.first(f"sitemaps?$select=sitemapid,sitemapxml&$filter=sitemapnameunique eq '{APP}'")
    xml = sitemap["sitemapxml"]
    has_group = 'Id="group_settings"' in xml
    print(f"site map: Settings group {'exists' if has_group else 'add at the end of the General area'}")
    meta = dv.first(f"EntityDefinitions?$select=MetadataId&$filter=LogicalName eq '{SETTINGS}'")
    if not apply or not meta:
        return sitemap["sitemapid"]
    if not has_group:
        group = ('<Group Id="group_settings" ResourceId="SitemapDesigner.NewGroup" IsProfile="false" '
                 'ToolTipResourseId="SitemapDesigner.Unknown"><Titles><Title LCID="1033" Title="Settings" />'
                 '<Title LCID="1025" Title="الإعدادات" /></Titles>'
                 f'<SubArea Id="subarea_autonumbersetting" Entity="{SETTINGS}" '
                 'Client="All,Outlook,OutlookLaptopClient,OutlookWorkstationClient,Web" AvailableOffline="true" '
                 'PassParams="false" Sku="All,OnPremise,Live,SPLA" /></Group>')
        start = xml.find(GENERAL_AREA)
        end = xml.find("</Area>", start)
        if start < 0 or end < 0:
            raise SystemExit("General area not found in the site map")
        xml = xml[:end] + group + xml[end:]
        dv.request("PATCH", f"sitemaps({sitemap['sitemapid']})", {"sitemapxml": xml}, solution=patch)
        print("  added")
    dv.request("POST", "AddAppComponents", idempotent=True, body={"AppId": app["appmoduleid"], "Components": [
        {"@odata.type": "Microsoft.Dynamics.CRM.entity", "entityid": meta["MetadataId"]}]})
    print(f"  table added to app '{app['name']}'")
    return sitemap["sitemapid"]


# ---------------------------------------------------------------------------------------------------------------

def deploy_components(dv, patch, choice_id, form_ids, script_ids, assembly_id, step_ids, sitemap_id):
    """Adds the changed existing components to the patch. New ones were created in it already; adding is a no-op."""
    campaign_attrs = attributes(dv, CAMPAIGN)
    entity_ids = {t: dv.first(f"EntityDefinitions?$select=MetadataId&$filter=LogicalName eq '{t}'")["MetadataId"]
                  for t in (CAMPAIGN, ADVERTISEMENT, SETTINGS)}
    add_component(dv, patch, ENTITY, entity_ids[SETTINGS], subcomponents=True)
    add_component(dv, patch, ENTITY, entity_ids[CAMPAIGN])
    add_component(dv, patch, ENTITY, entity_ids[ADVERTISEMENT])
    for name, _ in campaign_columns():
        add_component(dv, patch, ATTRIBUTE, campaign_attrs[name])
    for name in CHANGED_CAMPAIGN_COLUMNS:
        add_component(dv, patch, ATTRIBUTE, campaign_attrs[name])
    add_component(dv, patch, OPTIONSET, choice_id)
    for form_id in form_ids:
        add_component(dv, patch, FORM, form_id)
    for script_id in script_ids:
        add_component(dv, patch, WEBRESOURCE, script_id)
    if assembly_id:
        add_component(dv, patch, PLUGIN_ASSEMBLY, assembly_id)
    for step_id in step_ids:
        add_component(dv, patch, PLUGIN_STEP, step_id)
    add_component(dv, patch, SITEMAP, sitemap_id)
    print(f"patch components: added to {patch}")


def publish(dv, sitemap_id):
    app = dv.first(f"appmodules?$select=appmoduleid&$filter=uniquename eq '{APP}'")
    entities = "".join(f"<entity>{t}</entity>" for t in (CAMPAIGN, ADVERTISEMENT, SETTINGS))
    scripts = ""
    for name in SCRIPTS:
        wr = dv.first(f"webresourceset?$select=webresourceid&$filter=name eq '{name}'")
        scripts += f"<webresource>{wr['webresourceid']}</webresource>"
    dv.request("POST", "PublishXml", idempotent=True, body={"ParameterXml":
               f"<importexportxml><entities>{entities}</entities><optionsets><optionset>{CHOICE}</optionset>"
               f"</optionsets><webresources>{scripts}</webresources><sitemaps><sitemap>{sitemap_id}</sitemap>"
               f"</sitemaps><appmodules><appmodule>{app['appmoduleid']}</appmodule></appmodules></importexportxml>"})
    print("published")


def main(apply):
    dv = Dataverse()
    patch = deploy_patch(dv, apply)
    deploy_settings_table(dv, patch, apply)
    if apply:
        dv.request("POST", "PublishXml", idempotent=True, body={"ParameterXml":
                   f"<importexportxml><entities><entity>{SETTINGS}</entity></entities></importexportxml>"})
    deploy_columns(dv, patch, CAMPAIGN, campaign_columns(), apply)
    deploy_campaign_name(dv, patch, apply)
    choice_id = deploy_choice(dv, patch, apply)
    if apply:
        publish_entities = "".join(f"<entity>{t}</entity>" for t in (CAMPAIGN, SETTINGS))
        dv.request("POST", "PublishXml", idempotent=True, body={"ParameterXml":
                   f"<importexportxml><entities>{publish_entities}</entities></importexportxml>"})
    form_ids = deploy_forms(dv, patch, apply)
    deploy_settings_ui(dv, patch, apply)
    script_ids = deploy_scripts(dv, patch, apply)
    assembly_id, step_ids = deploy_plugin(dv, patch, apply)
    sitemap_id = deploy_app(dv, patch, apply)
    if apply:
        deploy_components(dv, patch, choice_id, form_ids, script_ids, assembly_id, step_ids, sitemap_id)
        publish(dv, sitemap_id)


if __name__ == "__main__":
    main("--apply" in sys.argv)
