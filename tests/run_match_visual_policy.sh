#!/usr/bin/env bash
set -euo pipefail
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
task_test_dir=$(mktemp -d /tmp/pes-visual-test.XXXXXX)
cd "$task_test_dir"
gcc -std=c11 -Wall -Wextra -fsanitize=undefined -I"$source_root/source" \
  "$source_root/tests/test_match_visual_policy.c" "$source_root/source/config.c" -o visual-test
./visual-test
