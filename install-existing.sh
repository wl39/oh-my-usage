#!/bin/sh
exec "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/install.sh" existing "$@"
