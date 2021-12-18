from fastapi import APIRouter
from pydantic import BaseModel

from . import queries, utils

router = APIRouter()


class CreateAccountPayload(BaseModel):
    username: str
    password: str


@router.get("/")
async def create_account(body: CreateAccountPayload):
    hashed_password = utils.hash_password(body.password)
    await queries.create_account(
        username=body.username, hashed_password=hashed_password
    )
    return {"success": True}
