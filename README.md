# UPS Tracking Checker (VDS)

VDS Desk Solutions edition: batch UPS tracking-number lookup via Edge
automation with Excel in/out. Windows EXE via GitHub Actions on push.

## VDS UPS Tracking apps (this repo)

| App | What it does | Log CSV columns |
| --- | --- | --- |
| `VDS_UPS_Tracking_Checker.py` | Batch UPS tracking via headless Edge — Delivered / Not delivered | A = `Tracking`, B = `Result` |
| `VDS_UPS_Tracking_Detailed.py` | Same flow, DETAILED status per package — Label Created / On the Way / Out for Delivery / Delivered / Delivery Attempted / Exception / Returned to Sender, etc. | A = `Date`, B = `Status`, C = `Tracking` |

Both apps build automatically via GitHub Actions (`.github/workflows/build.yml`) and ship as EXEs in every `build-*` release.
