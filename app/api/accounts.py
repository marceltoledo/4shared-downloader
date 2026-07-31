from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import config
from app.core.accounts import add_account, read_accounts, remove_account

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class AccountOut(BaseModel):
    folder_id: str
    url: str
    history_count: int


class AccountIn(BaseModel):
    url: str = Field(min_length=1)


@router.get("", response_model=list[AccountOut])
def list_accounts():
    accounts = read_accounts(config.ACCOUNTS_FILE, config.HISTORY_DIR)
    return [AccountOut(folder_id=a.folder_id, url=a.url, history_count=a.history_count) for a in accounts]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(body: AccountIn):
    account = add_account(config.ACCOUNTS_FILE, config.HISTORY_DIR, body.url)
    return AccountOut(folder_id=account.folder_id, url=account.url, history_count=account.history_count)


@router.delete("/{folder_id}", status_code=204)
def delete_account(folder_id: str):
    if not remove_account(config.ACCOUNTS_FILE, folder_id):
        raise HTTPException(status_code=404, detail="Account not found")
