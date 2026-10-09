# Snap Ad Squad table (`sanidi_SnapAdSquad`) and Get Snap Ad Squads flow

Stores Snapchat ad squads from the [Snapchat Marketing API](https://developers.snap.com/marketing-api/Ads-API/ad-squads).

- Entity set `sanidi_snapadsquads`; primary name `sanidi_adsquadname`.
- Alternate key `sanidi_snapadsquad_adsquadidkey` on `sanidi_adsquadid`.
- Lookup **Snap Campaign** (`sanidi_snapcampaign`), relationship `sanidi_snapadsquad_snapcampaign_sanidi_snapcampaign`;
  the Snap Campaign form lists a campaign's ad squads on its Related tab, and this table's form lists the ad
  squad's Snap Advertisements on its own Related tab.
- Choices use Snap's values as labels, numbered from 1. Multi-select columns use the shared choices
  `sanidi_snapadsquaddeliverystatus`, `sanidi_snapplatform`, `sanidi_snapplacementposition`,
  `sanidi_snapcontenttype` (included and excluded content types) and `sanidi_snapmeasurementprovider`.
- Money and ROAS columns hold Snap's micro values divided by 1,000,000. Targeting, Cap and Exclusion Config,
  Ad Scheduling Config and Event Sources keep Snap's JSON as text.

**Get Snap Ad Squads** runs whenever a Snap Campaign row is added or modified (so after every Get Snap Campaigns
run, once per campaign). It reads that campaign's ad squads from the Snap connector, then updates the matching
row by Ad Squad ID or adds a new one, linked to the campaign. Ad squads that disappear from Snap are kept.

See `../README.md` for building and importing.
