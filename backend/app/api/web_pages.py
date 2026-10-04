from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.dependencies import get_session
from app.models import WebPage
from app.rag.web_pages import PAGE_HEADERS

router = APIRouter(prefix="/web-pages", tags=["web pages"])


@router.get("/{page_id}", response_class=HTMLResponse)
def show_page(page_id: int, session: Session = Depends(get_session)) -> HTMLResponse:
    page = session.get(WebPage, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Web page not found")
    return HTMLResponse(page.html, headers=PAGE_HEADERS)
