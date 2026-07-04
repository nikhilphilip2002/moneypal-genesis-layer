import json
from pathlib import Path

from app.core.config import settings
from app.models.schema import RegulationCategory


def load_regulation_categories() -> list[RegulationCategory]:
    categories: list[RegulationCategory] = []
    for path in sorted(settings.registry_dir.glob("*.json")):
        with path.open("r", encoding="utf-8") as file:
            categories.append(RegulationCategory.model_validate(json.load(file)))
    return categories


def get_regulation_category(category_id: str) -> RegulationCategory:
    for category in load_regulation_categories():
        if category.id == category_id:
            return category
    raise KeyError(f"Unknown regulation category: {category_id}")


def source_paths_for_category(category: RegulationCategory) -> list[Path]:
    folder = settings.regulations_dir / category.category
    paths: list[Path] = []
    for doc in category.source_docs:
        if "*" in doc:
            paths.extend(sorted(folder.glob(doc)))
        else:
            paths.append(folder / doc)
    return paths
