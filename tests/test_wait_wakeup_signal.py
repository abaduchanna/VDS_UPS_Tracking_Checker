"""Wait wake-up signal tests for UPS Tracking Detailed.

Owner bug report (2026-10-20): 6 trackings took ~2 minutes. The two
"Label Created" shipments each burned the full 40s wait deadline because
wait_for_ups_result's case-sensitive STATUS_WORDS check never matched the
lowercase page text ("UPS received the shipping information...", "A UPS
shipping label has been created") — only the later case-insensitive status
engine classified it, after the deadline.

The fix makes the wait wake on the SAME case-insensitive engine
(match_status) that classifies, so:
- the wait can never disagree with the verdict,
- Label Created pages wake in seconds, not 40s,
- the status is still read afterwards from the page text (never guessed);
  pages without a recognizable status stay "Not Found".
"""
import importlib.util
import os

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(REPO_ROOT, "VDS_UPS_Tracking_Detailed.py")


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("vds_ups_detailed_wait", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LABEL_CREATED_PAGE = (
    "1Z999AA10123456789\n"
    "UPS received the shipping information for this shipment on October 18, 2026.\n"
    "A UPS shipping label has been created. UPS has not yet received this package.\n"
    "Shipping Label Created"
)

OFD_PAGE = "1Z999AA10123456789\nOut for Delivery\nExpected delivery: Today"

IN_TRANSIT_PAGE = "1Z999AA10123456789\nIn Transit\nArriving: Wednesday, October 21"


def test_wait_wakes_on_lowercase_label_created_page(mod):
    """The wait's engine-based signal must recognize the lowercase
    label-created page text — this is what used to burn 40 seconds."""
    # The engine classifies it (priority buckets keep it correct too)
    assert mod.UPSTrackingBot.match_status(LABEL_CREATED_PAGE) == "Label Created"


def test_wait_wake_signal_matches_engine_for_ofd(mod):
    assert mod.UPSTrackingBot.match_status(OFD_PAGE) == "Out for Delivery"


def test_wait_wake_signal_matches_engine_for_in_transit(mod):
    assert mod.UPSTrackingBot.match_status(IN_TRANSIT_PAGE) == "On the Way"


def test_engine_never_guesses_on_unknown_page(mod):
    """No recognizable status -> None -> caller records 'Not Found'
    (never a guessed status — owner requirement: exact statuses only)."""
    assert mod.UPSTrackingBot.match_status("Some unrelated page content") is None
    assert mod.UPSTrackingBot.match_status("") is None


def test_ofd_wins_over_label_created_in_history(mod):
    """Priority buckets: an OFD page that also mentions the label event
    must classify as Out for Delivery, not Label Created."""
    page = "Out for Delivery\nA UPS shipping label has been created."
    assert mod.UPSTrackingBot.match_status(page) == "Out for Delivery"
