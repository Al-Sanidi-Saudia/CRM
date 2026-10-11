# Sync Control

A page in the **AlSanidi | Marketing** app (Integration area → **Sync Control** group) that shows the
latest run of each ad platform's data and insights sync. System Administrators can also start a sync from it.
Everything lives in the **AlSanidi | Marketing** solution (`AlSanidiMarketing`, prefix `sanidi`).

## How it works

```
Sync Control page ──creates──▶ Integration Sync Request (row)
                                      │ (row added)
                                      ▼
                     Sync Control - Run Sync Request (flow)
                                      │ runs as a child flow
                                      ▼
            Get <Platform> Campaigns  /  Get <Platform> Insights
                                      │ (Dataverse triggers)
                                      ▼
                  ad sets / ad squads / ad groups → ads flows
```

- **Status** on the page comes from the built-in flow run history (`flowrun` table, kept 28 days):
  the latest run of every flow listed for the platform, plus the latest sync request.
- **Data** = the campaigns flow and the flows that run automatically after it. **Insights** = the insights flow.
- After a button press the part shows *Running* with the new date. While any sync is running, the page checks
  its request every 5 seconds and, once it has finished, refreshes itself exactly as **Refresh** does.
- **Run history lag**: run history can record a run several minutes after it finishes. Once a data sync's request
  has finished, the flow the button started shows the request's result straight away and the later flows show
  "Updating…"; the page checks run history every 15 seconds (up to 10 minutes) and refreshes once more when it
  has this sync's runs. A later flow that failed in the same sync turns the section to Failed with its error.
- **Usual duration**: the median duration of the last 5 successful runs of the flow the button starts, shown on the
  card and in the confirmation.
- While one of a platform's syncs runs, its other button is disabled (a Data and an Insights sync on the same
  campaigns at the same time made Meta Insights fail).
- **Last success** badge: time since the last successful run (flow run history or a succeeded request), measured
  when the page loads. Grey up to 12 hours, yellow over 12 hours, red over 1 day.
- **Notifications**: when a sync started from the page finishes, the dispatcher flow sends an in-app notification
  (the app's bell, with a pop-up) to the person who pressed the button, with the error message when it failed.
  In-app notifications are switched on for the app by the app setting `sanidi_AlSanidiMarketing_InAppNotification`.

## Components

| Component | Name |
|---|---|
| Table | `sanidi_integrationplatform` (Integration Platform): one row per platform, with its flows |
| Table | `sanidi_integrationsyncrequest` (Integration Sync Request): one row per button press, with status and error |
| Flow | **Sync Control - Run Sync Request**: runs the matching flow (no retries), writes Running / Succeeded / Failed back, notifies the requester |
| App setting | In-app notifications on for AlSanidi \| Marketing |
| Generative page | **Sync Control** (`sync-control.tsx`) |

The six manual flows (Get Meta/Snap/Google Ads Campaigns and Insights) end with a
**Respond to a Power App or flow** step and use stored ("embedded") connections. Both are required
for a flow to be run as a child flow.

## Adding a platform (for example TikTok)

1. Build its manual campaigns flow and insights flow in the solution. Give each a final
   **Respond to a Power App or flow** step and use stored connections, not "Provided by run-only user".
2. Update the platform's row in **Integration Platform**: set **Set Up** to Yes, fill in **Data Flows**
   (JSON: `[{"name":"...","id":"<workflow id>"}, ...]` in run order) and the insights flow name and ID.
3. In **Sync Control - Run Sync Request**, add two cases to the *Run the matching flow* switch:
   `<key>-100000000` (data) and `<key>-100000001` (insights), each with a *Run a Child Flow* action.
   A child flow can't be chosen dynamically, so the dispatcher flow needs these two cases.

The page needs no change.

## Who can start a sync

The buttons appear for the roles listed in `SYNC_ROLES` at the top of `page/sync-control.tsx`
(System Administrator today). To add a role, add it there, redeploy the page, and give that role
**Create** and **Read** on Integration Sync Request. Any role that should see the page needs **Read** on
Integration Platform, Integration Sync Request and Flow Run, and access to the app.

## Files

- `page/`: page source (`sync-control.tsx`) and the generated `RuntimeTypes.ts`.
  Redeploy with `pac model genpage upload --page-id fbb9c7b0-bb45-4583-997d-6b32b0e5d29b ...`.
- `scripts/update_dispatcher.py`: the current dispatcher flow definition. After updating the flow this way,
  turn it off and on in Power Automate (by someone who can use its Dataverse connection) so its trigger re-registers.
- `scripts/`: the scripts used to create the tables, the platform rows and the dispatcher flow
  through the Dataverse Web API (`DATAVERSE_*` environment variables, same as `scripts/dataverse-mcp.sh`).
  Flows keep their IDs when the solution is imported, so the IDs work in other environments too.
  The **Integration Platform rows are data, not solution components**: after importing the solution
  into another environment, add them there (for example with `scripts/seed_platforms.py`).
