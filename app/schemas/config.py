from enum import Enum

from pydantic import BaseModel, Field


class ServiceCriticality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ServiceConfigUpsertRequest(BaseModel):
    service_name: str = Field(..., examples=["pronunt-aggregator-service"])
    repository_full_name: str = Field(..., examples=["pronunt/pronunt-aggregator-service"])
    display_name: str
    description: str | None = None
    criticality: ServiceCriticality = ServiceCriticality.medium
    owners: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ServiceConfigResponse(ServiceConfigUpsertRequest):
    id: str


class ServiceConfigListResponse(BaseModel):
    items: list[ServiceConfigResponse]
    total: int


class DependencyUpsertRequest(BaseModel):
    service_name: str
    depends_on: list[str] = Field(default_factory=list)


class DependencyResponse(BaseModel):
    id: str
    service_name: str
    depends_on: list[str]


class ImpactResponse(BaseModel):
    service_name: str
    direct_dependencies: list[str]
    downstream_services: list[str]
