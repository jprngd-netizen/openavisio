import uuid
from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer

from app.core.datetimes import SAO_PAULO, ensure_aware

T = TypeVar("T")


def _local_iso(dt: datetime | None) -> str | None:
    """Serialize an instant in America/Sao_Paulo (its local wall-clock time).

    The clinical UI reads and slices these ISO strings as local dates/times
    (e.g. an all-day event's date), so returning the Brazil offset keeps the
    contract the string columns used to carry. Only the JSON form is re-rendered;
    in-memory code keeps a real datetime.
    """
    return dt.astimezone(SAO_PAULO).isoformat() if dt else None


# WS-5: a tz-aware datetime field. A naive value (an HTML datetime-local sends
# local wall-clock time) is read as America/Sao_Paulo; aware values pass through.
# On the wire it is an ISO-8601 string in the Sao Paulo offset, as before.
TzDateTime = Annotated[
    datetime,
    AfterValidator(ensure_aware),
    PlainSerializer(_local_iso, return_type=str, when_used="json"),
]


class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PagedResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
