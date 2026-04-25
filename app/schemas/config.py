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


class ConfigImportRequest(BaseModel):
    services: list[ServiceConfigUpsertRequest] = Field(default_factory=list)
    dependencies: list[DependencyUpsertRequest] = Field(default_factory=list)


class ConfigImportResponse(BaseModel):
    imported_services: int
    imported_dependency_sets: int


class DependencyResponse(BaseModel):
    id: str
    service_name: str
    depends_on: list[str]


class ImpactDirection(str, Enum):
    dependency = "dependency"
    downstream = "downstream"


class ImpactDetailResponse(BaseModel):
    service_name: str
    relationship: ImpactDirection
    path: list[str] = Field(default_factory=list)
    explanation: str


class ImpactResponse(BaseModel):
    service_name: str
    direct_dependencies: list[str]
    downstream_services: list[str]
    impact_summary: str
    impact_details: list[ImpactDetailResponse] = Field(default_factory=list)
