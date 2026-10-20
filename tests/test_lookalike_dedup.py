"""Lookalike-aware deduplication tests for UPS Tracking Detailed.

Regression test for the bug seen on 2026-10-19: the pasted input contained
two copies of the same tracking number differing only in an ambiguous
character (letter O vs digit zero). The app reported "Total unique tracking
numbers: 4" and checked the same-looking number twice — [2/4] and [3/4]
showed identical numbers in the log panel.

The fix: group extracted numbers by a canonical form (uppercase, lookalike
characters O/0, I/1/l, S/5, B/8 mapped together) and keep ONE representative
per group; skipped lookalikes are reported in
UPSTrackingBot.last_dedup_report.
"""
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(REPO_ROOT, "VDS_UPS_Tracking_Detailed.py")


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("vds_ups_detailed", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCanonicalTracking:
    def test_uppercase_and_strip(self, mod):
        bot = mod.UPSTrackingBot
        assert bot.canonical_tracking(" 1zyx9y895420076449 ") == "1ZYX9Y895420076449"

    def test_letter_o_maps_to_zero(self, mod):
        bot = mod.UPSTrackingBot
        # letter O and digit 0 are the same in canonical form
        assert bot.canonical_tracking("1ZYX9Y89542O076449") == \
               bot.canonical_tracking("1ZYX9Y895420076449")

    def test_i_l_map_to_one(self, mod):
        bot = mod.UPSTrackingBot
        assert bot.canonical_tracking("1ZYX9Y895420076I49") == \
               bot.canonical_tracking("1ZYX9Y895420076149")
        assert bot.canonical_tracking("1ZYX9Y895420076l49") == \
               bot.canonical_tracking("1ZYX9Y895420076149")

    def test_s_maps_to_five_b_maps_to_eight(self, mod):
        bot = mod.UPSTrackingBot
        # S->5 and O->0 collapse onto the all-digit variant of the same body
        assert bot.canonical_tracking("1Z999AB8O123456789") == \
               bot.canonical_tracking("1Z999A880123456789")
        # genuinely different letters must NOT collapse
        assert bot.canonical_tracking("1Z999AA01234567890") != \
               bot.canonical_tracking("1Z999AB01234567890")


class TestExtractDedup:
    A = "1ZYX9Y895420076449"   # digit zero in "...200..."
    A_O = "1ZYX9Y89542O076449"  # same number, letter O instead of that zero
    B = "1ZYX9Y895420076106"
    C = "1ZYX9Y895420076252"

    def test_exact_duplicates_collapsed(self, mod):
        text = f"{self.A}\n{self.A},{self.A}\n{self.A} {self.A}"
        out = mod.UPSTrackingBot.extract_tracking_numbers(text)
        assert out == [self.A]
        assert mod.UPSTrackingBot.last_dedup_report == []

    def test_lookalike_o_variant_deduped(self, mod):
        text = (f"{self.A}\n{self.A}\n{self.A}\n{self.A}\n{self.A}\n"
                f"{self.A_O},{self.A_O}\n{self.A_O}")
        out = mod.UPSTrackingBot.extract_tracking_numbers(text)
        assert out == [self.A]  # first seen variant kept
        assert mod.UPSTrackingBot.last_dedup_report == [(self.A_O, self.A)]

    def test_lowercase_o_variant_deduped(self, mod):
        text = f"{self.A}\n{self.A_O.lower()}"
        out = mod.UPSTrackingBot.extract_tracking_numbers(text)
        assert out == [self.A]
        assert len(mod.UPSTrackingBot.last_dedup_report) == 1

    def test_distinct_numbers_all_kept(self, mod):
        text = f"{self.A}\n{self.B}\n{self.C}"
        out = mod.UPSTrackingBot.extract_tracking_numbers(text)
        assert out == [self.A, self.B, self.C]
        assert mod.UPSTrackingBot.last_dedup_report == []

    def test_order_preserved_first_seen(self, mod):
        text = f"{self.C}\n{self.A_O}\n{self.A}\n{self.B}"
        out = mod.UPSTrackingBot.extract_tracking_numbers(text)
        # C first, then A-group (first seen is A_O at index 1), then B
        assert out == [self.C, self.A_O, self.B]
        assert mod.UPSTrackingBot.last_dedup_report == [(self.A, self.A_O)]

    def test_report_cleared_between_runs(self, mod):
        mod.UPSTrackingBot.extract_tracking_numbers(f"{self.A}\n{self.A_O}")
        assert mod.UPSTrackingBot.last_dedup_report  # non-empty
        mod.UPSTrackingBot.extract_tracking_numbers(f"{self.A}\n{self.B}")
        assert mod.UPSTrackingBot.last_dedup_report == []

    def test_full_owner_scenario(self, mod):
        """The exact 2026-10-19 scenario: 3 packages, one pasted twice with
        an O/0 slip plus comma-pairs — must result in 3 checks, not 4."""
        text = (
            f"{self.A}\n{self.A}\n{self.A}\n{self.A}\n{self.A} {self.B}\n"
            + "\n".join([f"{self.B},{self.B}"] * 8) + f"\n{self.C}\n{self.C}\n"
            f"{self.A_O},{self.A_O}"
        )
        out = mod.UPSTrackingBot.extract_tracking_numbers(text)
        assert len(out) == 3
        assert out == [self.A, self.B, self.C]
