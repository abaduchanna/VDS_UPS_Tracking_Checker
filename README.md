# verge-ups-tracking-checker

Standalone Verge Desk Solutions Tkinter tool: `verge_ups_tracking_checker.pyw` — UPS package tracking
verification via Selenium/Edge.

Fixed: the "Progress & Results" log panel was cramped (window capped at
800px wide, 50/50 split with the input panel). Window widened to 1150px
max and the panel split rebalanced 40/60 in favor of the log.

Builds a Windows EXE automatically via GitHub Actions on every push to
`main` (uploaded directly to the repo's Releases page — no Actions
storage used), and via CircleCI once the repo is connected at circleci.com.
