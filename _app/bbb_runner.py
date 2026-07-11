"""Small compatibility launcher for bbb-dl.

The TUES site can require the same Referer/User-Agent as the authenticated
playback page. bbb-dl already reads the local Netscape cookie file; this
launcher adds those two ordinary request headers before invoking its pinned CLI.
"""

from __future__ import annotations

import os

from bbb_dl.main import BBBDL, main


def run() -> None:
    referer = os.getenv("ECHOWRAITH_BBB_REFERER", os.getenv("EFSANE_BBB_REFERER", "")).strip()
    user_agent = os.getenv("ECHOWRAITH_BBB_USER_AGENT", os.getenv("EFSANE_BBB_USER_AGENT", "")).strip()
    if referer:
        BBBDL.headers["Referer"] = referer
    if user_agent:
        BBBDL.headers["User-Agent"] = user_agent
    main()


if __name__ == "__main__":
    run()
