# Snap Advertisement table (`sanidi_SnapAdvertisement`) and Get Snap Advertisements flow

Stores Snapchat ads from the [Snapchat Marketing API](https://developers.snap.com/marketing-api/Ads-API/ads).

- Entity set `sanidi_snapadvertisements`; primary name `sanidi_adname`.
- Alternate key `sanidi_snapadvertisement_adidkey` on `sanidi_adid`.
- Lookup **Snap Ad Squad** (`sanidi_snapadsquad`), relationship
  `sanidi_snapadvertisement_snapadsquad_sanidi_snapadsquad`; the Snap Ad Squad form lists an ad squad's ads on
  its Related tab.
- Choices use Snap's values as labels, numbered from 1. Delivery Status uses the shared choice
  `sanidi_snapaddeliverystatus`. Review Status Reasons are stored one per line; tracking URLs keep Snap's JSON.

**Get Snap Advertisements** runs whenever a Snap Ad Squad row is added or modified. It reads that ad squad's ads
from the Snap connector, then updates the matching row by Ad ID or adds a new one, linked to the ad squad. Ads that
disappear from Snap are kept.

See `../README.md` for building and importing.
