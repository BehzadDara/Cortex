from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_memory_store
from app.rag.memory import MemoryStore
from app.schemas import MemoryResponse

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[MemoryResponse])
def list_memories(
    store: MemoryStore = Depends(get_memory_store),
) -> list[MemoryResponse]:
    return [
        MemoryResponse(id=memory.id, text=memory.text, created_at=memory.created_at)
        for memory in store.all()
    ]


@router.delete("/{memory_id}")
def forget_memory(
    memory_id: str, store: MemoryStore = Depends(get_memory_store)
) -> dict:
    try:
        store.forget(memory_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"forgotten": memory_id}
