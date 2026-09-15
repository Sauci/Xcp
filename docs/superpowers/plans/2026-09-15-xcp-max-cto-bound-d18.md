# D18 — MAX_CTO's unenforced payload bound: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the relationship between `MAX_CTO` and the payloads this module attaches to a
response a checked one — at generation for the payloads the module chooses, at runtime for the one
it does not.

**Architecture:** Two halves, split by who chooses the length. The three error payloads are
compile-time constants, so `script/source_cfg.c.jinja2` refuses a configuration whose own `max_cto`
cannot hold the largest of them; no runtime branch is added, because none could ever be entered.
`USER_CMD`'s length comes from the integrator's callback at runtime, so `Xcp_DTOCmdStdUserCmd`
checks it and refuses an over-long response with `ERR_GENERIC` plus a detail WORD and a Det report.

**Tech Stack:** C (AUTOSAR-style BSW), Jinja2 code generation, CMake, pytest + CFFI compiling the
real C sources, Docker (Alpine) for the test run.

**Spec:** `docs/superpowers/specs/2026-09-15-xcp-max-cto-bound-d18-design.md` (DD126–DD131). Read it
first; every decision below argues from it.

## Global Constraints

- **Reference revision:** XCP Part 2 Protocol Layer Specification **1.1**, cited as `1.1/§x.y.z`.
  Cite 1.0 only where it differs. Comments in this codebase carry the citation with its revision.
- **Branch:** `fix/xcp-max-cto-bound-d18`, already created, design doc already committed on it.
- **The floor is 8.** `MAX_CTO >= 8` is what the largest error payload requires:
  `Xcp_BuildChecksumFillMaxBlockSize` (`source/Xcp_Std.c`) hands the helper **six** bytes — the
  reserved WORD 1.1/§1.6.1.2.9 puts at positions 2,3 plus the DWORD at 4..7 — written flat from
  position 2.
- **Tests run in Docker only.** A host run is a false pass. The image `xcp-test:local` is already
  built from this branch's `Dockerfile`; do not rebuild it. The house invocation, used by every
  prior sub-project in this repository, sets the cache variable with `cmake` and then runs
  `./test.sh` (which prunes stale CFFI module directories and merges coverage — running `ctest`
  directly skips both):
  ```bash
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
  ```
  Narrow a run by putting a `-k` expression in the cache variable, semicolon-separated:
  `-DXCP_PYTEST_ARGS="-k;max_cto_bound"`.
- **`XCP_PYTEST_ARGS` is a CMake cache variable** (`CMakeLists.txt:17`) and therefore **sticky**: it
  persists in `build/` until explicitly reset. To narrow a run, configure it once inside the
  container; to go back to the full suite, reset it with `-DXCP_PYTEST_ARGS=`. The final
  verification of every task is a full `./test.sh` with the cache cleared.
- **No new dead code.** DD126 rejects runtime guards that no configuration can enter; this project
  has shipped two such guards before and removed both.
- **Commit style:** `type: imperative summary`, body explaining the reasoning, and the trailer
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`. Push after each commit.

---

## File Structure

| File | Change | Responsibility |
|:--|:--|:--|
| `test/max_cto_bound_test.py` | create | The generation guard's two tests — the refusal and the paired acceptance that identifies it |
| `script/source_cfg.c.jinja2` | modify (after the `WRITE_DAQ_MULTIPLE` guard, currently line 855) | Refuse a configuration whose `max_cto` cannot hold the largest error payload |
| `source/Xcp.c` | modify (`Xcp_FillErrorPacketWithData` ~2688, `Xcp_FillGenericErrorPacket` ~2703, `Xcp_CTOErrorMatrix[0xF1]` line 1001) | Name the guard the copy loop depends on; declare `ERR_GENERIC` in `USER_CMD`'s row |
| `interface/Xcp_Errors.h` | modify (end of the `XCP_GENERIC_DETAIL_*` block, before `#endif`) | Define detail code `0x0006` |
| `interface/Xcp.h` | modify (after `XCP_E_IDENTIFICATION_NOT_GRANULAR`) | Define Det id `0x0A` |
| `source/Xcp_Std.c` | modify (`Xcp_DTOCmdStdUserCmd`) | The runtime check and the refusal |
| `test/user_cmd_test.py` | modify (append) | The three `USER_CMD` cases |
| `test/stub/Xcp_UserCmd.h` | modify | Replace the stale copied doc comment with the real contract, bound included |
| `README.md` | modify (new section before `## Flash programming`, line 349) | Tell integrators the bound and what violating it produces |
| `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` | modify (§3 D18, §1 test count) | Close D18 with its outcome |

