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
variant group, not across all variants — `Xcp_Daq.c` and `Xcp_DaqRuntime.c` report the 24-module
timestamp-enabled variant, and the other 12 modules' coverage of the disabled variant is real but not
folded in. gcov offers no way to combine them. An honest 92.42% beats a silent 0.00%.

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
