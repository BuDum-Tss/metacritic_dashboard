"""Subtitles come as a line every second or two; the transcript joins them into sentences."""

from app.transcripts.captions import MAX_SENTENCE_CHARS, Segment, merge_sentences


def pieces(*items):
    return [Segment(start, text) for start, text in items]


def test_pieces_are_joined_up_to_the_end_of_the_sentence():
    merged = merge_sentences(pieces((0, "So here we are"), (2, "in front of the elephants."), (5, "Cool guys!"), (7, "Really")))
    assert [(s.start, s.text) for s in merged] == [
        (0, "So here we are in front of the elephants."),
        (5, "Cool guys!"),
        (7, "Really"),
    ]


def test_closing_quotes_and_brackets_do_not_hide_the_end():
    merged = merge_sentences(pieces((0, 'He said "go."'), (3, "Then (he left.)"), (6, "Next")))
    assert [s.text for s in merged] == ['He said "go."', "Then (he left.)", "Next"]


def test_text_without_punctuation_is_cut_by_length():
    words = [(i * 2, "word " * 10) for i in range(30)]
    merged = merge_sentences([Segment(start, text.strip()) for start, text in words])
    assert len(merged) > 1
    assert all(len(s.text) <= MAX_SENTENCE_CHARS for s in merged)
    assert " ".join(s.text for s in merged).split() == " ".join(t for _, t in words).split()


def test_text_without_punctuation_is_cut_by_time():
    merged = merge_sentences(pieces((0, "a"), (10, "b"), (20, "c"), (30, "d"), (40, "e")))
    assert [(s.start, s.text) for s in merged] == [(0, "a b c"), (30, "d e")]


def test_nothing_gives_nothing():
    assert merge_sentences([]) == []


def test_the_speaker_change_marker_ends_the_sentence_and_is_dropped():
    merged = merge_sentences(pieces((0, "so we go"), (2, ">> What now"), (4, "my friend? >> Nothing"), (6, ">>> Ok.")))
    assert [(s.start, s.text) for s in merged] == [(0, "so we go"), (2, "What now my friend?"), (4, "Nothing"), (6, "Ok.")]
    assert not any(">" in s.text for s in merged)
