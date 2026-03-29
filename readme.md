# Investa Morning Dashboard

Internal market dashboard for Investa Solutions SA. Displays EOD prices across equities, rates, FX, commodities, credit ETFs, and the private markets portfolio.

## Live dashboard

[investa-dashboard link here]

## What it contains

- **Prices** — S&P 500, Nasdaq, DAX, FTSE, Nikkei, SMI, Hang Seng, rates, FX, gold, oil, bitcoin, credit ETFs
- **News & Commentary** — curated market commentary
- **Portfolio** — 24 private market positions with latest valuations and news

## Auto-refresh

Prices are refreshed automatically every weekday at 18:00 CET via GitHub Actions + Anthropic API web search. Each refresh commits a new version of `index.html` with updated data.

## Setup

1. Add `ANTHROPIC_API_KEY` to repository secrets (Settings → Secrets → Actions)
2. GitHub Pages enabled on `main` branch root
3. Workflow file: `.github/workflows/refresh.yml`

## Manual refresh

Go to **Actions → EOD Price Refresh → Run workflow** to trigger outside the schedule.
