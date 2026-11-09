from datetime import date, datetime

from app.videos.finder import (
    LETSPLAY,
    REVIEW,
    find_video,
    is_english,
    mentions_game,
    normalize,
    title_variants,
)
from app.videos.youtube import PlaylistInfo, VideoInfo


def video(id, title, views, channel="Chan", channel_id="c1", embeddable=True, published=None, language=None) -> VideoInfo:
    return VideoInfo(
        id=id,
        title=title,
        channel=channel,
        channel_id=channel_id,
        views=views,
        embeddable=embeddable,
        published_at=published,
        language=language,
    )


class FakeApi:
    """Answers like YouTube from a prepared set; remembers every call."""

    def __init__(self, videos: list[VideoInfo], playlists: list[PlaylistInfo] = (), first_of_playlist: str | None = None):
        self.videos = {v.id: v for v in videos}
        self.found = [v.id for v in videos]  # what the search returns, in this order
        self.playlists = list(playlists)
        self.first_of_playlist = first_of_playlist
        self.calls: list[tuple] = []

    def search_videos(self, query, published_after=None, limit=15):
        self.calls.append(("search_videos", query, published_after))
        return self.found

    def get_videos(self, ids):
        self.calls.append(("get_videos", tuple(ids)))
        return [self.videos[i] for i in ids if i in self.videos]

    def search_playlists(self, query, channel_id, limit=5):
        self.calls.append(("search_playlists", query, channel_id))
        return self.playlists

    def first_playlist_video(self, playlist_id):
        self.calls.append(("first_playlist_video", playlist_id))
        return self.first_of_playlist


def names(api: FakeApi) -> list[str]:
    return [call[0] for call in api.calls]


def test_picks_the_most_viewed_video_about_the_game():
    api = FakeApi(
        [
            video("a", "Doom Eternal Let's Play", 1_000),
            video("b", "Doom Eternal Full Walkthrough", 50_000),
            video("c", "Quake Let's Play", 9_000_000),  # not about the game
        ]
    )
    result = find_video(api, "Doom Eternal", LETSPLAY, None)
    assert (result.video_id, result.views, result.playlist_id) == ("b", 50_000, None)


def test_the_most_viewed_is_chosen_by_the_exact_numbers_not_by_the_search_order():
    api = FakeApi([video("a", "Doom Let's Play", 10), video("b", "Doom Let's Play 2", 20)])
    assert find_video(api, "Doom", LETSPLAY, None).video_id == "b"


def test_query_and_the_start_of_the_period():
    api = FakeApi([])
    find_video(api, "Stellar Blade", LETSPLAY, date(2026, 11, 5))
    find_video(api, "Stellar Blade", REVIEW, None)
    assert api.calls[0] == ("search_videos", "Stellar Blade let's play", datetime(2026, 10, 22))
    assert api.calls[2] == ("search_videos", "Stellar Blade review", None)


def test_nothing_fits_returns_none_without_asking_for_playlists():
    api = FakeApi([video("a", "Some other game Let's Play", 100), video("b", "Doom trailer", 100)])
    assert find_video(api, "Doom", LETSPLAY, None) is None
    assert "search_playlists" not in names(api)


def test_a_video_that_cannot_be_embedded_is_skipped():
    api = FakeApi([video("a", "Doom Let's Play", 100, embeddable=False), video("b", "Doom Let's Play 2", 10)])
    assert find_video(api, "Doom", LETSPLAY, None).video_id == "b"


def test_the_kind_must_be_named_in_the_title():
    api = FakeApi([video("a", "Doom Review", 100), video("b", "Doom Let's Play", 50)])
    assert find_video(api, "Doom", REVIEW, None).video_id == "a"
    assert find_video(api, "Doom", LETSPLAY, None).video_id == "b"


def test_the_edition_suffix_and_apostrophes_do_not_hide_a_video():
    api = FakeApi([video("a", "Stellar Blade Let’s Play - Part 1", 10)])
    assert find_video(api, "Stellar Blade: Complete Edition", LETSPLAY, None) is not None
    api = FakeApi([video("a", "Marvels Guardians of the Galaxy Review", 10)])
    assert find_video(api, "Marvel's Guardians of the Galaxy: Encore Edition", REVIEW, None) is not None


