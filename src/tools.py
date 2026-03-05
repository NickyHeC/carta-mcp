import asyncio
import time
from collections import deque
from typing import Any
from urllib.parse import urlencode

from dedalus_mcp import tool, get_context, HttpMethod, HttpRequest
from pydantic import BaseModel


# --- Result Models ---
# Define Pydantic models for structured tool responses.
# Each tool should return a model so clients receive typed, predictable data.


class CartaResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None


# --- Rate Limiter ---
# Carta enforces 10 requests/second and 300 requests/minute.
# https://docs.carta.com/carta/docs/rate-limiting


class _RateLimiter:
    """Sliding-window rate limiter that respects both per-second and per-minute caps."""

    def __init__(self, per_second: int = 10, per_minute: int = 300) -> None:
        self._per_second = per_second
        self._per_minute = per_minute
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a request slot is available under both rate limits."""
        while True:
            sleep_for = 0.0
            async with self._lock:
                now = time.monotonic()

                while self._timestamps and self._timestamps[0] <= now - 60:
                    self._timestamps.popleft()

                if len(self._timestamps) >= self._per_minute:
                    sleep_for = self._timestamps[0] - (now - 60) + 0.05
                else:
                    one_sec_ago = now - 1
                    recent = sum(1 for t in self._timestamps if t > one_sec_ago)

                    if recent >= self._per_second:
                        for t in self._timestamps:
                            if t > one_sec_ago:
                                sleep_for = t - one_sec_ago + 0.05
                                break
                    else:
                        self._timestamps.append(now)
                        return

            await asyncio.sleep(sleep_for)


_rate_limiter = _RateLimiter()


# --- Helpers ---


async def _carta_get(path: str) -> CartaResult:
    """Execute an authenticated GET request against the Carta API."""
    await _rate_limiter.acquire()
    ctx = get_context()
    resp = await ctx.dispatch(HttpRequest(method=HttpMethod.GET, path=path))
    if resp.success:
        return CartaResult(success=True, data=resp.response.body)
    return CartaResult(
        success=False,
        error=resp.error.message if resp.error else "Request failed",
    )


def _build_path(base: str, **params: Any) -> str:
    """Append non-None query parameters to a path."""
    filtered = {k: v for k, v in params.items() if v is not None}
    if not filtered:
        return base
    return f"{base}?{urlencode(filtered)}"


# --- Tool Definitions ---
# Decorate functions with @tool to expose them to MCP clients.
# The description appears in tool listings; the docstring provides extra detail.


# ========================================================================
# User
# ========================================================================

@tool(description="Get the current authenticated Carta user's profile information")
async def get_current_user() -> CartaResult:
    """Retrieve the authenticated user's id, name, and email address."""
    return await _carta_get("/v1alpha1/users/me")


# ========================================================================
# Investor — Firms
# ========================================================================

