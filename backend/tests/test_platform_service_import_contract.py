import importlib


def test_platform_exports_are_resolvable():
    platform_pkg = importlib.import_module("app.services.platform")
    assert hasattr(platform_pkg, "AsyncUnitOfWork")
    assert hasattr(platform_pkg, "idempotent_request")
