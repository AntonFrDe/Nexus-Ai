import pytest

from nexus.execution.expressions import (
    ExpressionError,
    check_syntax,
    evaluate,
    render_template,
)

SCOPE = {
    "input": {"score": 0.9, "tags": ["a"], "name": "ada"},
    "workflow": {"limit": 3},
    "variables": {"count": 2},
    "outputs": {"n1": {"items": [{"id": 7}]}},
}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("score > 0.8", True),
        ("score <= 0.8", False),
        ("input.score == 0.9", True),
        ("variables.count == 2 and workflow.limit >= 3", True),
        ("variables.count == 9 or not (score < 0.5)", True),
        ("tags contains 'a'", True),
        ("'b' in tags", False),
        ('name == "ada"', True),
        ("outputs.n1.items.0.id == 7", True),
        ("missing == null", True),
        ("missing > 1", False),
        ("true", True),
    ],
)
def test_evaluation(source, expected):
    assert evaluate(source, SCOPE) == expected


@pytest.mark.parametrize(
    "source",
    [
        "__import__('os').system('id')",
        "1 +",
        "(score > 1",
        "score > > 1",
        "a; b",
        "",
        "x" * 501,
    ],
)
def test_rejected_syntax(source):
    with pytest.raises(ExpressionError):
        check_syntax(source)
        evaluate(source, SCOPE)


def test_paths_read_data_only_never_python_attributes():
    assert evaluate("input.__class__", SCOPE) is None


def test_incomparable_types_are_an_expression_error():
    with pytest.raises(ExpressionError):
        evaluate("name > 1", SCOPE)


def test_templates_keep_types_for_whole_values_and_embed_in_text():
    rendered = render_template('{"total": "{{variables.count}}", "text": "hi {{name}}"}', SCOPE)
    assert rendered == {"total": 2, "text": "hi ada"}
    assert render_template("plain {{name}}", SCOPE) == "plain ada"
