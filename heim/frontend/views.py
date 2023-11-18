from typing import Annotated, Any

from fastapi import APIRouter, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..accounts.queries import get_account, get_locations
from ..accounts.utils import compare_password, hash_password
from ..auth.dependencies import CookieSession
from ..auth.queries import create_session, delete_session
from .dependencies import CurrentAccount
from .messages import Messages, get_messages

router = APIRouter()
templates = Jinja2Templates(directory="heim/frontend/templates")
templates.env.globals["get_messages"] = get_messages
fallback_password = hash_password("foobar")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, account_id: CurrentAccount) -> Response:
    locations = await get_locations(account_id=account_id)
    context = {"request": request, "locations": locations}
    return templates.TemplateResponse("index.html", context)


@router.get("/login", response_class=HTMLResponse)
def login(request: Request) -> Response:
    """
    Render the login form. The actual login is handled by the view below
    """

    context: dict[str, Any] = {"request": request}
    return templates.TemplateResponse("login.html", context)


@router.post("/login", response_class=RedirectResponse)
async def do_login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    messages: Messages,
) -> RedirectResponse:
    """
    Authenticate the user and set a session cookie.
    """

    if account := await get_account(username=username):
        account_id, stored_password = account
    else:
        account_id, stored_password = None, fallback_password

    if (
        not compare_password(
            stored_password=stored_password, provided_password=password
        )
        or account_id is None
    ):
        messages.error("Invalid credentials")
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    session = await create_session(account_id=account_id)
    response.set_cookie("session_id", session.key)
    return response


@router.get("/logout", response_class=RedirectResponse)
async def logout(request: Request, session: CookieSession) -> RedirectResponse:
    if session:
        await delete_session(session)
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_id")
    return response