def test_a_multi_part_lets_play_is_shown_by_the_first_video_of_its_playlist():
    api = FakeApi(
        [video("p7", "Doom Let's Play - Part 7", 900, channel="Ann", channel_id="ann"), video("p1", "Doom Let's Play - Part 1", 100)],
        playlists=[PlaylistInfo("other", "Another game"), PlaylistInfo("PL1", "Doom Let's Play playlist")],
        first_of_playlist="p1",
    )
    result = find_video(api, "Doom", LETSPLAY, None)
    assert (result.video_id, result.title, result.playlist_id) == ("p1", "Doom Let's Play - Part 1", "PL1")
    assert ("search_playlists", "Doom let's play", "ann") in api.calls  # the channel of the most viewed video
    assert ("first_playlist_video", "PL1") in api.calls


def test_without_a_playlist_of_the_game_the_most_viewed_video_stays():
    api = FakeApi([video("p7", "Doom Let's Play Part 7", 900)], playlists=[PlaylistInfo("x", "Other game")])
    result = find_video(api, "Doom", LETSPLAY, None)
    assert (result.video_id, result.playlist_id) == ("p7", None)


def test_if_the_first_video_cannot_be_shown_the_most_viewed_video_stays():
    api = FakeApi(
        [video("p7", "Doom Let's Play Part 7", 900), video("p1", "Doom Let's Play Part 1", 100, embeddable=False)],
        playlists=[PlaylistInfo("PL1", "Doom Let's Play")],
        first_of_playlist="p1",
    )
    result = find_video(api, "Doom", LETSPLAY, None)
    assert (result.video_id, result.playlist_id) == ("p7", None)


def test_a_single_video_let_play_and_a_review_do_not_search_playlists():
    api = FakeApi([video("a", "Doom Let's Play - Full Game", 100)])
    assert find_video(api, "Doom", LETSPLAY, None).playlist_id is None
    api = FakeApi([video("a", "Doom Review Part 1", 100)])  # a review is one video whatever its title says
    assert find_video(api, "Doom", REVIEW, None).playlist_id is None
    assert "search_playlists" not in names(api)


def test_text_helpers():
    assert normalize("Marvel’s  Game: Part 2!") == "marvels game part 2"
    assert title_variants("Stellar Blade: Complete Edition") == ["stellar blade complete edition", "stellar blade"]
    assert title_variants("Doom") == ["doom"]
    assert mentions_game("The Legend of Zelda Let's Play", ["the legend of zelda ocarina of time"]) is False


RELEASE = date(2026, 11, 5)  # the period of the videos starts 14 days earlier: 2026-10-22


def test_a_video_older_than_14_days_before_the_release_is_skipped_whatever_its_views():
    api = FakeApi(
        [
            video("old", "Doom Let's Play", 9_000_000, published=datetime(2026, 10, 21, 23, 59)),  # of the old game
            video("ok", "Doom Let's Play 2", 10, published=datetime(2026, 10, 22, 0, 0)),
        ]
    )
    assert find_video(api, "Doom", LETSPLAY, RELEASE).video_id == "ok"


def test_an_embargo_review_a_few_days_before_the_release_is_accepted():
    api = FakeApi([video("r", "Doom Review", 500, published=datetime(2026, 11, 2, 15, 0))])
    assert find_video(api, "Doom", REVIEW, RELEASE).video_id == "r"


def test_all_videos_older_than_the_period_mean_none():
    api = FakeApi([video("old", "Doom Review", 500, published=datetime(2020, 1, 1))])
    assert find_video(api, "Doom", REVIEW, RELEASE) is None


def test_the_date_is_not_checked_when_the_release_date_is_unknown():
    api = FakeApi([video("old", "Doom Review", 500, published=datetime(2020, 1, 1))])
    assert find_video(api, "Doom", REVIEW, None).video_id == "old"


def test_a_first_playlist_video_older_than_the_period_is_not_used():
    api = FakeApi(
        [
            video("p7", "Doom Let's Play Part 7", 900, published=datetime(2026, 11, 20)),
            video("p1", "Doom Let's Play Part 1", 100, published=datetime(2019, 3, 1)),  # an old game's playlist
        ],
        playlists=[PlaylistInfo("PL1", "Doom Let's Play")],
        first_of_playlist="p1",
    )
    api.found = ["p7"]  # the search found only the late part; the old first video comes from the playlist
    result = find_video(api, "Doom", LETSPLAY, RELEASE)
    assert (result.video_id, result.playlist_id) == ("p7", None)


