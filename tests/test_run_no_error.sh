#!/usr/bin/env bash
set -xe

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

for sample in $(ls $SCRIPT_DIR/samples/linux)
do
  cat $SCRIPT_DIR/samples/linux/$sample | poetry run tokei-pie -o $sample.html
done
