#!/bin/zsh
emulate -LR zsh
set -eu
cd "${0:A:h:h}"
for script in *.sh *.zsh zsh/*.zsh bin/oh-my-usage scripts/*.sh; do
  zsh -n "$script"
done
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
