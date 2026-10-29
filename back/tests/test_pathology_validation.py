import pytest

from app.domain.entities.pathology import (
    PathologyDefinition,
    validate_clinical_suspicion,
)


@pytest.fixture
def pathology():
    # IDs ficticios: no representan asociaciones clínicas reales.
    return PathologyDefinition("Patología de prueba", 1, frozenset({2, 3, 4}))


@pytest.mark.parametrize(
    "symptoms, valid, criterion, secondary",
    [
        ([1], True, "cardinal", ()),
        ([2, 3], True, "two_secondary", (2, 3)),
        ([2, 3, 4], True, "two_secondary", (2, 3, 4)),
        ([1, 2], True, "cardinal", (2,)),
        ([], False, "insufficient_symptoms", ()),
        ([2], False, "insufficient_symptoms", (2,)),
        ([2, 2], False, "insufficient_symptoms", (2,)),
        ([2, 999], False, "insufficient_symptoms", (2,)),
        ([998, 999], False, "insufficient_symptoms", ()),
    ],
)
def test_individual_suspicion(pathology, symptoms, valid, criterion, secondary):
    result = validate_clinical_suspicion(pathology, symptoms)
    assert result.valid is valid
    assert result.criterion == criterion
    assert result.matched_secondary_ids == secondary
    assert result.matched_cardinal is (1 in symptoms)


def test_cardinal_cannot_be_secondary():
    with pytest.raises(ValueError, match="cardinal"):
        PathologyDefinition("Prueba", 1, frozenset({1, 2}))


def test_pathology_requires_name():
    with pytest.raises(ValueError, match="nombre"):
        PathologyDefinition("  ", 1, frozenset())
