from app.core.exceptions import AppException
from app.core.settings import Settings
from app.schemas.config import ConfigImportRequest, DependencyUpsertRequest, ServiceConfigUpsertRequest
from app.services.config import ConfigService


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    def create_index(self, *args, **kwargs) -> None:
        return None

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        document = next((item for item in self.documents if all(item.get(key) == value for key, value in query.items())), None)
        if document is None:
            document = {"_id": f"id-{len(self.documents) + 1}"}
            self.documents.append(document)
        document.update(update["$set"])

    def find_one(self, query: dict, projection: dict | None = None) -> dict | None:
        for document in self.documents:
            if self._matches(document, query):
                return dict(document)
        return None

    def find(self, query: dict | None = None):
        query = query or {}
        results = [dict(document) for document in self.documents if self._matches(document, query)]
        return FakeCursor(results)

    @staticmethod
    def _matches(document: dict, query: dict) -> bool:
        for key, value in query.items():
            if key == "depends_on":
                if value not in document.get(key, []):
                    return False
                continue
            if document.get(key) != value:
                return False
        return True


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents

    def sort(self, field_name: str, _direction) -> list[dict]:
        return sorted(self.documents, key=lambda document: document[field_name])


def test_upsert_service_and_repo_lookup_work() -> None:
    service = ConfigService(FakeCollection(), FakeCollection(), Settings(_env_file=None, allow_unsafe_dev_auth=True))

    created = service.upsert_service(
        ServiceConfigUpsertRequest(
            service_name="pronunt-aggregator-service",
            repository_full_name="pronunt/pronunt-aggregator-service",
            display_name="Aggregator",
            criticality="critical",
        )
    )
    fetched = service.get_repo("pronunt/pronunt-aggregator-service")

    assert created.service_name == "pronunt-aggregator-service"
    assert fetched.repository_full_name == "pronunt/pronunt-aggregator-service"


def test_upsert_dependencies_requires_known_service() -> None:
    service = ConfigService(FakeCollection(), FakeCollection(), Settings(_env_file=None, allow_unsafe_dev_auth=True))

    try:
        service.upsert_dependencies(
            DependencyUpsertRequest(
                service_name="pronunt-worker-service",
                depends_on=["pronunt-aggregator-service"],
            )
        )
    except AppException as exc:
        assert exc.code == "service_not_found"
    else:
        raise AssertionError("Expected unknown service to fail.")


def test_impact_returns_direct_and_downstream_services() -> None:
    service_collection = FakeCollection()
    dependency_collection = FakeCollection()
    service = ConfigService(service_collection, dependency_collection, Settings(_env_file=None, allow_unsafe_dev_auth=True))

    service.upsert_service(
        ServiceConfigUpsertRequest(
            service_name="pronunt-aggregator-service",
            repository_full_name="pronunt/pronunt-aggregator-service",
            display_name="Aggregator",
        )
    )
    service.upsert_service(
        ServiceConfigUpsertRequest(
            service_name="pronunt-worker-service",
            repository_full_name="pronunt/pronunt-worker-service",
            display_name="Worker",
        )
    )
    service.upsert_service(
        ServiceConfigUpsertRequest(
            service_name="pronunt-frontend-service",
            repository_full_name="pronunt/pronunt-frontend-service",
            display_name="Frontend",
        )
    )
    service.upsert_dependencies(
        DependencyUpsertRequest(
            service_name="pronunt-worker-service",
            depends_on=["pronunt-aggregator-service"],
        )
    )
    service.upsert_dependencies(
        DependencyUpsertRequest(
            service_name="pronunt-frontend-service",
            depends_on=["pronunt-worker-service"],
        )
    )

    impact = service.get_impact("pronunt-worker-service")

    assert impact.service_name == "pronunt-worker-service"
    assert impact.direct_dependencies == ["pronunt-aggregator-service"]
    assert impact.downstream_services == ["pronunt-frontend-service"]


def test_import_graph_creates_services_and_dependencies() -> None:
    service = ConfigService(FakeCollection(), FakeCollection(), Settings(_env_file=None, allow_unsafe_dev_auth=True))

    result = service.import_graph(
        ConfigImportRequest(
            services=[
                ServiceConfigUpsertRequest(
                    service_name="pronunt-aggregator-service",
                    repository_full_name="pronunt/pronunt-aggregator-service",
                    display_name="Aggregator",
                ),
                ServiceConfigUpsertRequest(
                    service_name="pronunt-worker-service",
                    repository_full_name="pronunt/pronunt-worker-service",
                    display_name="Worker",
                ),
            ],
            dependencies=[
                DependencyUpsertRequest(
                    service_name="pronunt-worker-service",
                    depends_on=["pronunt-aggregator-service"],
                )
            ],
        )
    )

    assert result.imported_services == 2
    assert result.imported_dependency_sets == 1