---

### Task 1: The generation guard for module-chosen payloads

**Files:**
- Create: `test/max_cto_bound_test.py`
- Modify: `script/source_cfg.c.jinja2` (immediately after the `WRITE_DAQ_MULTIPLE` guard at line 855)
- Modify: `source/Xcp.c` (comments at `Xcp_FillErrorPacketWithData` and `Xcp_FillGenericErrorPacket`)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: the guarantee Task 2 relies on — that `Xcp_Ptr->general->maxCto >= 8` in every generated
  configuration, so the `ERR_GENERIC` packet Task 2 builds (4 bytes) always fits.

- [ ] **Step 1: Write the failing tests**

Create `test/max_cto_bound_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

from jinja2.exceptions import UndefinedError

import pytest

from .parameter import *
from .conftest import XcpTest


def test_generation_refuses_a_max_cto_below_the_error_payload_floor():
    """XCP part 2 - Protocol Layer Specification 1.1/1.1.3.3 puts an error packet's optional data at
    positions 2..MAX_CTO-1, and 1.1/1.6.1.2.9 puts BUILD_CHECKSUM's maximum block size at 4..7, so
    the largest error packet this module builds is 8 bytes. Nothing in source/ checks it:
    Xcp_FillErrorPacketWithData (source/Xcp.c) copies its payload with no comparison against
    maxCto, and Xcp_FinalizeResPacket cannot catch an over-long packet afterwards because its own
    padding loop simply does not execute. That is D18. The check therefore lives at generation,
    where the payload sizes are known constants (DD126).

    A constraint between a configuration field and the module's own constants, which is why it is
    not in config/xcp.schema.json: test/conftest.py bypasses the schema and would not see it.
    """
    with pytest.raises(UndefinedError):
        XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=7))


def test_generation_accepts_the_smallest_max_cto_that_holds_every_error_payload():
    """The companion the rejection above needs to mean anything. `raise` is a deliberately-undefined
    Jinja global, so every guard in that template surfaces the identical "'raise' is undefined" and
    pytest.raises(UndefinedError) alone cannot show which one fired, or that the configuration was
    not refused for an unrelated reason. 8 is the floor exactly, so this pair brackets it."""
    XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))
```

**Do not add a test that drives an over-long *error* payload.** There is no way to write one: with
the guard in place, no configuration — schema-valid or test fixture — can build a module whose
constants exceed the bound, which is the point of enforcing it at generation (spec §4).

