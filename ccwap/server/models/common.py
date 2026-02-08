"""Common Pydantic models for API request/response validation."""

from datetime import date
from typing import Optional, Literal

from pydantic import BaseModel, Field, model_validator


class DateRangeParams(BaseModel):
    """Date range query parameters."""
    date_from: Optional[date] = Field(None, alias="from")
    date_to: Optional[date] = Field(None, alias="to")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before date_to")
        today = date.today()
        if self.date_from and self.date_from > today:
            raise ValueError("date_from cannot be in the future")
        return self


class PaginationParams(BaseModel):
    """Pagination query parameters."""
    page: int = Field(1, ge=1)
    limit: int = Field(50, ge=1, le=200)
    sort: Optional[str] = None
    order: Literal["asc", "desc"] = "desc"


class PaginationMeta(BaseModel):
    """Pagination metadata in responses."""
    page: int
    limit: int
    total_count: int
    total_pages: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
