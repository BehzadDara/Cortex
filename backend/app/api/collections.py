from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_session, get_vector_store
from app.models import Collection
from app.rag.vector_store import VectorStore
from app.schemas import CollectionCreate, CollectionResponse

router = APIRouter(prefix="/collections", tags=["collections"])


def to_response(collection: Collection) -> CollectionResponse:
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        document_count=len(collection.documents),
        created_at=collection.created_at,
    )


@router.post("", response_model=CollectionResponse, status_code=201)
def create_collection(
    request: CollectionCreate, session: Session = Depends(get_session)
) -> CollectionResponse:
    existing = session.scalar(
        select(Collection).where(Collection.name == request.name)
    )
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Collection {request.name} already exists"
        )

    collection = Collection(name=request.name)
    session.add(collection)
    session.commit()
    return to_response(collection)


@router.get("", response_model=list[CollectionResponse])
def list_collections(
    session: Session = Depends(get_session),
) -> list[CollectionResponse]:
    collections = session.scalars(select(Collection)).all()
    return [to_response(collection) for collection in collections]


@router.delete("/{collection_id}", status_code=204)
def delete_collection(
    collection_id: int,
    session: Session = Depends(get_session),
    vector_store: VectorStore = Depends(get_vector_store),
) -> None:
    collection = session.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    chunk_ids = [
        chunk.id for document in collection.documents for chunk in document.chunks
    ]
    if chunk_ids:
        vector_store.remove(chunk_ids)
    session.delete(collection)
    session.commit()
