import os


def use_postgres():
    backend = os.environ.get(
        "DATABASE_BACKEND", "sqlite"
    ).strip().lower()

    if backend not in ("sqlite", "postgres"):
        raise RuntimeError(
            "DATABASE_BACKEND must be sqlite or postgres"
        )

    return backend == "postgres"
