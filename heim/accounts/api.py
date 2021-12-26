from fastapi import APIRouter
from pydantic import BaseModel

from . import queries

router = APIRouter(prefix="/accounts")


class CreateAccountPayload(BaseModel):
    username: str
    password: str


@router.post("/")
async def create_account(body: CreateAccountPayload):
    await queries.create_account(username=body.username, password=body.password)
    return {"success": True}
