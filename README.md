# carta-mcp

An MCP server for the [Carta](https://carta.com) equity management platform, built with the [dedalus_mcp](https://docs.dedaluslabs.ai/dmcp) framework. Authentication is handled by **DAuth** (Dedalus Auth).

Carta is the platform companies use to manage cap tables, valuations, equity plans, and fund administration. This server exposes 32 read-only tools covering the full Carta API v1alpha1 surface — investor data, issuer data, portfolios, compensation benchmarks, and more — so any MCP-compatible client (Claude, GPT, Cursor, etc.) can query Carta programmatically.

## Why DAuth?

Carta handles sensitive financial data — cap tables, valuations, equity holdings, and stakeholder PII. Passing raw API keys through an MCP server is a non-starter for this kind of information.

[DAuth](https://www.dedaluslabs.ai/blog/dedalus-auth-launch) (Dedalus Auth) is a **zero-trust**, **host-blind** authentication layer built into the `dedalus_mcp` SDK. Credentials are encrypted client-side, decrypted only for milliseconds inside a hardware-secured enclave to make the API call, then zeroed from memory. Your MCP server never sees the raw secret — it only holds an opaque connection handle. This makes DAuth the right fit for a finance-facing server where credential security is critical.

## Project Structure

```
carta-mcp/
├── src/
│   ├── main.py      # Server entry point and DAuth connection config
│   ├── tools.py     # 32 Carta API tools + rate limiter
│   └── client.py    # Test client for local debugging
├── pyproject.toml   # Dependencies and build config
├── .env             # Carta credentials (not committed)
└── README.md
```

## Prerequisites

1. A [Carta Developer Portal](https://developers.app.carta.com) account with an app configured.
2. Your app's **Client ID** and **Client Secret**.
3. An OAuth **access token** obtained via the [Authorization Code Flow](https://docs.carta.com/carta/docs/authorization-code-flow) or [Client Credentials Flow](https://docs.carta.com/carta/docs/client-credentials-flow).
4. A **Dedalus API key** from the [Dedalus dashboard](https://www.dedaluslabs.ai/dashboard/api-keys).

## Setup

### 1. Install dependencies

```bash
pip install -e .
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```
CARTA_CLIENT_ID=<your-client-id>
CARTA_CLIENT_SECRET=<your-client-secret>
CARTA_ACCESS_TOKEN=<your-bearer-token>

DEDALUS_API_KEY=<your-dedalus-api-key>
DEDALUS_AS_URL=https://as.dedaluslabs.ai
```

### 3. Obtain a Bearer token

The Carta API uses OAuth 2.0. You need a Bearer token to authenticate requests.

**Client Credentials Flow** (your own account data):

```bash
curl -X POST https://login.app.carta.com/o/access_token/ \
  -H "Authorization: Basic $(echo -n '<client_id>:<client_secret>' | base64)" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=CLIENT_CREDENTIALS&scope=read_issuer_info read_investor_firms read_portfolio_info"
```

**Authorization Code Flow** (third-party data): redirect users to `https://login.app.carta.com/o/authorize/` and exchange the code at `/o/access_token/`. See the [full guide](https://docs.carta.com/carta/docs/authorization-code-flow).

Access tokens expire after **1 hour**. Store the resulting `access_token` as `CARTA_ACCESS_TOKEN` in your `.env` or DAuth session.

### 4. Start the server

```bash
python -m src.main
```

The server starts on `http://127.0.0.1:8080/mcp`.

### 5. Test with the client

```bash
python -m src.client
```

## Available Tools

All tools are read-only and support pagination via `page_size` (default 25, max 50) and `page_token` parameters.

### User

| Tool | Description |
|------|-------------|
| `get_current_user` | Get the authenticated user's profile (id, name, email) |

### Investor

| Tool | Description |
|------|-------------|
| `list_investor_firms` | List investment firms |
| `list_investor_funds` | List funds belonging to a firm |
| `list_investor_investments` | List portfolio-company investments for a fund |
| `list_investor_securities` | List securities held by a fund |
| `list_investor_partners` | List limited partners in a fund |
| `list_investor_cash_balances` | List cash balances for a fund |
| `get_investor_fund_performance` | Get fund performance metrics |
| `get_investor_capitalization_table` | Get cap table summary for an investment |
| `get_investor_stakeholder_capitalization_table` | Get stakeholder-level cap table for an investment |

### Issuer

| Tool | Description |
|------|-------------|
| `list_issuers` | List issuers (companies) |
| `list_issuer_stakeholders` | List equity holders for an issuer |
| `list_issuer_share_classes` | List share classes (supports `as_of_date`) |
| `list_issuer_valuations` | List 409A valuations |
| `list_issuer_option_grants` | List option grant securities |
| `list_issuer_stock_certificates` | List stock certificates |
| `list_issuer_warrants` | List warrants |
| `list_issuer_convertible_notes` | List convertible notes |
| `list_issuer_draft_option_grants` | List draft (unissued) option grants |
| `list_issuer_vesting_schedules` | List vesting schedule templates |
| `list_issuer_interests` | List interests for LLC issuers |
| `get_issuer_cap_table_summary` | Get aggregated cap table summary (supports `as_of_date`) |
| `get_issuer_stakeholder_cap_table` | Get stakeholder-level cap table (supports `as_of_date`) |

### Portfolio

| Tool | Description |
|------|-------------|
| `list_portfolios` | List shareholder portfolios |
| `list_portfolio_securities` | List holdings in a portfolio |
| `list_portfolio_transactions` | List security transactions |
| `list_portfolio_issuer_valuations` | List issuer valuations within a portfolio |
| `list_portfolio_fund_investment_documents` | List fund investment documents |

### Other

| Tool | Description |
|------|-------------|
| `list_corporations` | List corporations and their details |
| `get_compensation_benchmarks` | Get compensation benchmarking data (Carta Total Comp) |
| `list_open_cap_tables` | List open cap tables |
| `list_draft_issuers` | List draft issuers (Carta Launch) |

## Rate Limiting

Carta enforces **10 requests/second** and **300 requests/minute** ([docs](https://docs.carta.com/carta/docs/rate-limiting)). A sliding-window rate limiter is built into the server and automatically throttles outbound requests so you never hit a `429 Too Many Requests` error. No configuration needed.

## OAuth Scopes

This server's tools map to the following [Carta OAuth scopes](https://docs.carta.com/carta/docs/scopes). Make sure your app has the scopes enabled for the tools you intend to use.

| Scope | Tools |
|-------|-------|
| `read_user_info` | `get_current_user` |
| `read_investor_firms` | `list_investor_firms` |
| `read_investor_funds` | `list_investor_funds` |
| `read_investor_investments` | `list_investor_investments` |
| `read_investor_securities` | `list_investor_securities` |
| `read_investor_partners` | `list_investor_partners` |
| `read_investor_cashbalances` | `list_investor_cash_balances` |
| `read_investor_fundperformance` | `get_investor_fund_performance` |
| `read_investor_capitalizationtables` | `get_investor_capitalization_table` |
| `read_investor_stakeholdercapitalizationtable` | `get_investor_stakeholder_capitalization_table` |
| `read_issuer_info` | `list_issuers` |
| `read_issuer_stakeholders` | `list_issuer_stakeholders` |
| `read_issuer_shareclasses` | `list_issuer_share_classes` |
| `read_issuer_valuations` | `list_issuer_valuations` |
| `read_issuer_securities` | `list_issuer_option_grants`, `list_issuer_stock_certificates`, `list_issuer_warrants`, `list_issuer_convertible_notes` |
| `read_issuer_draftsecurities` | `list_issuer_draft_option_grants` |
| `read_issuer_securitiestemplates` | `list_issuer_vesting_schedules` |
| `read_issuer_interests` | `list_issuer_interests` |
| `read_issuer_capitalizationtablesummary` | `get_issuer_cap_table_summary` |
| `read_issuer_stakeholdercapitalizationtable` | `get_issuer_stakeholder_cap_table` |
| `read_portfolio_info` | `list_portfolios` |
| `read_portfolio_securities` | `list_portfolio_securities` |
| `read_portfolio_transactions` | `list_portfolio_transactions` |
| `read_portfolio_issuervaluations` | `list_portfolio_issuer_valuations` |
| `read_portfolio_fundinvestmentdocuments` | `list_portfolio_fund_investment_documents` |
| `read_corporation_info` | `list_corporations` |
| `read_compensation_benchmarks` | `get_compensation_benchmarks` |
| `read_opencaptables` | `list_open_cap_tables` |
| `read_draftissuers` | `list_draft_issuers` |

## Deploy

Upload your server to [dedaluslabs.ai](https://dedaluslabs.ai). DAuth handles credential security automatically in production. Make sure all environment variables are configured in the deployment environment.

## Resources

- [Carta API Quickstart Guide](https://docs.carta.com/carta/docs/quickstart-guide)
- [Carta OAuth Scopes Reference](https://docs.carta.com/carta/docs/scopes)
- [Carta Rate Limits](https://docs.carta.com/carta/docs/rate-limiting)
- [Authorization Code Flow](https://docs.carta.com/carta/docs/authorization-code-flow)
- [Client Credentials Flow](https://docs.carta.com/carta/docs/client-credentials-flow)
- [Dedalus MCP Documentation](https://docs.dedaluslabs.ai/dmcp)
