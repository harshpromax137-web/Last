from app import app

routes = sorted(
    (method, route.path)
    for route in app.routes
    for method in (getattr(route, "methods", None) or set())
    if method not in {"HEAD", "OPTIONS"}
)
for method, path in routes:
    print(f"{method} {path}")

required = {
    ("GET", "/accinfo"),
    ("GET", "/info"),
    ("GET", "/stats"),
    ("GET", "/search"),
    ("GET", "/banner-image"),
    ("GET", "/outfit-image"),
    ("GET", "/api/healthz"),
    ("GET", "/refresh"),
    ("POST", "/refresh"),
}
actual = set(routes)
missing = required - actual
if missing:
    raise SystemExit(f"Missing routes: {sorted(missing)}")
print("Route validation: OK")
