#!/bin/sh
# Opens a SEPARATE Chrome profile the autopilot can control (macOS).
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/easyleadz-chrome" https://www.linkedin.com/feed/
