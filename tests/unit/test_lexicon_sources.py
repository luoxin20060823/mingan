from audit.lexicon_sources import load_builtin_seed


def test_load_builtin_seed_prefers_explicit_lexicon_dir(tmp_path):
    seed = tmp_path / "seed.csv"
    seed.write_text(
        "word,category,level\n"
        + "\n".join(f"CSV词{i},其他,提示" for i in range(1000)),
        encoding="utf-8",
    )
    lexicon_dir = tmp_path / "Vocabulary"
    lexicon_dir.mkdir()
    (lexicon_dir / "其他词库.txt").write_text(
        "\n".join(f"真实词{i}" for i in range(1000)),
        encoding="utf-8",
    )

    rows = load_builtin_seed(str(seed), str(lexicon_dir))

    words = {word for word, _, _ in rows}
    assert "真实词0" in words
    assert "CSV词0" not in words
