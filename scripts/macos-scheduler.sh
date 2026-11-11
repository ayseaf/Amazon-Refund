#!/bin/sh
# Phase 1 refusal script. launchd must not be loaded yet.
# If this file is started anyway, it does not check prices and does not contact Amazon.
echo "Phase 1: background price monitoring is not enabled and will not contact Amazon." >&2
exit 1
