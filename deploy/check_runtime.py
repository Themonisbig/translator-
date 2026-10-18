"""Check installed requirements, honoring only upstream's explicit protobuf override."""
from importlib.metadata import distributions, version, PackageNotFoundError
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

errors = []
for dist in distributions():
    for raw in dist.requires or []:
        req = Requirement(raw)
        if req.marker and not req.marker.evaluate({"extra": ""}):
            continue
        try:
            installed = version(req.name)
        except PackageNotFoundError:
            errors.append(f"{dist.metadata['Name']} requires missing {req.name}")
            continue
        if installed not in req.specifier:
            # Kept exactly as the official uv.lock/pyproject.toml specify.
            if (canonicalize_name(dist.metadata['Name']) == "descript-audiotools"
                    and canonicalize_name(req.name) == "protobuf" and installed == "5.29.6"):
                print("Applied official Fish override: descript-audiotools uses protobuf 5.29.6 (<6).")
                continue
            errors.append(f"{dist.metadata['Name']} requires {req}, installed {installed}")
if errors:
    raise SystemExit("\n".join(errors))
print("Runtime requirements verified against the official lockfile overrides.")
