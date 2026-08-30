import pytest

from app.services.assessment_service import (
    MINIMUM_SCORE,
    QUESTION_BANKS,
    course_requires_assessment,
    grade_answers,
    public_questions,
)


ASSESSMENT_COURSE_CODES = [
    "NR-06-F",
    "NR-10-B",
    "NR-10-S",
    "NR-12-F",
    "NR-33-AUT",
    "NR-35-F",
]


@pytest.mark.parametrize("course_code", ASSESSMENT_COURSE_CODES)
def test_configured_nr_courses_have_versioned_question_banks(course_code):
    assert course_requires_assessment(course_code) is True
    assert len(QUESTION_BANKS[course_code]) == 5
    questions = public_questions(course_code)
    assert len(questions) == 5
    assert all("correct" not in question for question in questions)
    assert all(len(question["options"]) >= 2 for question in questions)


@pytest.mark.parametrize("course_code", ASSESSMENT_COURSE_CODES)
def test_correct_answers_pass_and_are_graded_server_side(course_code):
    answers = {item["id"]: item["correct"] for item in QUESTION_BANKS[course_code]}
    correct, total, score, passed = grade_answers(course_code, answers)
    assert correct == total == 5
    assert score == 100.0
    assert passed is True


def test_nr10_variants_require_final_assessment():
    assert course_requires_assessment("NR-10-B") is True
    assert course_requires_assessment("NR-10-S") is True


def test_demo_policy_blocks_score_below_minimum():
    course_code = "NR-06-F"
    bank = QUESTION_BANKS[course_code]
    # Two correct answers out of five => 40%, below the demo policy threshold.
    answers = {
        item["id"]: item["correct"] if index < 2 else (item["correct"] + 1) % len(item["options"])
        for index, item in enumerate(bank)
    }
    correct, total, score, passed = grade_answers(course_code, answers)
    assert correct == 2
    assert total == 5
    assert score == 40.0
    assert score < MINIMUM_SCORE
    assert passed is False


def test_unconfigured_course_does_not_silently_get_assessment():
    assert course_requires_assessment("NR-99") is False
    with pytest.raises(ValueError):
        grade_answers("NR-99", {})
