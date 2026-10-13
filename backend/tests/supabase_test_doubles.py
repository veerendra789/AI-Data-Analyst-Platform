from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


class FakeResponse:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class FakeQuery:
    def __init__(self, client: FakeSupabase, table: str):
        self.client = client
        self.table_name = table
        self.action = "select"
        self.payload = None
        self.filters: list[tuple[str, object]] = []
        self.ordering: tuple[str, bool] | None = None
        self.window: tuple[int, int] | None = None
        self.max_results: int | None = None
        self.with_count = False

    def select(self, _columns="*", count=None):
        self.with_count = count == "exact"
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def upsert(self, payload, **_kwargs):
        self.action = "upsert"
        self.payload = payload
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        return self

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, field, desc=False):
        self.ordering = (field, desc)
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def limit(self, count):
        self.max_results = count
        return self

    def _matching_rows(self):
        return [
            row for row in self.client.tables.setdefault(self.table_name, [])
            if all(row.get(field) == value for field, value in self.filters)
        ]

    def execute(self):
        rows = self.client.tables.setdefault(self.table_name, [])
        if self.action == "insert":
            payloads = self.payload if isinstance(self.payload, list) else [self.payload]
            created = []
            for payload in payloads:
                row = deepcopy(payload)
                row.setdefault("id", str(uuid4()))
                now = datetime.now(timezone.utc).isoformat()
                row.setdefault("created_at", now)
                row.setdefault("updated_at", now)
                if self.table_name == "profiles":
                    row.setdefault("role", "ANALYST")
                    row.setdefault("is_active", True)
                if self.table_name == "datasets":
                    row.setdefault("columns", [])
                if self.table_name == "structuring_jobs":
                    row.setdefault("metadata_json", {})
                    row.setdefault("plan_json", [])
                    row.setdefault("history_json", [])
                rows.append(row)
                created.append(deepcopy(row))
            return FakeResponse(created)

        matched = self._matching_rows()
        total = len(matched)
        if self.action == "update":
            for row in matched:
                row.update(deepcopy(self.payload))
            matched = [deepcopy(row) for row in matched]
        elif self.action == "delete":
            for row in matched:
                rows.remove(row)
            matched = []

        if self.ordering:
            field, desc = self.ordering
            matched.sort(key=lambda row: row.get(field) or "", reverse=desc)
        if self.window:
            matched = matched[self.window[0] : self.window[1] + 1]
        if self.max_results is not None:
            matched = matched[: self.max_results]
        return FakeResponse(deepcopy(matched), total if self.with_count else None)


class FakeAuth:
    def get_user(self, token=None):
        if not token or not token.startswith("test-token:"):
            raise ValueError("Invalid test access token")
        uid, email = token.removeprefix("test-token:").split("|", 1)
        auth_user = SimpleNamespace(
            id=uid,
            email=email,
            user_metadata={"display_name": uid},
            created_at=datetime.now(timezone.utc),
        )
        return SimpleNamespace(user=auth_user)


class FakeStorageBucket:
    def __init__(self, client: FakeSupabase, name: str):
        self.client = client
        self.name = name

    def upload(self, path: str, file, _options=None):
        content = file if isinstance(file, bytes) else Path(file).read_bytes()
        self.client.objects[path] = content
        return SimpleNamespace(path=path)

    def download(self, path: str):
        if path not in self.client.objects:
            raise FileNotFoundError(path)
        return self.client.objects[path]

    def remove(self, paths: list[str]):
        for path in paths:
            self.client.objects.pop(path, None)
        return [{"name": path} for path in paths]


class FakeStorage:
    def __init__(self, client: FakeSupabase):
        self.client = client

    def from_(self, bucket: str):
        return FakeStorageBucket(self.client, bucket)


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list[dict]] = {}
        self.objects: dict[str, bytes] = {}
        self.auth = FakeAuth()
        self.storage = FakeStorage(self)

    def table(self, name: str):
        return FakeQuery(self, name)