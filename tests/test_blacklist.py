"""Unit tests for the library blacklist logic."""

from bindle.core import CORE_BLACKLIST, is_blacklisted


class TestBlacklisted:
    """All of these library names SHOULD be recognised as blacklisted."""

    def test_libc(self) -> None:
        assert is_blacklisted("libc.so.6", CORE_BLACKLIST)
        assert is_blacklisted("libc.so", CORE_BLACKLIST)

    def test_libm(self) -> None:
        assert is_blacklisted("libm.so.6", CORE_BLACKLIST)

    def test_libpthread(self) -> None:
        assert is_blacklisted("libpthread.so.0", CORE_BLACKLIST)

    def test_libdl(self) -> None:
        assert is_blacklisted("libdl.so.2", CORE_BLACKLIST)

    def test_librt(self) -> None:
        assert is_blacklisted("librt.so.1", CORE_BLACKLIST)

    def test_libgcc_s(self) -> None:
        assert is_blacklisted("libgcc_s.so.1", CORE_BLACKLIST)

    def test_libstdcpp(self) -> None:
        assert is_blacklisted("libstdc++.so.6", CORE_BLACKLIST)

    def test_ld_linux(self) -> None:
        assert is_blacklisted("ld-linux-x86-64.so.2", CORE_BLACKLIST)
        assert is_blacklisted("ld-linux.so.2", CORE_BLACKLIST)
        assert is_blacklisted("ld-linux-aarch64.so.1", CORE_BLACKLIST)

    def test_libresolv(self) -> None:
        assert is_blacklisted("libresolv.so.2", CORE_BLACKLIST)

    def test_libanl(self) -> None:
        assert is_blacklisted("libanl.so.1", CORE_BLACKLIST)

    def test_libBrokenLocale(self) -> None:
        assert is_blacklisted("libBrokenLocale.so.1", CORE_BLACKLIST)

    def test_libnsl(self) -> None:
        assert is_blacklisted("libnsl.so.1", CORE_BLACKLIST)

    def test_libutil(self) -> None:
        assert is_blacklisted("libutil.so.1", CORE_BLACKLIST)


class TestNotBlacklisted:
    """These library names SHOULD NOT be flagged as blacklisted."""

    def test_common_user_libs(self) -> None:
        assert not is_blacklisted("libssl.so.3", CORE_BLACKLIST)
        assert not is_blacklisted("libcurl.so.4", CORE_BLACKLIST)
        assert not is_blacklisted("libz.so.1", CORE_BLACKLIST)
        assert not is_blacklisted("libpcre2-8.so.0", CORE_BLACKLIST)
        assert not is_blacklisted("libfoo.so", CORE_BLACKLIST)

    def test_no_false_positives(self) -> None:
        """Prefix-based matching must not snag unrelated libraries."""

        # libc.so must not match libcrypt or libcidn
        assert not is_blacklisted("libcrypt.so.1", CORE_BLACKLIST)
        assert not is_blacklisted("libcidn.so.1", CORE_BLACKLIST)

        # libm.so must not match libmali etc.
        assert not is_blacklisted("libmali.so", CORE_BLACKLIST)

        # libstdc++.so must not match some hypothetical libstdc++foo.so
        assert not is_blacklisted("libstdc++static.a", CORE_BLACKLIST)
