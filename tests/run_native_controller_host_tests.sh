#!/usr/bin/env bash
set -euo pipefail

source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
task_test_dir=$(mktemp -d /tmp/pes-native-controller-test.XXXXXX)
trap 'rm -rf "$task_test_dir"' EXIT
cd "$task_test_dir"

gcc -std=c11 -Wall -Wextra -fsanitize=undefined \
  -I"$source_root/source" \
  "$source_root/tests/test_native_pad_routing.c" -lm -o native-pad-test
./native-pad-test

gcc -std=c11 -Wall -Wextra -fsanitize=undefined \
  -I"$source_root/source" \
  "$source_root/tests/test_friend_press.c" -o friend-press-test
./friend-press-test

gcc -std=c11 -Wall -Wextra -fsanitize=undefined \
  -I"$source_root/source" \
  "$source_root/tests/test_match_visual_policy.c" \
  "$source_root/source/config.c" -o visual-policy-test
./visual-policy-test
