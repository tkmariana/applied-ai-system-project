from rag import load_corpus, retrieve


def test_corpus_loads_all_sources():
    sources = {c.source for c in load_corpus()}
    assert {"dog.md", "cat.md", "other.md", "general.md"} <= sources


def test_dog_query_returns_dog_chunk_first():
    hits = retrieve("how long should I walk my dog", species="dog")
    assert hits and hits[0].source == "dog.md"


def test_species_filter_excludes_other_species():
    hits = retrieve("litter box scoop", species="dog")
    assert all(h.source in ("dog.md", "general.md") for h in hits)


def test_cat_litter_query():
    assert retrieve("litter box", species="cat")[0].source == "cat.md"


def test_unrelated_query_returns_empty():
    assert retrieve("quantum chromodynamics lagrangian", species="dog") == []


def test_empty_query_returns_empty():
    assert retrieve("the a of", species="dog") == []