- [ ] **Step 2: Run the tests and verify the first fails**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;max_cto_bound" && cd .. && ./test.sh'
```

Expected: `test_generation_refuses_a_max_cto_below_the_error_payload_floor` FAILS with
`DID NOT RAISE <class 'jinja2.exceptions.UndefinedError'>` — generation currently accepts
`max_cto=7`. The acceptance test passes already; that is fine and expected.

- [ ] **Step 3: Add the guard**

In `script/source_cfg.c.jinja2`, directly after the `WRITE_DAQ_MULTIPLE` guard that ends at line 857
(`{%- endif %}`), insert:

```jinja
{#- D18: the payloads this module attaches to an error packet are constants, so the bound between
    them and MAX_CTO is checkable here rather than at runtime, where no configuration could ever
    enter the branch (DD126). Each configuration's OWN max_cto, never XCP_MAX_CTO, which is a max()
    fold over every configuration in the generated file and would prove only that the largest one
    fits (DD127). #}
{%- if configuration.protocol_layer.max_cto < 8 %}
{{ raise('MAX_CTO is {}, but the largest error packet this module builds is 8 bytes: XCP part 2 1.1/1.6.1.2.9 puts the maximum block size BUILD_CHECKSUM reports at positions 4..7, inside the 2..MAX_CTO-1 payload area 1.1/1.1.3.3 defines. Xcp_FillErrorPacketWithData (source/Xcp.c) copies that payload with no bound of its own, which is defect D18; raising MAX_CTO to 8 or more is what makes it safe. A payload larger than six bytes added later must raise this floor with it -- see docs/superpowers/specs/2026-09-15-xcp-max-cto-bound-d18-design.md'.format(configuration.protocol_layer.max_cto)) }}
{%- endif %}
```

Note: no apostrophes inside the message — the surrounding Jinja string is single-quoted, as the
neighbouring guards are.

- [ ] **Step 4: Run the tests and verify both pass**

Same command as Step 2. Expected: both tests in `max_cto_bound_test.py` PASS.

- [ ] **Step 5: Move the init test above the floor**

`test_xcp_init_raises_e_init_failed_if_max_cto_parameter_does_not_fit_with_address_granularity`
(`test/asam_protocol_layer_test.py`) configures `max_cto` of 1 and 3 to reach `Xcp_Init`'s
`(maxCto % element_size) == 0` check (`source/Xcp.c:1262`). The guard you just added refuses to
generate those, so the test would now fail at `XcpTest(...)` construction instead of exercising what
it exists to exercise. Move its parametrisation above the floor — the values must still violate the
relation:

```python
# The values are at or above 8 and still fail the modulo: 9 % 2, 11 % 2, 9 % 4 and 10 % 4 are all
# non-zero. Below 8 they cannot be generated at all -- an error packet carrying BUILD_CHECKSUM's
# maximum block size needs MAX_CTO >= 8 (XCP part 2 1.1/1.6.1.2.9, D18), and
# script/source_cfg.c.jinja2 refuses the configuration before Xcp_Init ever runs. This test's own
# point is MAX_CTO not dividing the address granularity's element size, which these keep. Do not
# simplify this back to 1 -- the same reason the max_dto sibling below carries.
@pytest.mark.parametrize('max_cto, address_granularity', ((9, 'WORD'),
                                                          (11, 'WORD'),
                                                          (9, 'DWORD'),
                                                          (10, 'DWORD')))
```

Leave the body of the test and its `max_dto` sibling untouched. If a moved case now fails for a
reason other than `XCP_E_INIT_FAILED` — a different generator guard, say — report it rather than
tuning the numbers until it passes: the controller needs to know.

- [ ] **Step 6: Name the guard where the arithmetic lives**

In `source/Xcp.c`, immediately above `Xcp_FillErrorPacketWithData`'s copy loop:

```c
    /* This loop has no bound of its own, and Xcp_FinalizeResPacket cannot add one afterwards: its
     * padding loop runs from startIndex to maxCto and simply does not execute when startIndex is
     * already past it. The bound is enforced at generation instead --
     * script/source_cfg.c.jinja2 refuses a configuration whose max_cto cannot hold the largest
     * payload any caller here passes, which is BUILD_CHECKSUM's six bytes from position 2
     * (XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.9, 1.1/1.1.3.3). A larger payload
     * added later must raise that floor in the same commit. D18, DD126-DD128. */
```

And above `Xcp_FillGenericErrorPacket`'s body, one line inside the existing comment block:

```c
 * The two-byte payload is inside the MAX_CTO floor the generation guard in
 * script/source_cfg.c.jinja2 enforces (D18, DD128).
```

- [ ] **Step 7: Run the full suite with the cache cleared**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: the whole suite passes. Comments do not change behaviour, but the guard does — a
configuration somewhere in the fixtures may set a `max_cto` below 8, and if one does, that is the
guard working and the fixture needs correcting, not the guard.

- [ ] **Step 8: Commit and push**

```bash
git add test/max_cto_bound_test.py test/asam_protocol_layer_test.py script/source_cfg.c.jinja2 source/Xcp.c
git commit -m "fix: refuse a MAX_CTO that cannot hold the largest error payload"
git push
```

---

### Task 2: `USER_CMD` refuses an over-long response

**Files:**
- Modify: `interface/Xcp_Errors.h` (after `XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED`, before `#endif`)
- Modify: `interface/Xcp.h` (after `XCP_E_IDENTIFICATION_NOT_GRANULAR`)
- Modify: `source/Xcp.c` (`Xcp_CTOErrorMatrix` row `0xF1`, line 1001)
- Modify: `source/Xcp_Std.c` (`Xcp_DTOCmdStdUserCmd`)
- Modify: `test/stub/Xcp_UserCmd.h`
- Test: `test/user_cmd_test.py` (append)

**Interfaces:**
- Consumes: Task 1's guarantee that `maxCto >= 8`, so the 4-byte `ERR_GENERIC` packet always fits.
- Produces: `XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG` (`0x0006u`, `interface/Xcp_Errors.h`) and
  `XCP_E_USER_CMD_RESPONSE_TOO_LONG` (`0x0Au`, `interface/Xcp.h`) — Task 3 documents both.

- [ ] **Step 1: Write the failing tests**

The spec's third case — a response *shorter* than MAX_CTO is untouched — is already covered by
`test_user_cmd_function_returns_the_user_defined_buffer`, which parametrizes `sdu_length` 1 through
8, so do not re-add it. The boundary test below overlaps that test's `sdu_length=8` row
deliberately: it is the only one asserting that the exactly-at-MAX_CTO case reaches the wire
*without* a Det report, which is what an off-by-one in the new comparison would break.

Append to `test/user_cmd_test.py`:

```python
def test_user_cmd_refuses_a_response_longer_than_max_cto():
    """The integrator's callback is the only place a response length reaches this module from
    outside, and nothing checked it: Xcp_DTOCmdStdUserCmd finalized whatever SduLength came back, so
    a frame longer than the 2..MAX_CTO-1 layout of XCP part 2 - Protocol Layer Specification
    1.1/1.1.3.3 reached CanIf. Refused rather than truncated (DD129): a user-defined payload carries
    no length field, so a clamped response is indistinguishable from a complete one."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

    def xcp_user_cmd_function(_p_cmd_pdu_info, p_res_err_pdu_info):
        p_res_err_pdu_info[0].SduLength = 0x09
        for i in range(0x09):
            p_res_err_pdu_info[0].SduDataPtr[i] = 0xAA
        return handle.define('E_OK')

    handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    response = tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:4])

    assert response[0:2] == (0xFE, 0x31), 'ERR_GENERIC'
    # The length is asserted at the mock because SduDataPtr always holds a full MAX_CTO frame padded
    # with trailingValue, so bytes 2-3 are readable whether or not the module wrote them.
    assert handle.can_if_transmit.call_args[0][1].SduLength == 4
    assert u16_from_array(bytearray(response[2:4]), 'LITTLE_ENDIAN') == 0x0006, \
        'expected XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG'
    handle.det_report_error.assert_called_once_with(ANY,
                                                    ANY,
                                                    handle.define('XCP_CAN_IF_RX_INDICATION_API_ID'),
                                                    handle.define('XCP_E_USER_CMD_RESPONSE_TOO_LONG'))


def test_user_cmd_transmits_a_response_exactly_at_max_cto():
    """The boundary the refusal above must not swallow. MAX_CTO itself is a legal length -- XCP part
    2 - Protocol Layer Specification 1.1/1.1.3.3 ends the payload area at MAX_CTO-1, so a packet
    whose SduLength equals MAX_CTO occupies positions 0..MAX_CTO-1 exactly. An off-by-one in the
    comparison shows here and nowhere else."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, user_cmd_function='Xcp_UserCmdFunction'))

    def xcp_user_cmd_function(_p_cmd_pdu_info, p_res_err_pdu_info):
        p_res_err_pdu_info[0].SduLength = 0x08
        for i in range(0x08):
            p_res_err_pdu_info[0].SduDataPtr[i] = i
        return handle.define('E_OK')

    handle.xcp_user_cmd_function.side_effect = xcp_user_cmd_function

    # CONNECT
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    # USER_CMD
    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF1, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.can_if_transmit.call_args[0][1].SduLength == 0x08
    assert tuple(handle.can_if_transmit.call_args[0][1].SduDataPtr[0:8]) == (0, 1, 2, 3, 4, 5, 6, 7)
    handle.det_report_error.assert_not_called()
```

- [ ] **Step 2: Run the tests and verify they fail**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="-k;user_cmd" && cd .. && ./test.sh'
```

Expected: `test_user_cmd_refuses_a_response_longer_than_max_cto` FAILS at the CFFI compile step with
`'XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG' undeclared` (raised by `handle.define`), or — once
the two definitions exist but the handler does not check — at
`assert response[0:2] == (0xFE, 0x31)`, because the 9-byte user response is transmitted as-is.
`test_user_cmd_transmits_a_response_exactly_at_max_cto` PASSES already; it is the guard against the
fix overreaching.

- [ ] **Step 3: Define the detail code**

In `interface/Xcp_Errors.h`, after `XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED` and before the
closing `#endif`:

```c
/**
* @brief USER_CMD: the integrator's Xcp_UserCmdFunction returned a response whose SduLength exceeds
* MAX_CTO. The response is discarded rather than truncated -- a user-defined payload carries no
* length field of its own, so a clamped response would be indistinguishable from a complete one
* (DD129). The fault is in the callback, not in the master's request, which is why this is the one
* ERR_GENERIC 1.1/1.7.3.2.1's USER_CMD row does not list (DD130).
 */
#define XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG (0x0006u)
```

- [ ] **Step 4: Define the Det id**

In `interface/Xcp.h`, after `XCP_E_IDENTIFICATION_NOT_GRANULAR` and before the `/** @} */` that
closes the group:

```c
/**
 * @brief Xcp_UserCmdFunction set an SduLength greater than MAX_CTO.
 * @details The response is discarded and the master is answered ERR_GENERIC carrying
 * @ref XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG. XCP part 2 - Protocol Layer Specification
 * 1.1/1.1.3.3 ends a packet's payload area at MAX_CTO-1, so a longer response has no position to
 * occupy and cannot be transmitted.
 * @note This error is not part of the specification. Det is where the person who can fix it sees
 * it: the fault is in the integrator's own callback, and the master is told only that the command
 * failed. 0x0A rather than a lower free value because XCP_E_EVENT_QUEUE_FULL already collides with
 * AUTOSAR's XCP_E_INIT_FAILED at 0x04. DD131.
 */
#define XCP_E_USER_CMD_RESPONSE_TOO_LONG (0x0Au)
```

- [ ] **Step 5: Declare `ERR_GENERIC` in `USER_CMD`'s error-matrix row**

In `source/Xcp.c` line 1001, add the bit to `USER_CMD`'s row only:

```c
    XCP_INTERNAL_ERR_CMD_BUSY | XCP_INTERNAL_ERR_PGM_ACTIVE | XCP_INTERNAL_ERR_CMD_SYNTAX | XCP_INTERNAL_ERR_OUT_OF_RANGE | XCP_INTERNAL_ERR_GENERIC, /* USER_CMD 0xF1, optional */
```

Leave `TRANSPORT_LAYER_CMD`'s row on the next line untouched. The matrix drives only the three
generic pre-checks (`ERR_CMD_BUSY`, `ERR_CMD_SYNTAX`, `ERR_PGM_ACTIVE`), so this bit changes no
behaviour; it keeps the table from disagreeing with the handler, as DD76 did for `UNLOCK`.

- [ ] **Step 6: Implement the check**

Replace the body of `Xcp_DTOCmdStdUserCmd` in `source/Xcp_Std.c` with:

```c
uint8 Xcp_DTOCmdStdUserCmd(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8 result = E_OK;

    *responseExpected = TRUE;

    if (Xcp_Ptr->general->userCmdFunction != NULL_PTR) {
        result = Xcp_Ptr->general->userCmdFunction(pPduInfo, &Xcp_Internal.cto_response.pdu_info);

        /* The only response length in this module that an integrator chooses. XCP part 2 - Protocol
         * Layer Specification 1.1/1.1.3.3 ends a packet at MAX_CTO-1, so a longer one cannot be
         * transmitted; it is refused rather than clamped because a user-defined payload has no
         * length field a master could use to notice the clamp (DD129).
         *
         * ERR_GENERIC is a deliberate deviation: 1.1/1.7.3.2.1's USER_CMD row lists ERR_CMD_BUSY,
         * ERR_PGM_ACTIVE, ERR_CMD_SYNTAX, ERR_OUT_OF_RANGE and ERR_RES_TEMP_NOT_A., and each of the
         * usable ones blames the master's own request for what the slave's extension did. DD57
         * (PROGRAM_RESET) and DD76 (UNLOCK) took the same deviation for the same reason; DD130
         * records this as the third. Returning the Det id rather than reporting it here is what
         * Xcp_CanIfRxIndication already does with any non-E_OK handler result (source/Xcp.c), the
         * same path the XCP_E_PARAM_POINTER below takes -- and it does not suppress the response,
         * which is filled and transmitted either way. */
        if (Xcp_Internal.cto_response.pdu_info.SduLength > (PduLengthType)Xcp_Ptr->general->maxCto)
        {
            Xcp_FillGenericErrorPacket(XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG,
                                       &Xcp_Internal.cto_response.pdu_info);

            if (result == E_OK)
            {
                result = XCP_E_USER_CMD_RESPONSE_TOO_LONG;
            }
        }
        else
        {
            /* Xcp_FillGenericErrorPacket finalizes the packet itself, so this must not run for the
             * refused case: it would re-finalize at the stale length the callback set. */
            Xcp_FinalizeResPacket(Xcp_Internal.cto_response.pdu_info.SduLength, &Xcp_Internal.cto_response.pdu_info);
        }
    }
    else
    {
        result = XCP_E_PARAM_POINTER;
    }

    return result;
}
```

- [ ] **Step 7: Run the tests and verify they pass**

Same command as Step 2. Expected: every test in `user_cmd_test.py` PASSES, including the two
pre-existing ones that pass a response shorter than MAX_CTO.

- [ ] **Step 8: Give the callback its real contract**

`test/stub/Xcp_UserCmd.h` is the header an integrator implements, and its doc comment is a copy of
the checksum callback's, describing an address range this function does not take. Replace it:

```c
/**
 * @brief Handles a USER_CMD request (XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.12).
 * @param [in] pCtoPduInfo The request as received, including the USER_CMD PID in byte 0.
 * @param [out] pResErrPduInfo The response to transmit. Write the payload into SduDataPtr and set
 * SduLength to the number of bytes written, MAX_CTO included but never exceeded: 1.1/1.1.3.3 ends a
 * packet at MAX_CTO-1, and a longer response is discarded, answered ERR_GENERIC carrying
 * XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG, and reported to Det as
 * XCP_E_USER_CMD_RESPONSE_TOO_LONG.
 * @retval E_OK : Command executed successfully
 * @retval XCP_E_* : Command failed. If the DET module is enabled, this error will be reported to the DET
 */
```

- [ ] **Step 9: Run the full suite with the cache cleared**

```bash
docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp --volume "$PWD:/usr/project" --workdir /usr/project xcp-test:local sh -c 'cd build && cmake .. -DXCP_ENABLE_TEST=ON -DXCP_PYTEST_ARGS="" && cd .. && ./test.sh'
```

Expected: the whole suite passes. Record the reported test count — Task 3 updates the roadmap with
it.

- [ ] **Step 10: Commit and push**

```bash
git add interface/Xcp_Errors.h interface/Xcp.h source/Xcp.c source/Xcp_Std.c test/stub/Xcp_UserCmd.h test/user_cmd_test.py
git commit -m "fix: refuse a USER_CMD response longer than MAX_CTO"
git push
```

---

### Task 3: Integrator documentation and the roadmap's own record

**Files:**
- Modify: `README.md` (new `## User-defined commands` section immediately before `## Flash programming`)
- Modify: `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` (§3's D18 entry; §1's test count)

**Interfaces:**
- Consumes: the two identifiers Task 2 produced, and the test count from Task 2's Step 9 run.
- Produces: nothing other tasks depend on.

- [ ] **Step 1: Document the bound for integrators**

`USER_CMD` has no README presence at all today. Insert immediately before `## Flash programming`:

```markdown
## User-defined commands

`USER_CMD` (`0xF1`) is dispatched straight to `Xcp_UserCmdFunction` (`test/stub/Xcp_UserCmd.h`),
which receives the request and builds the response itself: it writes the payload into the response
`PduInfoType` and sets `SduLength` to what it wrote.

That length is the only one in this module an integrator chooses, and it is bounded. XCP part 2
§1.1.3.3 ends a packet's payload at `MAX_CTO-1`, so a response longer than `MAX_CTO` cannot be
transmitted: it is **discarded rather than truncated** — a user-defined payload carries no length
field, so a clamped response would look complete to the master — and the slave answers `ERR_GENERIC`
carrying `XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG` (`interface/Xcp_Errors.h`), reporting
`XCP_E_USER_CMD_RESPONSE_TOO_LONG` to Det for whoever wrote the callback. A response of exactly
`MAX_CTO` bytes is legal and is transmitted unchanged.
```

- [ ] **Step 2: Close D18 in the roadmap**

In `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` §3, replace D18's closing line —

```markdown
> **Open.** Found while designing D17 (`2026-09-15-xcp-err-generic-detail-design.md` §5).
```

— with:

```markdown
> **Fixed.** The bound is checked where each length is chosen: `script/source_cfg.c.jinja2` refuses a
> configuration whose own `max_cto` is below 8, and `Xcp_DTOCmdStdUserCmd` (`source/Xcp_Std.c`)
> refuses an over-long callback response with `ERR_GENERIC` plus
> `XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG` and a Det report. Design:
> `2026-09-15-xcp-max-cto-bound-d18-design.md` (DD126–DD131).
>
> The entry understated it in one way and overstated it in another. Understated: `USER_CMD` let the
> *integrator* set `SduLength` with no check at all, which no schema minimum could have protected —
> that is the half this defect did not name. Overstated: the schema floor was never "comfortable".
> `BUILD_CHECKSUM` hands the helper six bytes, not four (1.1/§1.6.1.2.9's reserved WORD at positions
> 2,3 is part of the payload), so the largest error packet is 8 — exactly the floor, with no headroom
> at all.
>
> Three findings recorded in that design's §5 rather than fixed here: `MAX_CTO mod AG = 0` and
> `MAX_DTO mod AG = 0` (1.1/§1.6.1.1.1) are enforced only at `Xcp_Init`, so a violation reaches the
> target instead of the build; `Xcp_CTOErrorMatrix` carries `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE`
> in no row though 1.1 adds it to the STD rows and `GET_STATUS` already answers it; and
> `XCP_E_EVENT_QUEUE_FULL` (0x04) collides with AUTOSAR's `XCP_E_INIT_FAILED`.
```

- [ ] **Step 3: Update the suite's test count**

§1's table row reads `... 12574 passing, 30 skipped ...`. Replace both numbers with what Task 2's
Step 9 run actually reported. Do not guess them — read them from that run's output.

- [ ] **Step 4: Verify the documentation claims against the code**

Re-read the README section and the D18 entry beside the shipped code. Every identifier named must
exist with that spelling (`XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG`,
`XCP_E_USER_CMD_RESPONSE_TOO_LONG`, `Xcp_UserCmdFunction`), and the behaviour described — discard,
`ERR_GENERIC`, Det, exactly-`MAX_CTO` transmitted — must match `Xcp_DTOCmdStdUserCmd` as written.
This step exists because the stale comment Task 2 Step 8 replaced is what an unverified doc becomes.

- [ ] **Step 5: Commit and push**

```bash
git add README.md docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
git commit -m "docs: close D18 and document USER_CMD's response bound"
git push
```

- [ ] **Step 6: Open the pull request**

```bash
gh pr create --base develop --title "fix: enforce the MAX_CTO bound on response payloads (D18)" --body "$(cat <<'BODY'
Closes D18. The bound between `MAX_CTO` and the payloads this module attaches to a response was
enforced nowhere in `source/`; it held only because `config/xcp.schema.json` happens to require
`max_cto >= 8`.

Two halves, split by who chooses the length.

**The module's own payloads — checked at generation.** All three are compile-time constants, so
`script/source_cfg.c.jinja2` refuses a configuration whose own `max_cto` is below 8 (not
`XCP_MAX_CTO`, which is a `max()` fold and would prove only that the largest configuration fits).
No runtime branch is added: none could ever be entered, and this project has removed two such dead
guards before.

**`USER_CMD` — checked at runtime.** Its length crosses an API boundary: the integrator's callback
writes the payload and sets `SduLength`, and the module finalized whatever came back. An over-long
response is now discarded rather than truncated — a user-defined payload has no length field, so a
clamped one would look complete to the master — and answered `ERR_GENERIC` carrying
`XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG`, with `XCP_E_USER_CMD_RESPONSE_TOO_LONG` to Det for
whoever wrote the callback.

`ERR_GENERIC` is a deliberate deviation: §1.7.3.2.1's `USER_CMD` row does not list it in either
revision, and every listed code blames the master's request for what the slave's extension did.
DD57 (`PROGRAM_RESET`) and DD76 (`UNLOCK`) took the same deviation for the same reason.

**Measured while writing the design:** `BUILD_CHECKSUM` hands the helper six bytes, not four —
§1.6.1.2.9's reserved WORD at positions 2,3 is part of the payload — so the largest error packet is
8, exactly the schema floor, with no headroom at all. D18 supposed the floor was comfortable.

Four findings are recorded in the design's §5 rather than fixed here: `MAX_CTO mod AG = 0` and
`MAX_DTO mod AG = 0` (§1.6.1.1.1) enforced only at `Xcp_Init`, so a violation reaches the target
rather than the build;
`Xcp_CTOErrorMatrix` carrying `ERR_RESOURCE_TEMPORARY_NOT_ACCESSIBLE` in no row though 1.1 adds it
to the STD rows and `GET_STATUS` already answers it; `XCP_E_EVENT_QUEUE_FULL` (0x04) colliding
with AUTOSAR's `XCP_E_INIT_FAILED`; and `USER_CMD` with no configured callback possibly
transmitting whatever the previous command left in the shared response buffer, traced through the
code but not confirmed on the wire.

Design: `docs/superpowers/specs/2026-09-15-xcp-max-cto-bound-d18-design.md` (DD126-DD131).
Plan: `docs/superpowers/plans/2026-09-15-xcp-max-cto-bound-d18.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
```
