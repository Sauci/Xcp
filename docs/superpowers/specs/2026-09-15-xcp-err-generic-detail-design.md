# ERR_GENERIC's implementation-specific detail — closing D17

**Defect:** D17 — `ERR_GENERIC` never carries its extended payload
(`docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` §3).

**Reference revision:** XCP Part 2 Protocol Layer Specification 1.1, read alongside 1.0. Every
citation carries its revision prefix. Where the two differ it is said so; where they agree, that
agreement was checked rather than assumed.

---

## 1. What is wrong, and what the specification does *not* say

1.1/§1.1.3.3 names two payload-bearing error codes. D6 closed the first. The second:

> If the error code is 0x31 = ERR_GENERIC, the error packet contains an implementation specific
> slave device error code as WORD as additional information.

1.0/§1.1.3.3 is word-for-word identical. This is not a revision difference.

All five sites answering `ERR_GENERIC` call plain `Xcp_FillErrorPacket`, so no WORD is ever
attached. The `UNLOCK` branch's own comment cites that very sentence as its justification for
*choosing* the code, then omits the payload the sentence describes.

**The specification deliberately declines to define the value.** "Implementation specific" hands
the choice to whoever writes the slave, which is this module. There is nothing to look up and no
conformance answer to find: the values below are invented here, and that is what the specification
asks for.

---

## 2. Decisions

**DD121 — the WORD carries module-defined detail, not the integrator's status byte.** Three of the
five sites are integrator-callback failures whose `pStatusCode` is already in hand and currently
discarded, so forwarding it is the superficially obvious reading of "implementation specific". It
is rejected because that byte has no defined meaning. `interface/Xcp.h` documents every
`pStatusCode` as "zero for success, non-zero for failure" and then pins only the *error code* a
non-zero value produces — `ERR_GENERIC` for `Xcp_ProgramStart`/`Xcp_ProgramPrepare`,
`ERR_ACCESS_DENIED` for `Xcp_ProgramClear`/`Xcp_ProgramWrite`, `ERR_VERIFY` for
`Xcp_ProgramVerify`. **Nothing anywhere constrains what a non-zero value may be.** Forwarding it
would retroactively turn an unconstrained boolean into a wire-visible protocol field: every
existing integrator's arbitrary `1` would become a value a master may interpret, and the module
would publish a number it neither defines nor controls.

**DD122 — a flat vocabulary, with no range reserved for integrator-defined codes.** Reserving the
upper half of the space would hedge against DD121 rather than commit to it. If integrator-defined
codes are ever wanted, that is a design with its own questions — how the two halves are told apart,
what an integrator must document, what happens to an unrecognised value — and it belongs in that
design, not pre-empted here. The 16-bit space is vast and five values are trivial to renumber while
no master depends on them.

**DD123 — `0x0000` is reserved and never emitted.** A zeroed or stale buffer must not decode as a
valid detail code. Same reasoning as `checksum_max_block_size`'s `minimum: 1` (DD116): a field
whose "absent" value is indistinguishable from a real one cannot be trusted by a reader.

**DD124 — the definitions live in a fenced block inside `interface/Xcp_Errors.h`.** That file is
today uniformly ASAM-defined: nineteen codes, each carrying a `(see ASAM protocol layer
specification 1.7.3.1)` citation, reaching integrators through `interface/Xcp.h:52`. Adding
module-invented values risks blurring what the specification mandates with what this module chose.

It goes there anyway, because the deciding audience is whoever holds a captured `FE 31 00 03` and
needs to know what `0x0003` means. They will look where `0x31` is defined. A second header serves
file purity at the direct expense of that lookup. The file is also already less uniform than it
appears — the `RESOURCE_TEMPORARY_NOT_ACCESSIBLE` entry carries six lines naming DD101,
`Xcp_CTOCmdStdGetStatus` and the integrator callback that resolves it.

The fence must make provenance unmissable: a banner stating these are **not** ASAM-defined, that
1.1/§1.1.3.3 leaves the value implementation-specific, and that this module is the implementation
defining them.

**DD125 — one shared helper, not five copies.** Each site otherwise needs the same three lines: a
two-byte buffer, `Xcp_CopyFromU16WithOrder`, then `Xcp_FillErrorPacketWithData`. Five verbatim
copies of a logic block is a defect the review rubric names explicitly. Unlike D6's
`Xcp_BuildChecksumFillMaxBlockSize`, which was file-local `static` because one site used it, this
one spans `source/Xcp_Std.c` and `source/Xcp_Pgm.c` and must be shared.

---

## 3. Behaviour

Packet layout, unchanged from 1.1/§1.1.3.3: byte 0 `0xFE`, byte 1 `0x31`, **bytes 2–3 the WORD**,
written with `Xcp_CopyFromU16WithOrder` against the configured `byteOrder` — the same call
`GET_STATUS` already uses for the session configuration id. Four bytes total.

**It always fits.** `config/xcp.schema.json` sets `max_cto` `"minimum": 8`, so no schema-valid
configuration has fewer than eight bytes of CTO. (D6's eight-byte payload sits exactly at that
floor; this one is well inside it.)

| Value | Name | Emitted when |
|:--|:--|:--|
| `0x0001u` | `XCP_GENERIC_DETAIL_KEY_CALCULATION_FAILED` | `UNLOCK`: `Xcp_CalcKey` returned `E_NOT_OK` |
| `0x0002u` | `XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE` | `PROGRAM_START` with `pgm_state != XCP_PGM_IDLE` |
| `0x0003u` | `XCP_GENERIC_DETAIL_PROGRAM_START_FAILED` | `Xcp_ProgramStart` reported non-zero status |
| `0x0004u` | `XCP_GENERIC_DETAIL_PROGRAM_RESET_FAILED` | `Xcp_ProgramReset` reported non-zero status |
| `0x0005u` | `XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED` | `Xcp_ProgramPrepare` reported non-zero status |