def test_a_video_in_another_language_is_skipped_whatever_its_views():
    api = FakeApi(
        [
            video("ru", "Doom Let's Play", 9_000_000, language="ru"),
            video("es", "Doom Review", 9_000_000, language="es-419"),
            video("en", "Doom Let's Play 2", 10, language="en-GB"),
        ]
    )
    assert find_video(api, "Doom", LETSPLAY, None).video_id == "en"
    assert find_video(api, "Doom", REVIEW, None) is None


def test_the_language_tag_decides_over_the_letters_of_the_title():
    assert is_english(video("a", "Дум Let's Play", 1, language="en-US")) is True
    assert is_english(video("b", "Doom Let's Play", 1, language="de")) is False


def test_without_a_language_tag_the_title_must_be_in_latin_letters():
    assert is_english(video("a", "Doom Let's Play - Part 12: Hell #3", 1)) is True
    assert is_english(video("b", "Doom Let's Play Прохождение", 1)) is False
    assert is_english(video("c", "Doom Let's Play 実況", 1)) is False
    assert is_english(video("d", "Doom 100% — Let's Play!", 1)) is True


def test_a_russian_word_no_longer_makes_a_video_a_let_play():
    api = FakeApi([video("a", "Doom прохождение", 100), video("b", "Doom обзор", 100)])
    assert find_video(api, "Doom", LETSPLAY, None) is None
    assert find_video(api, "Doom", REVIEW, None) is None


def test_a_first_playlist_video_in_another_language_is_not_used():
    api = FakeApi(
        [video("p7", "Doom Let's Play Part 7", 900), video("p1", "Doom Let's Play Part 1", 100, language="ru")],
        playlists=[PlaylistInfo("PL1", "Doom Let's Play")],
        first_of_playlist="p1",
    )
    api.found = ["p7"]
    result = find_video(api, "Doom", LETSPLAY, None)
    assert (result.video_id, result.playlist_id) == ("p7", None)


def test_a_lets_play_without_commentary_is_not_taken_even_when_it_is_the_most_viewed():
    titles = [
        "Doom Let's Play Part 1 | No Commentary",
        "Doom Walkthrough without commentary",
        "Doom Gameplay (NC)",
        "Doom Part 1 - commentary free",
        "Doom Let's Play Part 1 no talking",
    ]
    api = FakeApi([video(f"nc{i}", title, 9_000_000 - i) for i, title in enumerate(titles)] + [video("talk", "Doom Let's Play Part 1", 1_000)])
    assert find_video(api, "Doom", LETSPLAY, None).video_id == "talk"


def test_only_commentary_free_videos_found_means_nothing_found():
    api = FakeApi([video("nc", "Doom Playthrough | No Commentary", 5_000_000)])
    assert find_video(api, "Doom", LETSPLAY, None) is None


def test_the_commentary_mark_does_not_matter_for_a_review():
    api = FakeApi([video("rev", "Doom Review - No Commentary Needed", 100)])
    assert find_video(api, "Doom", REVIEW, None).video_id == "rev"


def test_words_that_only_look_like_the_mark_are_fine():
    api = FakeApi([video("ok", "Doom Let's Play Part 1 - Commentary by Ann and the Silent Hill fans", 100)])
    assert find_video(api, "Doom", LETSPLAY, None).video_id == "ok"


def test_game_movies_are_not_taken_either():
    titles = [
        "Doom Game Movie (All Cutscenes) Full Story",
        "Doom - The Full Movie",
        "Doom All Cutscenes Walkthrough",
        "Doom Cutscenes Only Playthrough",
        "Doom GameMovie 4K",
    ]
    api = FakeApi([video(f"gm{i}", title, 9_000_000 - i) for i, title in enumerate(titles)] + [video("talk", "Doom Let's Play Part 1", 1_000)])
    assert find_video(api, "Doom", LETSPLAY, None).video_id == "talk"


def test_a_movie_in_the_name_of_the_game_is_not_a_game_movie():
    api = FakeApi([video("ok", "The Movie Game - Let's Play Part 1", 100)])
    assert find_video(api, "The Movie Game", LETSPLAY, None).video_id == "ok"
