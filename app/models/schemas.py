from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class JellyfinItem(BaseModel):
    Id: Optional[str] = None
    Name: Optional[str] = None
    Type: Optional[str] = None  # e.g., "Movie", "Episode"
    SeriesName: Optional[str] = None
    SeasonName: Optional[str] = None
    IndexNumber: Optional[int] = None
    ParentIndexNumber: Optional[int] = None
    Overview: Optional[str] = None
    Path: Optional[str] = None
    RunTimeTicks: Optional[int] = None
    MediaSources: Optional[List[Dict[str, Any]]] = None


class JellyfinItemEvent(BaseModel):
    """
    Webhook payload sent by Jellyfin (e.g. on ItemAdded event).
    Supports standard Jellyfin webhook plugin schema variants.
    """
    Event: Optional[str] = "ItemAdded"
    NotificationType: Optional[str] = None
    NotificationUsername: Optional[str] = None
    ServerId: Optional[str] = None
    ServerName: Optional[str] = None
    ServerVersion: Optional[str] = None
    ItemId: Optional[str] = None
    ItemName: Optional[str] = None
    ItemType: Optional[str] = None
    ItemPath: Optional[str] = None
    Item: Optional[JellyfinItem] = None
    Timestamp: Optional[str] = None

    def get_item_id(self) -> Optional[str]:
        if self.Item and self.Item.Id:
            return self.Item.Id
        return self.ItemId

    def get_item_name(self) -> Optional[str]:
        if self.Item and self.Item.Name:
            return self.Item.Name
        return self.ItemName

    def get_file_path(self) -> Optional[str]:
        if self.Item and self.Item.Path:
            return self.Item.Path
        return self.ItemPath

    def get_overview(self) -> Optional[str]:
        if self.Item and self.Item.Overview:
            return self.Item.Overview
        return None


class SubtitleChunkSchema(BaseModel):
    id: Optional[int] = None
    item_id: str
    item_name: Optional[str] = None
    text: str
    start_time: float
    end_time: float
    embedding: Optional[List[float]] = None


class SearchQuery(BaseModel):
    query: str = Field(..., description="Query string for semantic search")
    item_id: Optional[str] = Field(None, description="Optional media item ID filter")
    top_k: int = Field(default=5, ge=1, le=50, description="Max number of matching chunks to return")


class SearchResultItem(BaseModel):
    id: Optional[int] = None
    item_id: str
    item_name: Optional[str] = None
    text: str
    start_time: float
    end_time: float
    score: float


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]

