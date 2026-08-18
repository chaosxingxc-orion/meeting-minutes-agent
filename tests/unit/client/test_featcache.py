from __future__ import annotations

import pytest

from meeting_minutes_agent.client.featcache import (
    LEGACY_Q4KM_PATH,
    SERVER_ENV_VAR,
    FeatCacheError,
    campaign_cache_dir,
    server_env,
)


class TestCampaignCacheDir:
    def test_resolves_and_creates_the_per_dataset_directory(self, tmp_path):
        directory = campaign_cache_dir("ami", "q4km", root=tmp_path)
        assert directory == tmp_path / "ami-q4km"
        assert directory.is_dir()

    def test_create_false_resolves_without_touching_disk(self, tmp_path):
        directory = campaign_cache_dir("earnings", "q4km", root=tmp_path, create=False)
        assert directory == tmp_path / "earnings-q4km"
        assert not directory.exists()

    def test_root_env_var_overrides_the_default_root(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MMA_FEAT_CACHE_ROOT", str(tmp_path))
        directory = campaign_cache_dir("slurp", "q4km", create=False)
        assert directory == tmp_path / "slurp-q4km"

    def test_explicit_root_wins_over_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MMA_FEAT_CACHE_ROOT", str(tmp_path / "from-env"))
        other_root = tmp_path / "explicit"
        directory = campaign_cache_dir("slurp", "q4km", root=other_root, create=False)
        assert directory == other_root / "slurp-q4km"

    def test_empty_dataset_refuses(self, tmp_path):
        with pytest.raises(FeatCacheError, match="dataset"):
            campaign_cache_dir("", "q4km", root=tmp_path, create=False)

    def test_empty_encoder_refuses(self, tmp_path):
        with pytest.raises(FeatCacheError, match="encoder"):
            campaign_cache_dir("ami", "", root=tmp_path, create=False)

    def test_dataset_named_q4km_refuses(self, tmp_path):
        with pytest.raises(FeatCacheError, match="q4km"):
            campaign_cache_dir("q4km", "anything", root=tmp_path, create=False)

    def test_dataset_named_q4km_refuses_case_insensitively(self, tmp_path):
        with pytest.raises(FeatCacheError, match="q4km"):
            campaign_cache_dir("Q4KM", "anything", root=tmp_path, create=False)

    def test_resolving_directly_under_the_legacy_root_refuses(self):
        # Any dataset/encoder pair resolved with root=LEGACY_Q4KM_PATH lands
        # nested under the SAEA legacy cache -- refused regardless of the
        # dataset/encoder names themselves.
        with pytest.raises(FeatCacheError, match="legacy"):
            campaign_cache_dir("earnings", "q4km", root=LEGACY_Q4KM_PATH, create=False)

    def test_a_dataset_named_q4km_alone_does_not_falsely_flag_unrelated_names(self, tmp_path):
        # Sanity check that the refusal is narrow: an ordinary dataset whose
        # resolved directory merely CONTAINS "q4km" as an encoder segment is
        # fine -- only the exact legacy literal (or a path nested under it)
        # and a dataset literally named "q4km" are refused.
        directory = campaign_cache_dir("earnings", "q4km", root=tmp_path, create=False)
        assert directory == tmp_path / "earnings-q4km"


class TestServerEnv:
    def test_returns_the_fixed_llama_cpp_env_var_name(self, tmp_path):
        env = server_env("ami", "q4km", root=tmp_path, create=False)
        assert env == {SERVER_ENV_VAR: str(tmp_path / "ami-q4km")}
        assert SERVER_ENV_VAR == "LLAMA_MTMD_FEAT_CACHE_DIR"

    def test_refusal_propagates_from_campaign_cache_dir(self, tmp_path):
        with pytest.raises(FeatCacheError):
            server_env("q4km", "enc", root=tmp_path, create=False)
