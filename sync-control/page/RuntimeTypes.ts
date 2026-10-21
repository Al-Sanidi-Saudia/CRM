// ---------------- Type Definitions which can be imported from ./RuntimeTypes -------------------------
export interface TableRegistrations extends BaseTableRegistrations {
    "flowrun": flowrun,
    "sanidi_integrationplatform": sanidi_integrationplatform,
    "sanidi_integrationsyncrequest": sanidi_integrationsyncrequest,
}
export interface EnumRegistrations extends BaseEnumRegistrations {
    "flowrun-isprimary": flowrun_isprimary,
    "flowrun-modernflowtype": flowrun_modernflowtype,
    "sanidi_integrationplatform-sanidi_connectionactive": sanidi_integrationplatform_sanidi_connectionactive,
    "sanidi_integrationplatform-sanidi_isconfigured": sanidi_integrationplatform_sanidi_isconfigured,
    "sanidi_integrationplatform-statecode": sanidi_integrationplatform_statecode,
    "sanidi_integrationplatform-statuscode": sanidi_integrationplatform_statuscode,
    "sanidi_integrationsyncrequest-sanidi_status": sanidi_integrationsyncrequest_sanidi_status,
    "sanidi_integrationsyncrequest-sanidi_synctype": sanidi_integrationsyncrequest_sanidi_synctype,
    "sanidi_integrationsyncrequest-statecode": sanidi_integrationsyncrequest_statecode,
    "sanidi_integrationsyncrequest-statuscode": sanidi_integrationsyncrequest_statuscode,
}
export type flowrun = TableRow<{
    // Primary Key Column
    readonly flowrunid: string,
    callingproductresourceid: string,
    callingproductrunid: string,
    callingproducttype: string,
    clienttrackingid: string,
    conversationid: string,
    readonly createdbyname: string,
    readonly createdbyyominame: string,
    readonly createdonbehalfbyname: string,
    readonly createdonbehalfbyyominame: string,
    duration: number,
    durationdeprecated: number,
    endtime: Date,
    errorcode: string,
    errormessage: string,
    isprimary: flowrun_isprimary,
    modernflowtype: flowrun_modernflowtype,
    readonly modifiedbyname: string,
    readonly modifiedbyyominame: string,
    readonly modifiedonbehalfbyname: string,
    readonly modifiedonbehalfbyyominame: string,
    name: string,
    readonly owningbusinessunitname: string,
    parentrunid: string,
    partitionid: string,
    resourceid: string,
    starttime: Date,
    status: string,
    triggertype: string,
    ttlinseconds: number,
    // Foreign Key Column
    readonly _workflow_value: `/workflow(${string})`,
    workflowid: string,
    readonly workflowname: string,
}>

export type sanidi_integrationplatform = TableRow<{
    // Primary Key Column
    readonly sanidi_integrationplatformid: string,
    readonly createdbyname: string,
    readonly createdbyyominame: string,
    readonly createdonbehalfbyname: string,
    readonly createdonbehalfbyyominame: string,
    readonly modifiedbyname: string,
    readonly modifiedbyyominame: string,
    readonly modifiedonbehalfbyname: string,
    readonly modifiedonbehalfbyyominame: string,
    // Foreign Key Column
    readonly _organizationid_value: `/organization(${string})`,
    readonly organizationidname: string,
    sanidi_connectionactive: sanidi_integrationplatform_sanidi_connectionactive,
    sanidi_dataflows: string,
    sanidi_insightsflowid: string,
    sanidi_insightsflowname: string,
    sanidi_isconfigured: sanidi_integrationplatform_sanidi_isconfigured,
    sanidi_name: string,
    sanidi_platformkey: string,
    sanidi_sortorder: number,
    statecode: sanidi_integrationplatform_statecode,
    statuscode: sanidi_integrationplatform_statuscode,
}>

export type sanidi_integrationsyncrequest = TableRow<{
    // Primary Key Column
    readonly sanidi_integrationsyncrequestid: string,
    readonly createdbyname: string,
    readonly createdbyyominame: string,
    readonly createdonbehalfbyname: string,
    readonly createdonbehalfbyyominame: string,
    readonly modifiedbyname: string,
    readonly modifiedbyyominame: string,
    readonly modifiedonbehalfbyname: string,
    readonly modifiedonbehalfbyyominame: string,
    readonly owningbusinessunitname: string,
    sanidi_completedon: Date,
    sanidi_errormessage: string,
    sanidi_name: string,
    // Foreign Key Column
    _sanidi_platform_value: `/sanidi_integrationplatform(${string})`,
    readonly sanidi_platformname: string,
    sanidi_startedon: Date,
    sanidi_status: sanidi_integrationsyncrequest_sanidi_status,
    sanidi_synctype: sanidi_integrationsyncrequest_sanidi_synctype,
    statecode: sanidi_integrationsyncrequest_statecode,
    statuscode: sanidi_integrationsyncrequest_statuscode,
}>

const enum flowrun_isprimary {
"true" = 1,
"false" = 0,
}
const enum flowrun_modernflowtype {
"PowerAutomateFlow" = 0,
"CopilotStudioFlow" = 1,
"M365CopilotAgentFlow" = 2,
}
const enum sanidi_integrationplatform_sanidi_connectionactive {
"No" = 0,
"Yes" = 1,
}
const enum sanidi_integrationplatform_sanidi_isconfigured {
"No" = 0,
"Yes" = 1,
}
const enum sanidi_integrationplatform_statecode {
"Active" = 0,
"Inactive" = 1,
}
const enum sanidi_integrationplatform_statuscode {
"Active" = 1,
"Inactive" = 2,
}
const enum sanidi_integrationsyncrequest_sanidi_status {
"Requested" = 100000000,
"Running" = 100000001,
"Succeeded" = 100000002,
"Failed" = 100000003,
}
const enum sanidi_integrationsyncrequest_sanidi_synctype {
"Data" = 100000000,
"Insights" = 100000001,
}
const enum sanidi_integrationsyncrequest_statecode {
"Active" = 0,
"Inactive" = 1,
}
const enum sanidi_integrationsyncrequest_statuscode {
"Active" = 1,
"Inactive" = 2,
}

export interface UxAgentDataApi extends BaseUxAgentDataApi<TableRegistrations, EnumRegistrations> {}

export interface GeneratedComponentProps {
    dataApi: UxAgentDataApi;
}

