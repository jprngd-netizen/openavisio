import uuid

from fastapi import APIRouter, Depends, Query

from app.deps import get_current_user
from app.models.user import User
from app.services import cid10

router = APIRouter()


@router.get("/cid10/search")
async def search_cid10(
    q: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
):
    """Search the CID-10 (pt-BR) catalogue for the diagnosis picker.

    Matches on the code (exact, then prefix) and, failing that, on the
    description text (accent-insensitive). Auth required; no patient scope.
    """
    return cid10.search(q, limit)
