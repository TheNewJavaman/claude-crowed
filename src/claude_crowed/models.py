from pydantic import BaseModel


class MemorySearchResult(BaseModel):
    id: str
    title: str
    similarity: float
    created_at: str
    updated_at: str
    is_deleted: bool


class MemoryFull(BaseModel):
    id: str
    version: int
    title: str
    content: str
    created_at: str
    updated_at: str
    source: str
    is_deleted: bool


class MemoryVersion(BaseModel):
    id: str
    version: int
    title: str
    content: str
    updated_at: str


class TimelineItem(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    is_deleted: bool


class TimelineResponse(BaseModel):
    items: list[TimelineItem]
    next_cursor: str | None


class RelatedMemory(BaseModel):
    id: str
    title: str
    updated_at: str


class ExportData(BaseModel):
    version: int = 1
    exported_at: str
    memories: list[dict]


class MemoryStats(BaseModel):
    total_memories: int
    total_deleted: int
    total_versions: int
    oldest_memory: str | None
    newest_memory: str | None
    db_size_bytes: int
