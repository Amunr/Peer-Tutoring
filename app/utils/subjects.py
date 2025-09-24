from __future__ import annotations

from typing import Iterable, List, Tuple

from ..models import Subject


def group_subjects(subjects: Iterable[Subject]) -> List[Tuple[str, List[Subject]]]:
    grouped: List[Tuple[str, List[Subject]]] = []
    current_category: str | None = None
    bucket: List[Subject] = []
    for subject in subjects:
        if subject.category != current_category:
            if bucket:
                grouped.append((current_category or '', bucket))
            current_category = subject.category
            bucket = []
        bucket.append(subject)
    if bucket:
        grouped.append((current_category or '', bucket))
    return grouped
