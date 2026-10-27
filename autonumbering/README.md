# Marketing Auto Numbering

Automatic numbers for campaigns and advertisements in **AlSanidi | Marketing**:

| Record | Number | When |
|---|---|---|
| Campaign | `MC-2026-01` (prefix, year, counter that restarts at 01 every year; 3 digits after 99) | On create |
| Campaign channel | `MC-2026-01-M` in Meta Number, `-S` Snap, `-T` TikTok, `-G` Google Ads | On create, and when a channel is ticked later. Kept when the channel is unticked. |
| Advertisement | `MC-2026-01-M-01` (campaign channel number + counter per channel in that campaign) | On create. Blocked if the campaign doesn't have the advertisement's channel. |

The numbers are set in real time, inside the save, by a synchronous plug-in. Records created before
27 October 2026 keep their names. If an advertisement is added to an older campaign, the channel number is
built from that campaign's name.

Deployed to **UAT** (`operations-alsenidiuat.crm4.dynamics.com`) and **Production**
(`operations-alsanidi.crm4.dynamics.com`) on 2026-10-27. In Production the managed patch was imported with
`import_patch.py` (no warnings), then `migrate_channels.py --apply` moved campaign C-2026-001 from Instagram to
Meta and removed the 5 old options. See [Deploying to Production](#deploying-to-production) for the steps.

## Where the counters live

| What | Where |
|---|---|
| Prefix `MC`, codes `M` `S` `T` `G`, current year, last campaign number | Table **Auto Numbering Setting** (`sanidi_autonumbersetting`), one row. In the app: General > Settings. |
| Last advertisement number per channel | Hidden columns on the campaign: `sanidi_lastmetaadnumber`, `sanidi_lastsnapadnumber`, `sanidi_lasttiktokadnumber`, `sanidi_lastgoogleadsadnumber` |

Every number is taken while holding a lock on the settings row. Two people saving at the same moment wait for
each other instead of getting the same number (tested with 8 campaigns saved at once). The plug-in creates the
settings row with the defaults on first use if it is missing. Change a code or the prefix on that row and the
next number uses it. Numbers already issued don't change. The plug-in runs as SYSTEM, so users need no
access to the settings table. Only administrators see it unless a role is given access.

## Changes

**Campaign (`sanidi_campaign`)**
- `sanidi_description` Description (multiline, 4,000), under Name on the main and quick create forms.
- `sanidi_metanumber`, `sanidi_snapnumber`, `sanidi_tiktoknumber`, `sanidi_googleadsnumber`: read-only. Each
  is shown above its platform campaign lookup only while its channel is ticked.
- Name is read-only on the forms and no longer required (the plug-in fills it).
- Start Date and End Date are Recommended instead of required.
- Main form layout (changed in UAT on 2026-10-27): General 30% and Social Media Channel 70% in two columns, with
  each channel number beside its platform campaign. The Finance section (Cost) was removed from the body; Cost
  is still in the header. Start Date and End Date appear twice in the General section, as saved.

**Advertisement (`sanidi_advertisement`)**: Name is read-only on the main form.

**Global choice `sanidi_socialmediachannel`** (used by Campaign, Advertisement and Influencer):
Meta (1), Snap (5), TikTok (4), Google Ads (6). Existing data was moved: Facebook/Instagram to Meta,
Google/YouTube to Google Ads, and X, WhatsApp and Other were removed from rows (3 influencers, 4 campaigns and
2 advertisements in UAT). The form scripts `campaign.form.js` and `advertisement.form.js` use the new values.

**Plug-in** `Sanidi.Marketing.Plugins.AutoNumbering` (sandbox, PreOperation, synchronous):
Create of Campaign; Update of Campaign filtered on `sanidi_socialmediachannel`; Create of Advertisement. No
existing flow creates campaigns or advertisements, and no flow is triggered by the columns the plug-in writes.

## Packaging: a patch, not a new version

Production runs **AlSanidi | Marketing 1.0.0 managed**. Everything above is in a **patch** of that solution,
**AlSanidi | Marketing | Auto Numbering** (`AlSanidiMarketing_Patch_facc1073`, 1.0.1.0), exported as managed.
It holds 26 components:

| Type | Components |
|---|---|
| Tables | Auto Numbering Setting (complete); Campaign and Advertisement with **only** the changed parts |
| Columns | Campaign: 9 new columns + Name, Start Date, End Date (required level) |
| Forms | Campaign Information and Quick Create, Advertisement Information |
| Other | Channel choice, 2 form scripts, site map, plug-in assembly and 3 steps |

Why a patch:
- **It doesn't touch what is running.** The 28 flows, connection references, environment variables,
  connectors, Copilot agent and the other 19 tables aren't in the package, so the import can't turn flows
  off, reset connections or overwrite settings. A full 1.1.0 upgrade would re-import all 141 components.
- **It layers on top of 1.0.0** and can be removed on its own: deleting the patch in Production returns the
  forms, scripts and choice labels to 1.0.0 and removes the new table, columns and plug-in.
- **Same publisher and solution**, so there is no second owner of the campaign forms.

Limits:
- A patch can add and change, not delete. Production keeps the 5 old channel options after the import, and
  `migrate_channels.py` removes them (step 3 below). They leave the solution for good at the next roll-up.
- **In UAT, AlSanidi | Marketing is now locked** while the patch exists. Put new Marketing changes in this patch
  (or a new one, 1.0.2.0). When the next full release is due, roll the patches up with *Clone Solution*
  (AlSanidi | Marketing 1.1.0.0) and import that into Production as an **Upgrade**.

## Deploying to Production

Production: `https://operations-alsanidi.crm4.dynamics.com`. Do it outside working hours. Import with the
same service account as 1.0.0 (# CRM-Claude).

1. **Check** that Solutions in Production shows *AlSanidi | Marketing* 1.0.0 managed, and that no Microsoft
   update is running (the 1.0.0 import was rolled back once because of one).
2. **Import** `solution/AlSanidiMarketing_AutoNumbering_1_0_1_0_managed.zip` (Solutions > Import). Keep
   *Enable plug-in steps and flows included in the solution* ticked. The page says it is a patch for
   AlSanidi | Marketing.
3. **Move channel data and remove the old options** in Production:
   ```
   DATAVERSE_URL=https://operations-alsanidi.crm4.dynamics.com python3 migrate_channels.py           # look first
   DATAVERSE_URL=https://operations-alsanidi.crm4.dynamics.com python3 migrate_channels.py --apply
   ```
   This needs credentials for the Production app user (DATAVERSE_TENANT_ID / CLIENT_ID / CLIENT_SECRET). The rows
   are updated with custom plug-ins and flows bypassed.
4. **Check** in the app: the Campaign form shows Description, Name is read-only, and the channels are Meta,
   Snap, TikTok, Google Ads. General > Settings opens Auto Numbering Settings. The row appears after the first
   campaign is saved, or create it by hand with MC, M, S, T, G.
5. **Don't test-save campaigns in Production** unless you then put *Last Campaign Number* back. Each save
   takes a number.
6. Optional: give *AlSanidi | Marketing | Manager* Read/Write on Auto Numbering Setting so managers can change
   the codes (the role isn't in the solution, so this is per environment).

Rollback: delete *AlSanidi | Marketing | Auto Numbering* in Production. Records keep the names they were given,
and the channel data moved in step 3 stays moved.

## Files

| Path | What it is |
|---|---|
| `plugin/` | The plug-in (C#, .NET Framework 4.6.2). Build: `dotnet build -c Release`. `Sanidi.Marketing.Plugins.snk` signs it. Raise `<Version>` and `ASSEMBLY_VERSION` in `deploy.py` together. |
| `deploy.py` | Builds everything in UAT inside the patch. Dry run by default, `--apply` to make changes. Safe to re-run. |
| `migrate_channels.py` | Moves channel data to the 4 options and deletes the others. Dry run by default. Targets `DATAVERSE_URL`. |
| `test_numbering.py` | End-to-end test in UAT: numbers, channel numbers, blocking, year restart, 8 parallel saves, prefix/code change, 3-digit counter. Deletes its rows and restores the counters. |
| `import_patch.py` | Imports the managed patch into `DATAVERSE_URL` and waits for the result. |
| `export.py` | Exports the patch, managed and unmanaged, to `solution/`. |
| `solution/` | The exported patch. `_managed.zip` is the one for Production. |
