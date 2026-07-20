"""Pydantic response models for the public map contract."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


CrimeCategory = Literal["Begal", "Geng Motor"]


class IncidentProperties(BaseModel):
    id: int
    occurred_at: datetime
    crime_type: CrimeCategory
    street_name: str | None = None
    location_precision: str


class IncidentFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: dict = Field(..., examples=[{"type": "Point", "coordinates": [107.6, -6.9]}])
    properties: IncidentProperties


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[IncidentFeature]
    total: int


class IncidentDetail(IncidentProperties):
    description: str
    location_status: str
    location_review_reason: str | None = None


class StreetReference(BaseModel):
    name: str
    latitude: float
    longitude: float


class RoadSearchResult(BaseModel):
    osm_way_id: int
    name: str
    highway_type: str
    latitude: float
    longitude: float


class RoadMatchRequest(BaseModel):
    road_name: str = Field(min_length=2, max_length=120)
    road_way_id: int | None = Field(default=None, ge=1)

    @field_validator("road_name")
    @classmethod
    def normalize_road_input(cls, value):
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("road_name must contain at least two characters")
        return normalized


class RoadMatchCandidate(BaseModel):
    osm_way_id: int
    name: str
    highway_type: str
    latitude: float
    longitude: float
    score: float | None = None


class RoadMatchResponse(BaseModel):
    status: Literal["exact", "alias_match", "ambiguous", "needs_review"]
    confidence: float = Field(ge=0, le=1)
    street_name_normalized: str | None = None
    road_way_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_precision: str
    geocode_source: str
    review_reason: str
    candidates: list[RoadMatchCandidate]


class ReportSubmission(RoadMatchRequest):
    crime_type: CrimeCategory
    occurred_at: datetime
    description: str = Field(min_length=20, max_length=500)
    reporter_name: str | None = Field(default=None, max_length=80)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value):
        normalized = " ".join(value.split())
        if len(normalized) < 20:
            raise ValueError("description must contain at least twenty characters")
        return normalized

    @field_validator("reporter_name")
    @classmethod
    def normalize_reporter_name(cls, value):
        if value is None:
            return None
        return " ".join(value.split()) or None


class ReportSubmissionResponse(BaseModel):
    id: int
    moderation_status: Literal["pending"]
    road_match: RoadMatchResponse
