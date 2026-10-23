"""Every /admin route is admin-only, and the legacy unauthenticated client route is gone.

Written after an audit found the whole admin surface reachable without credentials: 24 write
endpoints that create, edit and delete the axes, capabilities, rubrics and quick-win templates
every assessment is scored against, plus the analytics reads. `require_admin` existed and was
used only in auth.py.

Two kinds of check, because they fail for different reasons. The structural one walks FastAPI's
resolved dependency tree, so it catches a NEW admin endpoint added without protection even if
nobody writes a test for it -- protection now comes from the router, and this asserts the router
keeps it. The behavioural one proves an unauthenticated request is actually refused.

Neither touches the database: `get_current_user` rejects a request with no credential before the
endpoint body runs, so these stay fast and need no fixtures.
"""

from __future__ import annotations

import inspect
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Anything that establishes an identity. A route is "protected" if one of these is anywhere in
# its dependency tree.
AUTH_DEPENDENCIES = {
    "get_current_user",
    "require_admin",
    "get_respondent_assessment",
}


def _dependency_names(dependant) -> set[str]:
    """Every callable in a route's resolved dependency tree, transitively.

    FastAPI flattens decorator dependencies, router-level `dependencies=` and nested
    sub-dependencies into this one tree, so it is the ground truth for what runs before the
    endpoint -- unlike reading the decorator, which misses router-level protection.
    """
    found: set[str] = set()

    def walk(dep) -> None:
        name = getattr(dep.call, "__name__", None)
        if name:
            found.add(name)
        for sub in dep.dependencies:
            walk(sub)

    walk(dependant)
    return found


def _routes():
    for route in app.routes:
        if not hasattr(route, "dependant"):
            continue
        methods = route.methods - {"HEAD", "OPTIONS"}
        if methods:
            yield route, methods


ADMIN_ROUTES = [
    pytest.param(route, sorted(methods), id=f"{sorted(methods)[0]} {route.path}")
    for route, methods in _routes()
    if route.path.startswith("/api/v1/admin")
]


def test_there_are_admin_routes_to_check():
    """Guards the two tests below: if the prefix ever changes they would silently pass on an
    empty set."""
    assert len(ADMIN_ROUTES) > 20, f"expected the admin surface, found {len(ADMIN_ROUTES)} routes"


@pytest.mark.parametrize("route,methods", [(p.values[0], p.values[1]) for p in ADMIN_ROUTES],
                         ids=[p.id for p in ADMIN_ROUTES])
def test_every_admin_route_requires_admin(route, methods):
    """A new admin endpoint is protected by the router, not by remembering to annotate it."""
    names = _dependency_names(route.dependant)
    assert "require_admin" in names, (
        f"{methods} {route.path} does not resolve require_admin. Admin routers must be declared "
        f"as APIRouter(prefix=..., dependencies=[Depends(require_admin)])."
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/admin/reference/sectors"),
        ("GET", "/api/v1/admin/analytics/overview"),
        ("GET", "/api/v1/admin/capabilities"),
        ("POST", "/api/v1/admin/reference/regions"),
        ("PATCH", "/api/v1/admin/reference/axes/1"),
        ("DELETE", "/api/v1/admin/capabilities/1"),
    ],
)
def test_admin_endpoints_refuse_an_unauthenticated_request(method, path):
    """The writes matter most: before this was fixed, an anonymous POST created a real row."""
    with TestClient(app) as client:
        response = client.request(method, path, json={"name": "should-never-be-created"})
    assert response.status_code == 401, (
        f"{method} {path} answered {response.status_code} without credentials"
    )


def test_legacy_client_turn_route_is_not_mounted():
    """`/client/turn` predates the token-scoped respondent flow and took an assessment_id straight
    from the body with no credential, so anyone could drive any assessment by guessing an integer.
    The passwordless path is /respondent/*, which resolves a token to exactly one assessment."""
    with TestClient(app) as client:
        response = client.post("/api/v1/client/turn", json={"message": "hello"})
    assert response.status_code == 404, "the legacy unauthenticated client route is reachable again"

def test_every_route_taking_a_resource_id_authorizes_it():
    """Authentication is not authorization: a signed-in consultant must not reach another's
    record by guessing an integer.

    This found one. `/assessments/interview-guide/{guide_id}/chat` took only the id and no user,
    while the guide's own GET beside it carried an explicit IDOR guard, so any signed-in user
    could read any consultant's discussion of a client's interview answers.

    The pattern list is deliberately broad: guards live variously in route `dependencies=`, in a
    module-level helper, or inline in the handler, and an earlier version of this check reported
    54 false positives by only looking in one of those places.
    """
    guards = re.compile(
        r"require_assessment_access|require_admin|_role_or_404|_require_owner|_session_or_404|"
        r"_readable\(|_owned\(|_owned_assessment_or_404|can_view|can_edit|list_visible|"
        r"visible_project|owner_id|actor_id|user\.id"
    )
    id_param = re.compile(r"\{[a-z_]*(id|key|token|ref|no)[a-z_]*\}", re.I)

    unchecked = []
    examined = 0
    for route, methods in _routes():
        if not id_param.search(route.path):
            continue
        examined += 1
        try:
            source = inspect.getsource(route.endpoint)
        except (OSError, TypeError):
            source = ""
        names = " ".join(_dependency_names(route.dependant))
        if not (guards.search(names) or guards.search(source)):
            unchecked.append(f"{sorted(methods)[0]} {route.path}")

    # Without this the test would pass on an empty set if the route table ever stopped
    # resolving -- the same trap test_there_are_admin_routes_to_check guards above.
    assert examined > 40, f"expected the id-taking surface, examined {examined} routes"

    assert not unchecked, (
        "these routes take a resource id but never check whether it belongs to the caller: "
        + ", ".join(sorted(unchecked))
    )
