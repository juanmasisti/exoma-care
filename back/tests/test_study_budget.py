import pytest

from app.domain.entities.budget import Budget, calculate_budget, combine_genes


def genes(count, prefix="G"):
    return [f"{prefix}{number}" for number in range(1, count + 1)]


@pytest.mark.parametrize("count", [1, 3, 4, 5])
def test_up_to_five_genes_cost_the_flat_base_price(count):
    budget = calculate_budget(genes(count))
    assert budget == Budget(count, 500, 0, 0, 500)


def test_sixth_gene_adds_thirty_dollars():
    budget = calculate_budget(genes(6))
    assert (budget.extra_genes, budget.extra_amount, budget.total) == (1, 30, 530)


def test_each_extra_gene_adds_thirty_dollars():
    budget = calculate_budget(genes(8))
    assert (budget.base_amount, budget.extra_genes, budget.extra_amount, budget.total) == (500, 3, 90, 590)


def test_shared_genes_are_counted_once():
    # Dos patologías que comparten GAA y un adicional repetido: 5 genes distintos.
    pathology_a = ["GAA", "GLA", "GBA"]
    pathology_b = ["GAA", "IDUA"]
    additional = ["gla", " BRCA1 "]
    assert calculate_budget(combine_genes(pathology_a, pathology_b, additional)).total == 500
    assert combine_genes(pathology_a, pathology_b, additional) == ("GAA", "GLA", "GBA", "IDUA", "BRCA1")


def test_duplicates_do_not_push_the_study_over_five_genes():
    budget = calculate_budget(["GAA"] * 10 + genes(4))
    assert (budget.gene_count, budget.total) == (5, 500)


def test_gene_symbols_are_compared_case_insensitively():
    assert combine_genes(["gaa"], ["GAA"], [" Gaa "]) == ("GAA",)


def test_study_without_genes_cannot_be_budgeted():
    with pytest.raises(ValueError):
        calculate_budget([])


def test_blank_gene_symbol_is_rejected():
    with pytest.raises(ValueError):
        combine_genes(["GAA", "   "])
