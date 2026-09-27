from hr_agent.handbook import MAX_RESULTS, score_section, search_handbook


def test_carryover_query_ranks_carryover_section_first() -> None:
    result = search_handbook("PTO carryover")
    assert result["status"] == "success"
    assert result["results"][0]["section"] == "PTO carryover"
    assert "March 31" in result["results"][0]["text"]


def test_results_are_capped_and_ordered_by_relevance() -> None:
    result = search_handbook("PTO days carry over approval")
    assert result["status"] == "success"
    assert len(result["results"]) <= MAX_RESULTS


def test_no_match_lists_available_sections() -> None:
    result = search_handbook("dental insurance")
    assert result["status"] == "not_found"
    assert "PTO carryover" in result["available_sections"]


def test_empty_and_stopword_only_queries_are_errors() -> None:
    assert search_handbook("")["status"] == "error"
    assert search_handbook("what is the")["status"] == "error"


def test_title_match_outweighs_body_match() -> None:
    assert score_section({"remote"}, "Remote work", "x") > score_section(
        {"remote"}, "Other", "remote"
    )


def test_natural_language_question() -> None:
    result = search_handbook("How many sick days do I get?")
    assert result["results"][0]["section"] == "Sick leave"
