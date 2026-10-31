from functools import lru_cache

import yaml


@lru_cache
def load_semantic_layer() -> dict:
    with open("configs/semantic_layer.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dimensions() -> dict:
    return load_semantic_layer()["dimensions"]


def metrics() -> dict:
    return load_semantic_layer()["metrics"]

