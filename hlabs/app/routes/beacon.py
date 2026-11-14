"""JS beacon (static/px.js). The gateway reads and logs the body; the app just answers 204."""

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()


@router.post("/_hl/px")
def beacon() -> Response:
    return Response(status_code=204)
