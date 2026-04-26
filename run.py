#!/usr/bin/env python3
"""Entry-point for the OpenRouter top-bar tracker."""

import signal
import sys

# Graceful Ctrl-C handling in GTK
signal.signal(signal.SIGINT, signal.SIG_DFL)

from openrouter_tracker.indicator import OpenRouterIndicator


def main() -> int:
    indicator = OpenRouterIndicator()
    indicator.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
