from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, JsonValue
from sqlalchemy.orm import Session

from nexus.api.deps import get_session
from nexus.settings_store.models import AppSetting

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingValue(BaseModel):
    value: JsonValue


@router.get("/{key}", response_model=SettingValue)
def read_setting(key: str, session: Session = Depends(get_session)) -> SettingValue:
    setting = session.get(AppSetting, key)
    if setting is None:
        raise HTTPException(404, f"Unknown setting: {key}")
    return SettingValue(value=setting.value)


@router.put("/{key}", response_model=SettingValue)
def write_setting(
    key: str, body: SettingValue, session: Session = Depends(get_session)
) -> SettingValue:
    session.merge(AppSetting(key=key, value=body.value))
    return body
