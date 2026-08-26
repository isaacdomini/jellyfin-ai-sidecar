from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, AliasChoices


class JellyfinItem(BaseModel):
    Id: Optional[str] = Field(default=None, validation_alias=AliasChoices("Id", "id", "ItemId", "item_id"))
    Name: Optional[str] = Field(default=None, validation_alias=AliasChoices("Name", "name", "ItemName", "item_name"))
    Type: Optional[str] = Field(default=None, validation_alias=AliasChoices("Type", "type", "ItemType", "item_type"))
    SeriesName: Optional[str] = Field(default=None, validation_alias=AliasChoices("SeriesName", "seriesName", "series_name"))
    SeasonName: Optional[str] = Field(default=None, validation_alias=AliasChoices("SeasonName", "seasonName", "season_name"))
    IndexNumber: Optional[int] = Field(default=None, validation_alias=AliasChoices("IndexNumber", "indexNumber", "index_number"))
    ParentIndexNumber: Optional[int] = Field(default=None, validation_alias=AliasChoices("ParentIndexNumber", "parentIndexNumber", "parent_index_number"))
    Overview: Optional[str] = Field(default=None, validation_alias=AliasChoices("Overview", "overview"))
    Path: Optional[str] = Field(default=None, validation_alias=AliasChoices("Path", "path", "ItemPath", "item_path"))
    RunTimeTicks: Optional[int] = Field(default=None, validation_alias=AliasChoices("RunTimeTicks", "runTimeTicks", "run_time_ticks"))
    MediaSources: Optional[List[Dict[str, Any]]] = Field(default=None, validation_alias=AliasChoices("MediaSources", "mediaSources", "media_sources"))


class JellyfinItemEvent(BaseModel):
    """
    Webhook payload sent by Jellyfin (e.g. on ItemAdded event).
    Supports standard Jellyfin webhook plugin schema variants.
    """
    Event: Optional[str] = Field(default="ItemAdded", validation_alias=AliasChoices("Event", "event", "NotificationType", "notification_type"))
    NotificationType: Optional[str] = Field(default=None, validation_alias=AliasChoices("NotificationType", "notificationType", "notification_type"))
    NotificationUsername: Optional[str] = Field(default=None, validation_alias=AliasChoices("NotificationUsername", "notificationUsername", "notification_username"))
    ServerId: Optional[str] = Field(default=None, validation_alias=AliasChoices("ServerId", "serverId", "server_id"))
    ServerName: Optional[str] = Field(default=None, validation_alias=AliasChoices("ServerName", "serverName", "server_name"))
    ServerVersion: Optional[str] = Field(default=None, validation_alias=AliasChoices("ServerVersion", "serverVersion", "server_version"))
    ItemId: Optional[str] = Field(default=None, validation_alias=AliasChoices("ItemId", "itemId", "item_id", "Id", "id"))
    ItemName: Optional[str] = Field(default=None, validation_alias=AliasChoices("ItemName", "itemName", "item_name", "Name", "name"))
    ItemType: Optional[str] = Field(default=None, validation_alias=AliasChoices("ItemType", "itemType", "item_type", "Type", "type"))
    ItemPath: Optional[str] = Field(default=None, validation_alias=AliasChoices("ItemPath", "itemPath", "item_path", "Path", "path"))
    Item: Optional[JellyfinItem] = Field(default=None, validation_alias=AliasChoices("Item", "item"))
    Timestamp: Optional[str] = Field(default=None, validation_alias=AliasChoices("Timestamp", "timestamp"))

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
    item_id: Optional[Union[str, List[str]]] = Field(None, description="Optional media item ID(s) to filter")
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


class RagQueryRequest(BaseModel):
    query: str = Field(..., description="User query or question to answer using media context")
    item_id: Optional[Union[str, List[str]]] = Field(None, description="Optional media item ID(s) to restrict the search")
    top_k: int = Field(default=15, ge=1, le=50, description="Number of context chunks to retrieve")
    provider: Optional[str] = Field(None, description="LLM provider: 'openai', 'gemini', 'anthropic', 'groq', 'ollama', 'custom', 'mock'")
    api_key: Optional[str] = Field(None, description="API key override for the LLM provider")
    model: Optional[str] = Field(None, description="Model identifier override")
    base_url: Optional[str] = Field(None, description="Custom base URL override (e.g. for Ollama or OpenAI-compatible)")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")


class RagCitation(BaseModel):
    item_id: str
    item_name: Optional[str] = None
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")
    timestamp_formatted: str = Field(..., description="Formatted timestamp (e.g. 01:45:10 - 01:46:20)")
    start_ticks: int = Field(..., description="Jellyfin playback ticks (10,000,000 ticks per second)")
    deep_link: str = Field(..., description="Jellyfin deep-link URL jumping straight to playback timestamp")
    text: str = Field(..., description="Quoted dialogue chunk")
    score: float = Field(..., description="Semantic similarity score")


class RagQueryResponse(BaseModel):
    query: str
    answer: str
    provider_used: str = "gemini"
    model_used: str = "gemini-3.5-flash-lite"
    citations: List[RagCitation] = Field(default_factory=list, description="Citations referenced with playback deep-links")
    sources: List[SearchResultItem] = Field(default_factory=list, description="Retrieved vector DB context chunks")


class ProviderModelInfo(BaseModel):
    id: str
    name: str
    default_model: str
    available_models: List[str]
    requires_api_key: bool
    supports_base_url: bool


