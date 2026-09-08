#!/bin/sh
# Final review F1 (.superpowers/sdd/2026-09-07-xcp-pgm-sp4b/final-review.md).
#
# Nothing before this script ever asked CMake itself to compile the Xcp target with
# programming.enabled effectively true. The shipped config/xcp.json keeps the gate off, and
# test/conftest.py's own MockGen supplies XCP_MAX_CTO/XCP_PGM_MAX_BLOCK_SIZE straight to the CFFI
# compiler for every PGM test -- a path that goes around this project's own CMakeLists.txt wiring
# entirely, so 12000+ green pytest cases proved nothing about whether `cmake .. && make` can still
# produce this build. It could not: both macros reach only the generated Xcp_Cfg.h, which
# source/*.c never includes, and neither was on the Xcp target's own compiler command line.
#
# This script is that missing proof, run as its own ctest (Xcp_GateOnCompiles, CMakeLists.txt) so
# an ordinary green ./test.sh means this ran too. A nested, isolated configure+build of the real
# Xcp target, in its own build directory so it cannot disturb the caller's own XCP_ENABLE_TEST/
# XCP_PYTEST_ARGS-scoped cache, with XCP_FLASH_PROGRAMMING_ENABLED forced ON over the UNMODIFIED
# default XCP_CONFIG_FILEPATH -- whose own protocol_layer.max_cto and programming.max_block_size
# still feed XCP_MAX_CTO/XCP_PGM_MAX_BLOCK_SIZE exactly as they would for a real gate-on
# configuration, since that derivation reads every configuration's max_cto/max_block_size
# regardless of programming.enabled's own value. Compiling one translation unit's worth of macros
# from the shipped file rather than authoring a synthetic gate-on configuration keeps this script
# from becoming a second, independently-maintained copy of what a gate-on configuration looks
# like -- exactly the kind of drift this whole review is about.
#
# Deliberately narrow: this proves compilability, nothing about wire behaviour -- the generated
# Xcp_Cfg.c this nested build links against still reports every PGM ctoInfo entry disabled, since
# regenerating it is driven by the JSON configuration's own programming.enabled, not by this
# script's compiler-only override. Wire-level gate-on behaviour is exhaustively covered by the
# CFFI-driven pytest suite (pgm_*.py) instead; this script exists solely to catch what that suite
# cannot, by construction: a macro CMakeLists.txt forgot to wire onto the real compiler command
# line.
set -e

project_dir="$1"
work_dir="$2"
cmake_command="$3"

rm -rf "${work_dir}"

"${cmake_command}" -S "${project_dir}" -B "${work_dir}" \
    -DXCP_ENABLE_TEST=ON -DXCP_FLASH_PROGRAMMING_ENABLED=ON
"${cmake_command}" --build "${work_dir}" --target Xcp
