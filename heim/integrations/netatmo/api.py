from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/netatmo", tags=["netatmo"])
templates = Jinja2Templates(directory="heim/frontend/templates")
templates.env.loader.searchpath.append("heim/integrations/netatmo/templates")


@router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> HTMLResponse:
    """
    OAuth callback endpoint for Netatmo authorization.

    Displays the authorization code for the user to copy into the CLI.
    """
    return templates.TemplateResponse(
        "callback.html",
        {
            "request": request,
            "code": code,
            "error": error,
            "error_description": error_description,
        },
    )
