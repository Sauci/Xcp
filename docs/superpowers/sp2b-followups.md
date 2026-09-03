# SP2b follow-ups

Carried out of SP2b's execution ledger before that scratch workspace was deleted. The whole-branch
review triaged these and recommended they land as a hygiene branch rather than gate SP2b's merge.
Nothing here is a correctness defect in shipped behaviour.

## Closed before merge — coverage reporting for `Xcp_Daq.c`

`test.sh` reported `source/Xcp_Daq.c` at 0.00% of 422 lines with `Xcp_Daq.gcda:stamp mismatch with
notes file`. Fixed on this branch; recorded here because the mechanism generalises.

[#4](https://github.com/Sauci/Xcp/pull/4) merged gcov profiles by choosing **one seed** module — the
directory with the most `.gcda` files — and pairing every file's merged profile with that seed's
notes. That is correct only while each source compiles **identically** in every module. SP2b broke
the assumption: `XCP_DAQ_TIMESTAMP_SUPPORTED` gates `Xcp_DTOCmdDaqGetDaqClock` in or out, so
`Xcp_Daq.c` compiles two different function sets (`.gcno` of 33044 and 33844 bytes), and gcov cannot
merge profiles from structurally different compilations. `gcov-tool merge` replaced the seed's
profile with the other variant's, whose stamp then mismatched the seed's notes.

`Xcp_DaqRuntime.c` has the same two-variant property (8180 / 9488) and was reporting correctly only
by luck of which variant the seed happened to hold.

The merge is now **per source file**: group modules by that file's `.gcno` content, merge the largest
group, pair with that group's notes. With a single variant the largest group is every module, so #4's
behaviour is preserved rather than replaced.

**Residual, by design and documented in the code:** reported coverage is the union across the largest
variant group, not across all variants. gcov offers no way to combine them. An honest 92.42% beats a
silent 0.00%.

**Corrected in the round-2 fix wave — this paragraph previously stated the residual inverted.** It
said `Xcp_Daq.c` and `Xcp_DaqRuntime.c` report "the 24-module timestamp-**enabled** variant". It is
the opposite, and the inversion mattered: most test configurations declare no
`protocol_layer.timestamp` block, so the majority group is the timestamp-**disabled** compilation.
`build/Xcp_DaqRuntime.c.gcov` marks every line inside `#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)`
as `-` — not compiled, rather than uncovered — so its headline `100.00% of 105` is 100% of a
compilation containing none of SP2b's feature. `Xcp_Daq.c`'s uncovered lines are almost entirely the
new timestamp code, at `#####`.

The split is also not two-way. `Xcp_Daq.gcno` sizes fell into four groups (33044 ×24, 33736 ×1,
33756 ×2, 33844 ×9), so the losing side is itself several unmergeable groups and no selection rule
recovers the union; each new build-time gate erodes it further. `test.sh` now prints the winning
`.gcno`'s byte size and the number of variants present alongside the module count, and says outright
that the figure is one variant's, so a `100.00%` that omits a feature cannot be read as a clean bill
of health.

Still open: nothing folds the variants together, and nothing fails when the *measured* variant is the
one without the feature under test. A per-variant report, or a coverage gate keyed on the winning
`.gcno` size, would close it.

## Test hygiene

- `test_only_the_first_odt_of_a_cycle_carries_a_timestamp` asserts frame lengths only; the
  configured clock value is never compared against ODT 0's bytes, so reserving four bytes and
  filling them with garbage passes.
- `test/get_daq_event_info_test.py`'s `EVENT_CHANNEL_NAME_LENGTH == 0` assertion for
  `publish_names: false` is vacuous — the preceding `set_mta` already zero-filled that byte.
- `test/daq_timestamp_test.py`'s first two assertions are `MagicMock` tautologies that never cross
  the CFFI boundary; the sibling test below them does.
- `WRITE_DAQ_MULTIPLE`'s one-byte positive response is already `0xFF` from the preceding
  `SET_DAQ_PTR`, and no test in that file resets `can_if_transmit` or checks `call_count`, so
  deleting the success arm passes every test in the file.
- Five new `response()` helpers never `reset_mock()`, unlike `DaqSession.exchange` in
  `daq_acceptance_test.py`, which is the pattern they copied. This is the enabling condition for
  several of the items above.
- All ten `pytest.raises(UndefinedError)` generation-failure tests are mutually indistinguishable,
  because `raise` is not a registered Jinja global and every guard surfaces the same
  `'raise' is undefined`. Asserting that the same configuration succeeds once the offending field is
  corrected would discriminate; only one of the ten does that today.
- Coverage gaps judged low risk: no `BIG_ENDIAN` ticks case with a clock configured; "once per cycle
  per list" is untested with more than one list; no 1-byte `WRITE_DAQ_MULTIPLE` request test.

## Consistency and documentation

- The `BYTE`/`WORD`/`DWORD` → 1/2/4 wire-size mapping has **eight** independent copies plus the C
  `switch`, and four more identification-field/address-granularity copies keyed on the same strings.
  Two are structurally dead — changing `WORD → 3` in `CMakeLists.txt` passes the entire suite. The
  consolidation CMake ≥ 3.19 now makes possible is a JSON table that `string(JSON ... GET)`,
  `json.load` and the Jinja environment all read.
- `config/xcp.json` declares no `timestamp` block, so the CMake derivation and its test are not
  load-bearing on the shipped configuration.
- `Xcp_CTOErrorMatrix[0xC7]` declares `ACCESS_DENIED | ACCESS_LOCKED`; `[0xD7]`, `[0xD8]`, `[0xDB]`
  and `[0xDC]` do not, though all five are `MASK_DAQ` and can answer `ERR_ACCESS_LOCKED`.
  Documentation-only, but the five new commands are inconsistent with each other.
- `Xcp_DTOCmdDaqGetDaqEventInfo` is the only handler in its file without the
  `uint8 error` / `if (error == 0)` idiom.
- Design §7.1 prescribes `ERR_OUT_OF_RANGE` for a `WRITE_DAQ_MULTIPLE` length/`n` disagreement; the
  implementation answers `ERR_CMD_SYNTAX`. Defensible, but the document and the code disagree.
- Design §5.2's table still says `ERR_OUT_OF_RANGE` for the `WRITE_DAQ` overfill row, which SP2b
  overturned to `ERR_DAQ_CONFIG` to match the shipped SP2a behaviour and its existing test.
- `test/parameter.py`'s `timestamp_type_name` has no consumer.
- Two comment inaccuracies: a `SET_DAQ_LIST_MODE` comment says the RUNNING check is "two branches
  above" the budget check when it is four; a `get_daq_list_info_test.py` docstring cites a
  DAQ-capable precedent in `Xcp_CanIfRxIndication` that does not exist — that code checks
  `STIM || DAQ_STIM`.

## Robustness, deliberately deferred

- `odtEntrySizeDaq - timestampWireSize` underflows **permissively** in two places
  (`Xcp_DaqOdtEntryBudget` and `Xcp_DTOCmdDaqSetDaqListMode`) — the capacity check silently passes
  rather than fails. A generation guard makes both unreachable, but the guard lives in a different
  file from the arithmetic; a comment at each site naming the guard it depends on would stop a
  future template edit silently arming them.
- A malformed `protocol_layer.timestamp` block — present but missing `size`, or a configuration with
  no `protocol_layer` at all — yields a silent OFF/0 from the CMake derivation where the previous
  inline Python raised. Schema-guarded, so reachable only with a schema-invalid config file.
- `READ_DAQ` has no `XCP_DAQ_LIST_MODE_RUNNING` check, so it succeeds and advances the shared DAQ
  pointer in a state where `SET_DAQ_PTR` and `WRITE_DAQ` both answer `ERR_DAQ_ACTIVE`. Harmless
  today — read-only, and nothing in the sampler reads the pointer — and consistent with the error
  matrix, but undocumented and untested.
- A timestamped DAQ list whose ODT 0 holds no entries transmits no timestamp at all, silently:
  `Xcp_DaqSampleOdt` returns `E_NOT_OK` for an empty ODT so the frame is never queued. Reachable and
  legal per the specification. Needs a decision — emit ODT 0 for the timestamp alone, or refuse the
  mode — rather than a mechanical fix.
- `script/source_rt.c.jinja2`'s `Xcp_DtoFrameStrideCheck` asserts `XCP_MAX_DTO ==` this
  configuration's `max_dto` inside a per-configuration loop, but `XCP_MAX_DTO` is a **max** fold, so
  any two-configuration file with differing `max_dto` fails to compile. `>=` is the correct
  relation. Same family as the literal-suffix template bug SP2b's two-configuration fixture
  uncovered; it caps how far that fixture can be pushed.
- `header_cfg.h.jinja2`'s own `any`/`max` folds remain unasserted for multi-configuration input:
  both probe tests pass a single configuration, and in the compiled two-configuration module the
  harness's `-D` pre-empts the header's blocks.

## Infrastructure

`test.sh` should prune stale `_cffi_xcp_*` module directories **at the start of a run**, before
`cmake` — it cannot prune at the end, because its coverage merge depends on them surviving. They
reached 3017 directories (307 MB) against the container's 1024 file-descriptor limit during SP2b and
are the documented common cause of five transient failures, each of which cost a full four-minute
run and none of which reproduced. The modules are keyed by digest and rebuilt on demand, so clearing
them is safe. Raising the image's FD limit is worth doing as well, but treats the symptom.

---

# Round-2 review, consolidated fix wave

A second independent review of the branch, in two lenses. Everything below either landed on this
branch or is recorded here because it did not.

## Fixed on this branch

- **`PID_OFF` enforced only half of §1.1.2.1.** DD20 justified checking only `maxOdt == 1` by
  claiming the transport-layer half — "separate CAN-Ids for each DAQ list" — held by construction,
  since each list gets one TX PDU. One PDU per list is not a *distinct* PDU per list: the schema has
  no `uniqueItems` on `pdu_mapping`, and `config/xcp.json` maps both its lists to
  `XCP_PDU_ID_TRANSMIT`. `SET_DAQ_LIST_MODE` now also refuses `PID_OFF` when another list shares this
  list's `dto[0].dto2PduMapping.txPdu.id`. DD20 records the correction rather than the original
  claim.
- **Out-of-bounds read via `max_odt: 0`.** The ODT-0 timestamp capacity check indexed `odt[0]` with
  no `maxOdt` bound — the module's only `.odt[` site bounded by neither `maxOdt` nor `SET_DAQ_PTR`.
  Guarded at the call site; a zero-ODT list now answers `ERR_OUT_OF_RANGE` for `TIMESTAMP`.
- **The CMake derivation was latched in the cache.** `option()` / `set(... CACHE ...)` no-op once the
  entry exists, so editing `XCP_CONFIG_FILEPATH` could not move `XCP_PAGING_SUPPORTED`,
  `XCP_DAQ_TIMESTAMP_SUPPORTED` or `XCP_DAQ_TIMESTAMP_SIZE` in an existing build directory — while
  `generated/CMakeLists.txt` regenerated `Xcp_Cfg.c` from the new file anyway. Now derived through
  `xcp_derive_from_configuration`, which shadows the last derived value so `FORCE` can update it
  without clobbering an explicit `-D`; `CMAKE_CONFIGURE_DEPENDS` makes the configure step re-run.
- **`odtEntrySizeDaq` truncated without a guard**, and the sibling `counters.odt > 255` guard was
  dead (shadowed by the stricter PID ceiling in an earlier template loop). Both corrected, with the
  docstring that reasoned about them as independent ceilings.
- **`daqs[].type: "STIM"` refused at generation**, rather than emitting `DAQ_LIST_PROPERTIES == 0x00`
  — an encoding §1.6.4.2.2.1 marks "Not allowed".
- **`READ_DAQ`'s `ERR_OUT_OF_RANGE`** kept, but recorded as a deliberate deviation: §1.7.3.2.4 does
  not list that code for `READ_DAQ`, and its only listed alternative prescribes recovery advice
  ("retry other syntax") that cannot repair a pointer.
- **The coverage merge reported the timestamp-disabled variant**, and this document said the
  opposite. Both corrected; see the section above.
- **`test_max_daq_list_reports_the_full_reference_count_at_the_byte_boundary`'s docstring** claimed a
  change no test can observe. Corrected to claim only the boundary check it performs.

## Found in this wave and not fixed

- **AddressSanitizer never runs.** `test/conftest.py`'s `_asan_flags` is gated on `XCP_ASAN=1` and
  off by default, and the image is Alpine/musl, where it is not readily available. The round-2 review
  assumed "the harness compiles with ASAN"; it does not. One half of
  `test_enabling_timestamp_is_refused_for_a_list_with_no_odt` (`max_odt_entries=4`, the actual
  out-of-bounds read) therefore cannot fail on the default suite — its docstring says so. A CI job on
  a glibc image with `XCP_ASAN=1` would make that half, and any future memory-safety test, real.
- **The schema still permits `max_odt: 0` and `max_odt_entries: 0`.** Now harmless — the C guard
  covers the one unbounded site, and every other `.odt[` index is bounded — but a DAQ list with no
  ODT can do nothing, and nothing tells the integrator so. Raising the minimum to 1 was rejected
  here because the schema is enforced only on the CMake path: `test/conftest.py` bypasses it, and the
  README documents building these sources under a different build system entirely, so a schema
  minimum would have left the read reachable exactly where it was reachable.
- **The schema still permits two DAQ lists to name the same `pdu_mapping`**, deliberately — it is
  legal and useful for lists that keep their identification field. But the refusal it now causes
  surfaces only at runtime, as `ERR_MODE_NOT_VALID` from `SET_DAQ_LIST_MODE`; an integrator who wants
  `PID_OFF` gets no warning at generation. A generation-time *warning* (not an error) naming the
  lists that share a PDU would close the gap; a hard guard would not, since `pdu_mapping` is a macro
  name the preprocessor resolves.
- **`xcp_derive_from_configuration` cannot distinguish an explicit `-D` that agrees with the
  derivation** from the derivation itself, so such an override is followed if the configuration later
  changes. Re-passing the `-D` pins it again. Documented at the function.
- **`Xcp_DTOCmdDaqGetDaqListInfo`'s DAQ-bit condition now has an unreachable false arm**, since
  `STIM` is refused at generation and both remaining types are DAQ-capable. Kept, with a comment
  naming the guard it depends on, because SP3 lifts that guard. The test that used to pin the
  condition says plainly that it no longer can.
- **`PID_OFF_SUPPORTED` in `DAQ_PROPERTIES` is not narrowed by the PDU-sharing rule.** It is a
  property of the slave, not of a list, so a configuration where some lists have an exclusive TX PDU
  and others do not has no single honest answer. A master may therefore see `PID_OFF_SUPPORTED` set
  and still be refused per list. Recorded in DD20.
- **Two transient failures reproduced during this wave** —
  `daq_acceptance_test.py::test_a_dto_filled_to_capacity_has_every_byte_in_place[AG = BYTE-MAX_DTO =
  016d]` and `daq_configuration_test.py::test_configured_timestamp_reaches_the_generated_
  configuration[BYTE-ONE_BYTE-1]` — each passing on an immediate re-run of the same selection. Same
  signature as the five recorded under *Infrastructure* above; the stale `_cffi_xcp_*` prune is still
  the fix.
