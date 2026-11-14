"""Template rendering shared by every route, including the error pages."""

from datetime import date, datetime
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from app import ledger
from app.auth import AUTH_COOKIE, AUTH_SALT, read_claims

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

ERRORS = {
    403: ("Access denied", "You don't have permission to view this page."),
    404: ("Page not found", "The page you're looking for doesn't exist or has moved."),
    500: ("Something went wrong", "An unexpected error occurred. Our team has been notified."),
    503: ("Down for maintenance", "We're doing some scheduled maintenance. Please try again in a few minutes."),
}


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def short_date(value: datetime | date | None) -> str:
    return value.strftime("%b %d, %Y") if value else "never"


def number(value: int) -> str:
    return f"{value:,}"


def compact(value: float) -> str:
    """12_345_678 -> 12.3M"""
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if value >= size:
            return f"{value / size:.1f}{unit}"
    return f"{value:,.0f}"


def period(value: str) -> str:
    """Billing period 2026-10 -> Oct 2026"""
    try:
        return datetime.strptime(value, "%Y-%m").strftime("%b %Y")
    except ValueError:
        return value


def visitor(request: Request) -> dict | None:
    """Claims of the signed-in customer, for the navigation bar."""
    secret = request.app.state.settings.session_secret
    return read_claims(secret, request.cookies.get(AUTH_COOKIE), AUTH_SALT)


templates.env.globals.update(bait=ledger.show, visitor=visitor)
templates.env.filters.update(money=money, short_date=short_date, number=number, compact=compact, period=period)


def page(request: Request, name: str, status_code: int = 200, **context: object) -> Response:
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def error_page(request: Request, status_code: int) -> Response:
    title, message = ERRORS.get(status_code, ERRORS[404])
    return page(request, "error.html", status_code=status_code, code=status_code, title=title, message=message)
