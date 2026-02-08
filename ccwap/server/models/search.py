from typing import List
from pydantic import BaseModel


class SearchResult(BaseModel):
    category: str
    label: str
    sublabel: str = ""
    url: str


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
