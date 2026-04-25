from __future__ import annotations

from fastapi import Depends, status
from pymongo import ASCENDING
from pymongo.collection import Collection

from app.core.database import get_dependency_collection, get_service_collection
from app.core.exceptions import AppException
from app.core.settings import Settings, get_settings
from app.schemas.config import (
    ConfigImportRequest,
    ConfigImportResponse,
    DependencyResponse,
    DependencyUpsertRequest,
    ImpactDetailResponse,
    ImpactDirection,
    ImpactResponse,
    ServiceConfigListResponse,
    ServiceConfigResponse,
    ServiceConfigUpsertRequest,
)

SERVICE_NOT_FOUND_CODE = "service_not_found"
SERVICE_NOT_FOUND_MESSAGE = "Service configuration was not found."


class ConfigService:
    def __init__(self, service_collection: Collection, dependency_collection: Collection, settings: Settings) -> None:
        self.service_collection = service_collection
        self.dependency_collection = dependency_collection
        self.settings = settings
        self.service_collection.create_index("service_name", unique=True)
        self.service_collection.create_index("repository_full_name", unique=True)
        self.dependency_collection.create_index("service_name", unique=True)
        self.dependency_collection.create_index([("depends_on", ASCENDING)])

    def upsert_service(self, payload: ServiceConfigUpsertRequest) -> ServiceConfigResponse:
        document = payload.model_dump()
        self.service_collection.update_one({"service_name": payload.service_name}, {"$set": document}, upsert=True)
        saved = self.service_collection.find_one({"service_name": payload.service_name})
        return self._to_service_response(saved)

    def list_services(self) -> ServiceConfigListResponse:
        items = [self._to_service_response(document) for document in self.service_collection.find().sort("service_name", ASCENDING)]
        return ServiceConfigListResponse(items=items, total=len(items))

    def get_service(self, service_name: str) -> ServiceConfigResponse:
        document = self.service_collection.find_one({"service_name": service_name})
        if not document:
            self._raise_service_not_found(service_name)
        return self._to_service_response(document)

    def get_repo(self, repository_full_name: str) -> ServiceConfigResponse:
        document = self.service_collection.find_one({"repository_full_name": repository_full_name})
        if not document:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code=SERVICE_NOT_FOUND_CODE,
                message=SERVICE_NOT_FOUND_MESSAGE,
                details={"repository_full_name": repository_full_name},
            )
        return self._to_service_response(document)

    def upsert_dependencies(self, payload: DependencyUpsertRequest) -> DependencyResponse:
        self._ensure_service_exists(payload.service_name)
        sorted_dependencies = sorted(set(payload.depends_on))
        self._ensure_services_exist(sorted_dependencies)
        self.dependency_collection.update_one(
            {"service_name": payload.service_name},
            {"$set": {"service_name": payload.service_name, "depends_on": sorted_dependencies}},
            upsert=True,
        )
        saved = self.dependency_collection.find_one({"service_name": payload.service_name})
        return self._to_dependency_response(saved)

    def import_graph(self, payload: ConfigImportRequest) -> ConfigImportResponse:
        for service in payload.services:
            self.upsert_service(service)
        for dependency in payload.dependencies:
            self.upsert_dependencies(dependency)
        return ConfigImportResponse(
            imported_services=len(payload.services),
            imported_dependency_sets=len(payload.dependencies),
        )

    def get_impact(self, service_name: str) -> ImpactResponse:
        self._ensure_service_exists(service_name)
        dependency_document = self.dependency_collection.find_one({"service_name": service_name}) or {
            "service_name": service_name,
            "depends_on": [],
        }
        direct_dependencies = sorted(dependency_document.get("depends_on", []))
        reverse_graph = self._build_reverse_graph()
        downstream_paths = self._build_downstream_paths(service_name, reverse_graph)
        downstream_services = sorted(path[-1] for path in downstream_paths.values())

        impact_details = [
            ImpactDetailResponse(
                service_name=dependency_name,
                relationship=ImpactDirection.dependency,
                path=[service_name, dependency_name],
                explanation=f"{service_name} directly depends on {dependency_name}.",
            )
            for dependency_name in direct_dependencies
        ]
        impact_details.extend(
            ImpactDetailResponse(
                service_name=downstream_name,
                relationship=ImpactDirection.downstream,
                path=path,
                explanation=self._build_downstream_explanation(path),
            )
            for downstream_name, path in sorted(downstream_paths.items())
        )

        return ImpactResponse(
            service_name=service_name,
            direct_dependencies=direct_dependencies,
            downstream_services=downstream_services,
            impact_summary=self._build_impact_summary(service_name, direct_dependencies, downstream_services),
            impact_details=impact_details,
        )

    def _build_reverse_graph(self) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {}
        for document in self.dependency_collection.find():
            service_name = document["service_name"]
            for dependency_name in document.get("depends_on", []):
                graph.setdefault(dependency_name, []).append(service_name)
        for dependents in graph.values():
            dependents.sort()
        return graph

    def _build_downstream_paths(self, service_name: str, reverse_graph: dict[str, list[str]]) -> dict[str, list[str]]:
        queue: list[tuple[str, list[str]]] = [(service_name, [service_name])]
        visited = {service_name}
        paths: dict[str, list[str]] = {}

        while queue:
            current, path = queue.pop(0)
            for dependent in reverse_graph.get(current, []):
                if dependent in visited:
                    continue
                visited.add(dependent)
                next_path = [*path, dependent]
                paths[dependent] = next_path
                queue.append((dependent, next_path))
        return paths

    @staticmethod
    def _build_downstream_explanation(path: list[str]) -> str:
        downstream_service = path[-1]
        dependency_chain = list(reversed(path))
        if len(dependency_chain) == 2:
            return f"{downstream_service} is impacted because it directly depends on {dependency_chain[1]}."
        chain_text = ", which depends on ".join(dependency_chain[1:])
        return f"{downstream_service} is impacted because it depends on {chain_text}."

    @staticmethod
    def _build_impact_summary(service_name: str, direct_dependencies: list[str], downstream_services: list[str]) -> str:
        dependency_count = len(direct_dependencies)
        downstream_count = len(downstream_services)
        return (
            f"{service_name} depends on {dependency_count} service(s) and has "
            f"{downstream_count} downstream impacted service(s)."
        )

    def _ensure_service_exists(self, service_name: str) -> None:
        if not self.service_collection.find_one({"service_name": service_name}, {"_id": 1}):
            self._raise_service_not_found(service_name)

    def _ensure_services_exist(self, service_names: list[str]) -> None:
        for service_name in service_names:
            self._ensure_service_exists(service_name)

    def _raise_service_not_found(self, service_name: str) -> None:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code=SERVICE_NOT_FOUND_CODE,
            message=SERVICE_NOT_FOUND_MESSAGE,
            details={"service_name": service_name},
        )

    @staticmethod
    def _to_service_response(document: dict) -> ServiceConfigResponse:
        response_data = dict(document)
        response_data["id"] = str(response_data.pop("_id"))
        return ServiceConfigResponse.model_validate(response_data)

    @staticmethod
    def _to_dependency_response(document: dict) -> DependencyResponse:
        response_data = dict(document)
        response_data["id"] = str(response_data.pop("_id"))
        return DependencyResponse.model_validate(response_data)


def get_config_service(
    settings: Settings = Depends(get_settings),
) -> ConfigService:
    return ConfigService(
        service_collection=get_service_collection(settings),
        dependency_collection=get_dependency_collection(settings),
        settings=settings,
    )
