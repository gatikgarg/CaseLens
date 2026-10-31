from backend.app.documents import chunker
from backend.app.documents.chunker import Turn, chunk_turns

# Force the offline tokenizer so tests never hit the network.
chunker._tok = chunker._FallbackTokenizer()


def test_small_turns_share_one_chunk():
    turns = [Turn(1, "customer", "cannot log in"), Turn(2, "agent", "please restart")]
    chunks = chunk_turns(turns, "Ticket 1 | Auth | High")
    assert len(chunks) == 1
    text, used = chunks[0]
    assert "cannot log in" in text
    assert used == turns


def test_chunk_boundary_respected_and_overlap():
    turns = [Turn(i, "customer", "word " * 60) for i in range(1, 6)]
    chunks = chunk_turns(turns, "Header", max_tokens=40, overlap_turns=1)
    assert len(chunks) > 1
    # Overlap of one turn means the second chunk starts with the last turn of the first.
    assert chunks[1][1][0].seq == chunks[0][1][-1].seq


def test_long_turn_is_not_split():
    turns = [Turn(1, "customer", "word " * 100)]
    chunks = chunk_turns(turns, "Header", max_tokens=20)
    assert len(chunks) == 1