Names deliberately sit outside `XCP_E_`, which is already overloaded — `XCP_E_ASAM_*` for wire
codes, `XCP_E_*` for DET diagnostics. A third meaning under that prefix would be the worst option
available.

**What the last three actually deliver.** The integrator's own byte stays boolean and is still
discarded (DD121). What the master gains is *which callback failed* — information it could not
previously recover, because all three answered an identical two-byte packet. In particular a
`PROGRAM_START` refused by the module's own state gate (`0x0002`) is now distinguishable from one
refused by the integrator (`0x0003`), which is the pair most likely to send a diagnosing engineer
to the wrong side of the interface.

**What this does not change.** `ERR_GENERIC`'s prescribed master action remains "restart session"
in every 1.7.3.2 row carrying it. The WORD is diagnostic information attached to a response that
still tells the master to tear down the connection; it shortens the diagnosis, it does not soften
the outcome.

### The helper

```c
void Xcp_FillGenericErrorPacket(const uint16 detail, PduInfoType *pPduInfo);
```

Defined in `source/Xcp.c` immediately after `Xcp_FillErrorPacketWithData` (which ends at `:2700`),
declared in `source/Xcp_Internal.h` beside its siblings at `:935-936`. It writes the WORD in the
configured byte order and delegates, so `Xcp_FillErrorPacketWithData` stays the single place that
knows an error packet's payload starts at byte 2.

---

## 4. Testing

**Five assertion sites across three files change.** Every one uses the `[0:2]` slice idiom, which
**cannot see a payload** — so none of them fails when the WORD is added. They would keep passing
while proving nothing about it. Each therefore gains an `SduLength == 4` assertion *and* the
expected detail value, exactly as D6's payload tests did and for the same reason.

**How the length is asserted, corrected.** An earlier draft of this section said each site "gains
an `SduLength == 4` assertion" without checking what those sites can reach. They cannot reach it:
all three files read responses through helpers that return **decoded tuples, not `PduInfoType`** —
`pgm_deferred_test.py`'s `transmitted()` returns `tuple(...SduDataPtr[0:8])`, `pgm_session_test.py`'s
`send()` delegates to it, and `seed_key_defects_test.py`'s `exchange(handle, request, length=3)`
returns a byte slice. `SduLength` appears in none of the three.

Widening those helpers would touch every caller across three files, far outside this defect. So the
length is asserted **directly at the mock**, beside the existing helper call, following the idiom
already established at `daq_identification_field_test.py:281`:

```python
assert handle.can_if_transmit.call_args[0][1].SduLength == 4
```

This is additive and changes no helper.

**The length assertion is not optional.** `SduDataPtr` always holds a full `MAX_CTO`-sized frame
padded with `trailingValue`, so bytes 2–3 read out of a `[0:8]` tuple are present whether or not the
module wrote them. A module that produced the right WORD but finalised the packet at length 2 would
pass a value-only assertion. The length check is what distinguishes "the WORD was written" from
"the buffer happened to contain those bytes".

| File:line | Test | Expected detail |
|:--|:--|:--|
| `seed_key_defects_test.py:579` | `..._calc_key_fails_answers_an_error_instead_of_a_stale_positive_response` | `0x0001` |
| `seed_key_defects_test.py:650` | `..._does_not_leave_a_stale_answer_for_whatever_reads_it_next` | `0x0001` |
| `pgm_deferred_test.py:308` | `test_a_failing_integrator_yields_err_generic_and_leaves_the_session_closed` | `0x0003` |
| `pgm_deferred_test.py:660` | `test_a_failing_program_reset_yields_err_generic_and_does_not_disconnect` | `0x0004` |
| `pgm_session_test.py:553` | `test_program_prepare_answers_err_generic_on_a_non_zero_status_code` | `0x0005` |

**`pgm_session_test.py:796` is deliberately left alone.** Its `(0xFE, 0x31)` sits inside
`test_a_mid_session_synch_does_not_end_the_programming_session`, whose subject is
`Xcp_PgmAbandonPendingCommand` and DD55. The assertion exists to prove *the session never ended*,
using a second `PROGRAM_START`'s refusal as the observable — the error code is incidental to it.
Coupling it to this vocabulary would make an unrelated test fail the next time this design changes.
It matched the grep; that is not a reason to amend it.

**Coverage gap to close.** `0x0002` — `PROGRAM_START` refused because a session is already active —
is exercised today only by `pgm_session_test.py:796`, the test just excluded. It needs an assertion
of its own rather than borrowing one, so this adds a test for that condition, asserting the code,
the length and the detail value.

**Byte order.** At least one site is parametrized over both byte orders so the WORD's encoding is
checked against the configured order rather than the host's.

---

## 5. Out of scope, and one finding recorded in passing

Out of scope: any use of the integrator's `pStatusCode` value (DD121), and any reserved range for
integrator-defined codes (DD122).

**`Xcp_FinalizeResPacket` does not clamp `startIndex` to `maxCto`.** It sets
`SduLength = startIndex` and pads from there to `maxCto`, so a payload longer than `MAX_CTO` would
report an `SduLength` the 1.1/§1.1.3.3 layout (`2..MAX_CTO-1`) forbids. **This is latent, not live:**
the schema's `max_cto` `"minimum": 8` means no schema-valid configuration can reach it, for this
four-byte packet or for D6's eight-byte one. Recorded because the guarantee currently rests
entirely on that schema bound — nothing in `source/` enforces it — and because the next payload
added may not be so comfortably inside the floor.