@tool(description="List investment firms accessible to the authenticated user")
async def list_investor_firms(
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve investment firms.

    Args:
        page_size: Max firms to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path("/v1alpha1/investors/firms", pageSize=page_size, pageToken=page_token)
    return await _carta_get(path)


# ========================================================================
# Investor — Funds
# ========================================================================

@tool(description="List investment funds belonging to a given firm")
async def list_investor_funds(
    firm_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve the investment funds of a given investment firm.

    Args:
        firm_id: Identifier of the investment firm.
        page_size: Max funds to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/investors/firms/{firm_id}/funds",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Investor — Investments
# ========================================================================

@tool(description="List portfolio-company investments for a given fund")
async def list_investor_investments(
    firm_id: str,
    fund_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve the company investments or portfolio companies of a given fund.

    Args:
        firm_id: Identifier of the investment firm.
        fund_id: Identifier of the fund.
        page_size: Max investments to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/investors/firms/{firm_id}/funds/{fund_id}/investments",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Investor — Securities
# ========================================================================

@tool(description="List securities held by a given fund in an investment firm")
async def list_investor_securities(
    firm_id: str,
    fund_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve securities for a given fund.

    Args:
        firm_id: Identifier of the investment firm.
        fund_id: Identifier of the fund.
        page_size: Max securities to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/investors/firms/{firm_id}/funds/{fund_id}/securities",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Investor — Partners
# ========================================================================

@tool(description="List partners (limited partners) in a given fund")
async def list_investor_partners(
    firm_id: str,
    fund_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve partners in funds in an investment firm.

    Args:
        firm_id: Identifier of the investment firm.
        fund_id: Identifier of the fund.
        page_size: Max partners to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/investors/firms/{firm_id}/funds/{fund_id}/partners",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Investor — Cash Balances
# ========================================================================

@tool(description="List cash balances for funds in a given investment firm")
async def list_investor_cash_balances(
    firm_id: str,
    fund_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve cash balance information for a fund.

    Args:
        firm_id: Identifier of the investment firm.
        fund_id: Identifier of the fund.
        page_size: Max entries to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/investors/firms/{firm_id}/funds/{fund_id}/cashBalances",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Investor — Fund Performance
# ========================================================================

@tool(description="Get fund performance metrics for a given fund")
async def get_investor_fund_performance(
    firm_id: str,
    fund_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve fund performance metrics.

    Args:
        firm_id: Identifier of the investment firm.
        fund_id: Identifier of the fund.
        page_size: Max entries to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/investors/firms/{firm_id}/funds/{fund_id}/performance",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Investor — Capitalization Tables
# ========================================================================

@tool(description="Get the capitalization table summary for a portfolio-company investment")
async def get_investor_capitalization_table(
    firm_id: str,
    fund_id: str,
    company_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve the summary capitalization table of an investor investment.

    Args:
        firm_id: Identifier of the investment firm.
        fund_id: Identifier of the fund.
        company_id: Identifier of the portfolio company (investment).
        page_size: Max entries to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/investors/firms/{firm_id}/funds/{fund_id}/investments/{company_id}/capitalizationTable",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


@tool(description="Get stakeholder-level capitalization table for a portfolio-company investment")
async def get_investor_stakeholder_capitalization_table(
    firm_id: str,
    fund_id: str,
    company_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve stakeholder-level capitalization table information about an investment company.

    Args:
        firm_id: Identifier of the investment firm.
        fund_id: Identifier of the fund.
        company_id: Identifier of the portfolio company (investment).
        page_size: Max entries to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/investors/firms/{firm_id}/funds/{fund_id}/investments/{company_id}/stakeholderCapitalizationTable",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Info
# ========================================================================

@tool(description="List issuers (companies) accessible to the authenticated user")
async def list_issuers(
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve issuers.

    Args:
        page_size: Max issuers to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path("/v1alpha1/issuers", pageSize=page_size, pageToken=page_token)
    return await _carta_get(path)


# ========================================================================
# Issuer — Stakeholders
# ========================================================================

@tool(description="List stakeholders (equity holders) for a given issuer")
async def list_issuer_stakeholders(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve stakeholders. A stakeholder is a person or entity that has been
    issued a security by an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        page_size: Max stakeholders to return (default 25, max 100).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/stakeholders",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Share Classes
# ========================================================================

@tool(description="List share classes for a given issuer, optionally as of a specific date")
async def list_issuer_share_classes(
    issuer_id: str,
    as_of_date: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve an issuer's share classes.

    Args:
        issuer_id: Identifier of the issuer.
        as_of_date: Retrieve share classes as of this date (ISO 8601 YYYY-MM-DD).
        page_size: Max share classes to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/shareClasses",
        asOfDate=as_of_date, pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Valuations
# ========================================================================

@tool(description="List 409A valuations for a given issuer")
async def list_issuer_valuations(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve valuation information about an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        page_size: Max valuations to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/valuations",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Securities (option grants)
# ========================================================================

@tool(description="List option grants issued by a given issuer")
async def list_issuer_option_grants(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve option grant securities for an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        page_size: Max option grants to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/optionGrants",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Securities (stock certificates)
# ========================================================================

@tool(description="List stock certificates issued by a given issuer")
async def list_issuer_stock_certificates(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve stock certificate securities for an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        page_size: Max certificates to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/stockCertificates",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Securities (warrants)
# ========================================================================

@tool(description="List warrants issued by a given issuer")
async def list_issuer_warrants(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve warrant securities for an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        page_size: Max warrants to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/warrants",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Securities (convertible notes)
# ========================================================================

@tool(description="List convertible notes issued by a given issuer")
async def list_issuer_convertible_notes(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve convertible note securities for an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        page_size: Max convertible notes to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/convertibleNotes",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Draft Securities
# ========================================================================

@tool(description="List draft option grants for a given issuer (not yet issued)")
async def list_issuer_draft_option_grants(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve draft option grant securities for an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        page_size: Max draft grants to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/draftSecurities/optionGrants",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Securities Templates (vesting schedules)
# ========================================================================

@tool(description="List vesting schedule templates for a given issuer")
async def list_issuer_vesting_schedules(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve vesting schedule templates for an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        page_size: Max vesting schedules to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/securitiesTemplates/vestingSchedules",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Interests (LLC issuers)
# ========================================================================

@tool(description="List interests for an LLC-type issuer")
async def list_issuer_interests(
    issuer_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve interests for an LLC issuer.

    Args:
        issuer_id: Identifier of the LLC issuer.
        page_size: Max interests to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/interests",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Capitalization Table Summary
# ========================================================================

@tool(description="Get the aggregated capitalization table summary for a given issuer")
async def get_issuer_cap_table_summary(
    issuer_id: str,
    as_of_date: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve aggregated summary information of an issuer's capitalization table.

    Args:
        issuer_id: Identifier of the issuer.
        as_of_date: Cap table as of this date (ISO 8601 YYYY-MM-DD).
        page_size: Max entries to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/capitalizationTableSummary",
        asOfDate=as_of_date, pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Issuer — Stakeholder Capitalization Table
# ========================================================================

@tool(description="Get stakeholder-level capitalization table for a given issuer")
async def get_issuer_stakeholder_cap_table(
    issuer_id: str,
    as_of_date: str | None = None,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve stakeholder capitalization table for an issuer.

    Args:
        issuer_id: Identifier of the issuer.
        as_of_date: Cap table as of this date (ISO 8601 YYYY-MM-DD).
        page_size: Max entries to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/issuers/{issuer_id}/stakeholderCapitalizationTable",
        asOfDate=as_of_date, pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Portfolio — Info
# ========================================================================

@tool(description="List shareholder portfolios accessible to the authenticated user")
async def list_portfolios(
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve shareholder portfolios.

    Args:
        page_size: Max portfolios to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path("/v1alpha1/portfolios", pageSize=page_size, pageToken=page_token)
    return await _carta_get(path)


# ========================================================================
# Portfolio — Securities
# ========================================================================

@tool(description="List securities (holdings) in a given portfolio")
async def list_portfolio_securities(
    portfolio_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve securities issued to a portfolio.

    Args:
        portfolio_id: Identifier of the portfolio.
        page_size: Max securities to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/portfolios/{portfolio_id}/securities",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Portfolio — Transactions
# ========================================================================

@tool(description="List security transactions for a given portfolio")
async def list_portfolio_transactions(
    portfolio_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve transactions related to a portfolio.

    Args:
        portfolio_id: Identifier of the portfolio.
        page_size: Max transactions to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/portfolios/{portfolio_id}/transactions",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Portfolio — Issuer Valuations
# ========================================================================

@tool(description="List issuer valuations for companies held in a given portfolio")
async def list_portfolio_issuer_valuations(
    portfolio_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve valuation information for issuers within a portfolio.

    Args:
        portfolio_id: Identifier of the portfolio.
        page_size: Max valuations to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/portfolios/{portfolio_id}/issuerValuations",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Portfolio — Fund Investment Documents
# ========================================================================

@tool(description="List fund investment documents for a given portfolio")
async def list_portfolio_fund_investment_documents(
    portfolio_id: str,
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve fund investment documents from a portfolio.

    Args:
        portfolio_id: Identifier of the portfolio.
        page_size: Max documents to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        f"/v1alpha1/portfolios/{portfolio_id}/fundInvestmentDocuments",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Corporation
# ========================================================================

@tool(description="List corporations and their details (name, description, website)")
async def list_corporations(
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve corporation details.

    Args:
        page_size: Max corporations to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path("/v1alpha1/corporations", pageSize=page_size, pageToken=page_token)
    return await _carta_get(path)


# ========================================================================
# Compensation Benchmarks
# ========================================================================

@tool(description="Get compensation benchmarking data from Carta Total Comp")
async def get_compensation_benchmarks(
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve compensation benchmarking data.

    Args:
        page_size: Max entries to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path(
        "/v1alpha1/compensation/benchmarks",
        pageSize=page_size, pageToken=page_token,
    )
    return await _carta_get(path)


# ========================================================================
# Open Cap Tables
# ========================================================================

@tool(description="List open cap tables accessible to the authenticated user")
async def list_open_cap_tables(
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve open cap tables.

    Args:
        page_size: Max cap tables to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path("/v1alpha1/openCapTables", pageSize=page_size, pageToken=page_token)
    return await _carta_get(path)


# ========================================================================
# Draft Issuers (Carta Launch)
# ========================================================================

@tool(description="List draft issuers from Carta Launch")
async def list_draft_issuers(
    page_size: int | None = None,
    page_token: str | None = None,
) -> CartaResult:
    """
    Retrieve draft issuers.

    Args:
        page_size: Max draft issuers to return (default 25, max 50).
        page_token: Token from a previous response to fetch the next page.
    """
    path = _build_path("/v1alpha1/draftIssuers", pageSize=page_size, pageToken=page_token)
    return await _carta_get(path)


# --- Tool Registry ---
# List every tool here. main.py iterates this list to register them with the server.

tools = [
    # User
    get_current_user,
    # Investor
    list_investor_firms,
    list_investor_funds,
    list_investor_investments,
    list_investor_securities,
    list_investor_partners,
    list_investor_cash_balances,
    get_investor_fund_performance,
    get_investor_capitalization_table,
    get_investor_stakeholder_capitalization_table,
    # Issuer
    list_issuers,
    list_issuer_stakeholders,
    list_issuer_share_classes,
    list_issuer_valuations,
    list_issuer_option_grants,
    list_issuer_stock_certificates,
    list_issuer_warrants,
    list_issuer_convertible_notes,
    list_issuer_draft_option_grants,
    list_issuer_vesting_schedules,
    list_issuer_interests,
    get_issuer_cap_table_summary,
    get_issuer_stakeholder_cap_table,
    # Portfolio
    list_portfolios,
    list_portfolio_securities,
    list_portfolio_transactions,
    list_portfolio_issuer_valuations,
    list_portfolio_fund_investment_documents,
    # Corporation
    list_corporations,
    # Compensation
    get_compensation_benchmarks,
    # Open Cap Tables
    list_open_cap_tables,
    # Draft Issuers / Launch
    list_draft_issuers,
]
