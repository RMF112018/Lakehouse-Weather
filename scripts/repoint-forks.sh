#!/usr/bin/env bash
set -euo pipefail

OWNER="${1:-RMF112018}"

cat <<MSG
This script repoints modifiable submodules to user-owned forks.
It does not create the forks; create them first on GitHub.
Owner: $OWNER
MSG

git config -f .gitmodules submodule.vendor/weewx-sdr.url "https://github.com/${OWNER}/weewx-sdr.git"
git config -f .gitmodules submodule.vendor/weewx-belchertown-new.url "https://github.com/${OWNER}/weewx-belchertown-new.git"
git submodule sync -- vendor/weewx-sdr vendor/weewx-belchertown-new

echo "Repointed weewx-sdr and weewx-belchertown-new fork URLs in .gitmodules."
