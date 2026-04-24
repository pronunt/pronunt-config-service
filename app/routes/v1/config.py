from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.auth import AuthContext, require_roles
from app.schemas.config import (
    DependencyResponse,
    DependencyUpsertRequest,
    ImpactResponse,
    ServiceConfigListResponse,
    ServiceConfigResponse,
    ServiceConfigUpsertRequest,
)
from app.services.config import ConfigService, get_config_service

router = APIRouter(tags=["config"])
ConfigAccessDependency = Annotated[
    AuthContext,
    Depends(require_roles("developer", "reviewer", "release")),
]
ConfigServiceDependency = Annotated[ConfigService, Depends(get_config_service)]


@router.post("/services", status_code=status.HTTP_201_CREATED)
def upsert_service(
    payload: ServiceConfigUpsertRequest,
    _: ConfigAccessDependency,
    service: ConfigServiceDependency,
) -> ServiceConfigResponse:
    return service.upsert_service(payload)


@router.get("/services")
def list_services(
    _: ConfigAccessDependency,
    service: ConfigServiceDependency,
) -> ServiceConfigListResponse:
    return service.list_services()


@router.get("/services/{service_name}")
def get_service(
    service_name: str,
    _: ConfigAccessDependency,
    service: ConfigServiceDependency,
) -> ServiceConfigResponse:
    return service.get_service(service_name)


@router.get("/repos/{repository_full_name:path}")
def get_repo(
    repository_full_name: str,
    _: ConfigAccessDependency,
    service: ConfigServiceDependency,
) -> ServiceConfigResponse:
    return service.get_repo(repository_full_name)


@router.post("/dependencies", status_code=status.HTTP_201_CREATED)
def upsert_dependencies(
    payload: DependencyUpsertRequest,
    _: ConfigAccessDependency,
    service: ConfigServiceDependency,
) -> DependencyResponse:
    return service.upsert_dependencies(payload)


@router.get("/impact/{service_name}")
def get_impact(
    service_name: str,
    _: ConfigAccessDependency,
    service: ConfigServiceDependency,
) -> ImpactResponse:
    return service.get_impact(service_name)
