"""The acquisition step, run against the synthetic archive through curl's file:// support, so
that the whole path from listing to verified tables is exercised without the network."""
import hashlib, json
import restart.acquire as A


def _tree(archive, sha):
    return [dict(type="file", path="README.md", size=10),
            dict(type="file", path="synthetic_4runs_mini.tar.gz", size=5, lfs=dict(oid="x", size=5)),
            dict(type="file", path="synthetic_4runs.tar.gz", size=archive.stat().st_size,
                 lfs=dict(oid=sha, size=archive.stat().st_size))]


def test_selects_full_archives_only(synthetic_archive):
    rows = A.full_archives(_tree(synthetic_archive, "abc"))
    assert [r["name"] for r in rows] == ["synthetic_4runs.tar.gz"] and rows[0]["sha256"] == "abc"


def test_streams_verifies_and_discards_the_copy(synthetic_archive, config_name, tmp_path, monkeypatch):
    sha = hashlib.sha256(synthetic_archive.read_bytes()).hexdigest()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(A, "listing", lambda: _tree(synthetic_archive, sha))
    monkeypatch.setattr(A, "FILE", f"file://{synthetic_archive.parent}/{{name}}")
    assert A.main(["--out", "derived"]) == 0
    out = tmp_path / "derived" / "synthetic_4runs"
    assert json.load(open(out / f"audit_{config_name}.json"))["archive_sha256"] == sha
    assert not (tmp_path / "archives" / ".partial" / "synthetic_4runs.tar.gz").exists()
    assert f"{sha}  synthetic_4runs.tar.gz" in (tmp_path / "archives" / "SHA256SUMS").read_text()


def test_a_wrong_checksum_keeps_the_copy(synthetic_archive, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(A, "listing", lambda: _tree(synthetic_archive, "0" * 64))
    monkeypatch.setattr(A, "FILE", f"file://{synthetic_archive.parent}/{{name}}")
    assert A.main(["--out", "derived"]) == 1
    kept = tmp_path / "archives" / ".partial" / "synthetic_4runs.tar.gz"
    assert kept.read_bytes() == synthetic_archive.read_bytes()
    assert "synthetic_4runs" not in (tmp_path / "archives" / "SHA256SUMS").read_text()


def test_the_copy_is_complete_when_extraction_fails(tmp_path):
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not a gzip stream" * 100000)
    with open(tmp_path / "log", "w") as log:
        got = A.stream(["cat", str(bad)], tmp_path / "copy", tmp_path / "out", log)
    assert got["source_rc"] == 0 and got["extract_rc"] != 0
    assert (tmp_path / "copy").read_bytes() == bad.read_bytes()


def test_a_local_copy_is_used_when_present(synthetic_archive, config_name, tmp_path, monkeypatch):
    sha = hashlib.sha256(synthetic_archive.read_bytes()).hexdigest()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(A, "listing", lambda: _tree(synthetic_archive, sha))
    monkeypatch.setattr(A, "FILE", "file:///nonexistent/{name}")          # would fail if used
    assert A.main(["--out", "derived", "--local", str(synthetic_archive.parent)]) == 0


def test_a_verified_checksum_is_recorded_even_when_nothing_extracts(tmp_path, monkeypatch):
    import io, tarfile
    odd = tmp_path / "odd_4runs.tar.gz"                       # a layout with no <config>-run_N folders
    with tarfile.open(odd, "w:gz") as tf:
        ti = tarfile.TarInfo("odd/elsewhere/output.jsonl"); ti.size = 2
        tf.addfile(ti, io.BytesIO(b"{}"))
    sha = hashlib.sha256(odd.read_bytes()).hexdigest()
    tree = [dict(type="file", path="odd_4runs.tar.gz", size=odd.stat().st_size, lfs=dict(oid=sha, size=1))]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(A, "listing", lambda: tree)
    assert A.main(["--out", "derived", "--local", str(tmp_path)]) == 1            # nothing extracted
    assert f"{sha}  odd_4runs.tar.gz" in (tmp_path / "archives" / "SHA256SUMS").read_text()


def test_sums_only_restores_the_checksums_without_extracting(synthetic_archive, tmp_path, monkeypatch):
    import io, tarfile
    sha = hashlib.sha256(synthetic_archive.read_bytes()).hexdigest()
    local = tmp_path / "dl"; local.mkdir()
    odd = local / "odd_4runs.tar.gz"                          # did not extract: hashed from the local copy
    with tarfile.open(odd, "w:gz") as tf:
        ti = tarfile.TarInfo("odd/elsewhere/output.jsonl"); ti.size = 2
        tf.addfile(ti, io.BytesIO(b"{}"))
    odd_sha = hashlib.sha256(odd.read_bytes()).hexdigest()
    tree = _tree(synthetic_archive, sha) + [dict(type="file", path="odd_4runs.tar.gz", size=1,
                                                lfs=dict(oid=odd_sha, size=1))]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(A, "listing", lambda: tree)
    monkeypatch.setattr(A, "FILE", f"file://{synthetic_archive.parent}/{{name}}")
    assert A.main(["--out", "derived", "--only", "synthetic_4runs.tar.gz"]) == 0
    sums = tmp_path / "archives" / "SHA256SUMS"
    sums.write_text("# header only\n")                          # as an old copy would leave it
    monkeypatch.setattr(A, "listing", lambda: (_ for _ in ()).throw(AssertionError("no network")))
    (tmp_path / "archives" / "hf_tree.json").write_text(json.dumps(tree))
    before = sorted(p.name for p in (tmp_path / "derived" / "synthetic_4runs").iterdir())
    assert A.main(["--sums-only", "--out", "derived", "--local", str(local)]) == 0
    text = sums.read_text()
    assert f"{sha}  synthetic_4runs.tar.gz" in text and f"{odd_sha}  odd_4runs.tar.gz" in text
    assert sorted(p.name for p in (tmp_path / "derived" / "synthetic_4runs").iterdir()) == before
    (tmp_path / "archives" / "hf_tree.json").write_text(json.dumps(_tree(synthetic_archive, "0" * 64)))
    assert A.main(["--sums-only", "--out", "derived"]) == 1                  # a mismatch is not recorded
