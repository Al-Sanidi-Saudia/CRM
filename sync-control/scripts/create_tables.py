import sys; sys.path.insert(0, sys.argv[1])
import dv

def L(t): return {"@odata.type":"Microsoft.Dynamics.CRM.Label","LocalizedLabels":[{"@odata.type":"Microsoft.Dynamics.CRM.LocalizedLabel","Label":t,"LanguageCode":1033}]}
def req(level='None'): return {"Value":level,"CanBeChanged":True,"ManagedPropertyLogicalName":"canmodifyrequirementlevelsettings"}
def text(schema, label, maxlen=200, desc=''):
    return {"@odata.type":"Microsoft.Dynamics.CRM.StringAttributeMetadata","SchemaName":schema,"DisplayName":L(label),"Description":L(desc),"RequiredLevel":req(),"MaxLength":maxlen,"FormatName":{"Value":"Text"}}
def memo(schema,label,desc=''):
    return {"@odata.type":"Microsoft.Dynamics.CRM.MemoAttributeMetadata","SchemaName":schema,"DisplayName":L(label),"Description":L(desc),"RequiredLevel":req(),"MaxLength":100000,"Format":"TextArea"}
def intg(schema,label,desc=''):
    return {"@odata.type":"Microsoft.Dynamics.CRM.IntegerAttributeMetadata","SchemaName":schema,"DisplayName":L(label),"Description":L(desc),"RequiredLevel":req(),"MinValue":0,"MaxValue":1000,"Format":"None"}
def boolean(schema,label,desc=''):
    return {"@odata.type":"Microsoft.Dynamics.CRM.BooleanAttributeMetadata","SchemaName":schema,"DisplayName":L(label),"Description":L(desc),"RequiredLevel":req(),"DefaultValue":False,
      "OptionSet":{"@odata.type":"Microsoft.Dynamics.CRM.BooleanOptionSetMetadata","TrueOption":{"Value":1,"Label":L("Yes")},"FalseOption":{"Value":0,"Label":L("No")}}}
def dt(schema,label,desc=''):
    return {"@odata.type":"Microsoft.Dynamics.CRM.DateTimeAttributeMetadata","SchemaName":schema,"DisplayName":L(label),"Description":L(desc),"RequiredLevel":req(),"Format":"DateAndTime","DateTimeBehavior":{"Value":"UserLocal"}}
def choice(schema,label,opts,desc='',default=None):
    a={"@odata.type":"Microsoft.Dynamics.CRM.PicklistAttributeMetadata","SchemaName":schema,"DisplayName":L(label),"Description":L(desc),"RequiredLevel":req(),
       "OptionSet":{"@odata.type":"Microsoft.Dynamics.CRM.OptionSetMetadata","IsGlobal":False,"OptionSetType":"Picklist","Options":[{"Value":v,"Label":L(t)} for v,t in opts]}}
    if default is not None: a["DefaultFormValue"]=default
    return a
def primary(label):
    a=text("sanidi_Name",label,200); a["IsPrimaryName"]=True; a["RequiredLevel"]=req("ApplicationRequired"); return a
def table(schema,disp,plural,desc,ownership,attrs):
    return {"@odata.type":"Microsoft.Dynamics.CRM.EntityMetadata","SchemaName":schema,"DisplayName":L(disp),"DisplayCollectionName":L(plural),"Description":L(desc),
            "OwnershipType":ownership,"IsActivity":False,"HasNotes":False,"HasActivities":False,"Attributes":attrs}

plat=table("sanidi_IntegrationPlatform","Integration Platform","Integration Platforms",
  "Ad platforms shown on the Sync Control page, with the flows behind their Sync Data and Sync Insights buttons.","OrganizationOwned",[
  primary("Name"),
  text("sanidi_PlatformKey","Platform Key",50,"Short key used by the page and the dispatcher flow (meta, snap, google, tiktok)."),
  intg("sanidi_SortOrder","Sort Order","Order of the card on the page."),
  boolean("sanidi_IsConfigured","Set Up","Yes when the platform's flows exist; No shows the card as Not set up yet."),
  memo("sanidi_DataFlows","Data Flows","JSON list of the data sync flows in run order: [{\"name\":\"...\",\"id\":\"<workflow id>\"}]. The first one is started by Sync Data."),
  text("sanidi_InsightsFlowName","Insights Flow Name",200),
  text("sanidi_InsightsFlowId","Insights Flow Id",100,"Workflow id of the flow started by Sync Insights."),
])
st,b,_=dv.call('POST','EntityDefinitions',plat); print('platform',st, b if st>=300 else '')

reqt=table("sanidi_IntegrationSyncRequest","Integration Sync Request","Integration Sync Requests",
  "One row per Sync Data or Sync Insights button press on the Sync Control page. The dispatcher flow runs the matching flow and records the outcome.","UserOwned",[
  primary("Name"),
  choice("sanidi_SyncType","Sync Type",[(100000000,"Data"),(100000001,"Insights")]),
  choice("sanidi_Status","Status",[(100000000,"Requested"),(100000001,"Running"),(100000002,"Succeeded"),(100000003,"Failed")],default=100000000),
  dt("sanidi_StartedOn","Started On"),
  dt("sanidi_CompletedOn","Completed On"),
  memo("sanidi_ErrorMessage","Error Message"),
])
st,b,_=dv.call('POST','EntityDefinitions',reqt); print('request',st, b if st>=300 else '')

lk={"SchemaName":"sanidi_IntegrationPlatform_SyncRequest","@odata.type":"Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
    "ReferencedEntity":"sanidi_integrationplatform","ReferencingEntity":"sanidi_integrationsyncrequest",
    "CascadeConfiguration":{"Assign":"NoCascade","Delete":"Restrict","Merge":"NoCascade","Reparent":"NoCascade","Share":"NoCascade","Unshare":"NoCascade"},
    "Lookup":{"@odata.type":"Microsoft.Dynamics.CRM.LookupAttributeMetadata","SchemaName":"sanidi_Platform","DisplayName":L("Platform"),"RequiredLevel":req("ApplicationRequired")}}
st,b,_=dv.call('POST','RelationshipDefinitions',lk); print('lookup',st, b if st>=300 else '')
