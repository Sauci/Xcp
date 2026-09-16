# SERV Service Request Codes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `SERV_RESET` and `SERV_TEXT` (XCP Part 2 §1.3), completing the user-data path the event queue half-built.

**Architecture:** `Xcp_EventQueueGet` gains the user data and size it already reads; the transmit branch copies them and finalizes at `2 + size` instead of a constant 2; two integrator functions push with `XCP_PID_SERV`. The three `EV_*` callers that push a status byte §1.2 defines nowhere stop doing so, in the same commit.

**Tech Stack:** C (AUTOSAR MISRA style), pytest + CFFI compiling the real C, CMake/ctest, Docker.

**Spec:** `docs/superpowers/specs/2026-09-16-xcp-serv-codes-design.md` (DD138–DD142)

## Global Constraints

- **Reference revision:** XCP Part 2 1.1, read alongside 1.0. Comments cite with the revision prefix, e.g. `1.1/1.1.3.5`.
- **Tests run in Docker only**, image `xcp-build:local` (not `ghcr.io/sauci/xcp:develop`, which has CMake 3.14.5 against a 3.19 floor):
  ```
  docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
    --volume "$PWD:/usr/project" --workdir /usr/project xcp-build:local ./test.sh
  ```
  ~7 minutes. `-x` is hardcoded at `CMakeLists.txt:307`, so the run halts at the first failure; to collect all failures in one run, seed `XCP_PYTEST_ARGS="--maxfail=200"` into the CMake cache and **clear it back to `""` afterwards**.
- **Baseline:** 13018 passed, 29 skipped, 2/2 ctest targets, exit 0.
- **DD141 is a correctness constraint:** the EV status-byte cleanup must land in the *same commit* as the transmit change. Splitting them puts undefined content on the wire in between.

---

## File Structure

| File | Change |
|:--|:--|
| `source/Xcp.c` | `Xcp_EventQueueGet` signature + body; transmit branch; three `EV_*` push callers; `Xcp_CanIfTxConfirmation`'s getter call |
| `source/Xcp_Internal.h` | `XCP_PID_SERV`, `XCP_SERV_RESET`, `XCP_SERV_TEXT`; getter forward declaration |
| `interface/Xcp.h` | `XCP_E_SERVICE_TEXT_INVALID`; the two API declarations |
| `test/serv_codes_test.py` | new — wire behaviour, rejections, ordering, queue-full |
| `test/event_frame_length_test.py` | the two-byte pin |
| `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md` | §2.6 `SERV_*` row, pass count, DAQ spike note |

---

### Task 1: Honour the queue's user data (DD138 + DD141)

**Files:** Modify `source/Xcp.c` (getter at `:2565`, transmit branch at `:2622`, TxConfirmation caller at `:2391`, pushes at `:1600`, `:1683`, `:1747`), `source/Xcp_Internal.h`
**Interfaces produced:** `Xcp_EventQueueGet(queue, *pPacketID, *pEventCode, **ppUserData, *pUserDataSize)` — Tasks 2 and 3 rely on the transmit branch honouring the size.

- [ ] **Step 1: Write the failing test** — append to `test/event_frame_length_test.py`:

```python
def test_an_event_carrying_no_user_data_is_still_exactly_two_bytes():
    """DD138 replaces Xcp_FinalizeResPacket(0x02u, ...) with a computed 2 + userDataSize. Every
    EV_* this module sends has userDataSize 0 -- 1.2 defines event information for none of them --
    so this must stay 2. Without this pin the generalisation could regress the 2026-09-16 fix that
    gave event frames a length at all, and DD141's removal of the three dead status-byte pushes
    could be forgotten without any test objecting."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    return_values = (r for r in [handle.define('E_NOT_OK'), handle.define('E_NOT_OK'), handle.define('E_OK')])

    def store_calibration_data_to_non_volatile_memory(p_success):
        p_success[0] = handle.define('E_OK')
        return next(return_values)

    handle.xcp_store_calibration_data_to_non_volatile_memory.side_effect = store_calibration_data_to_non_volatile_memory

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xF9, 0x01, 0x00, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    frame = handle.can_if_transmit.call_args[0][1]
    assert tuple(frame.SduDataPtr[0:2]) == (0xFD, 0x03), 'EV_STORE_CAL'
    assert frame.SduLength == 0x02, 'no event this module sends carries information data'
```

- [ ] **Step 2: Run it.** Expect PASS — it passes before the change too, which is the point: it is a pin, not a red test. Note the count (13019).

- [ ] **Step 3: Add the identifiers** to `source/Xcp_Internal.h`, beside `XCP_PID_EVENT` (line 47) and the `XCP_EVENT_*` block (lines 51-54):

```c
/* 1.1/1.1.3.5. The comment further down this file has named 0xFC as SERV since before anything
 * could send one; this is the definition it described. */
#define XCP_PID_SERV (0xFCu)
```

```c
/* 1.1/1.3's two service request codes. "The implementation is optional for the slave device, but
 * mandatory for the master device", and service requests are not acknowledged, so delivery is not
 * guaranteed -- which is why they share the event queue rather than getting a priority path of
 * their own (DD139). */
#define XCP_SERV_RESET (0x00u)
#define XCP_SERV_TEXT (0x01u)
```

- [ ] **Step 4: Widen the getter.** In `source/Xcp.c`, replace `Xcp_EventQueueGet`'s definition (`:2565`):

```c
static Std_ReturnType Xcp_EventQueueGet(Xcp_EventQueueType *pEventQueue, uint8 *pPacketID,
                                        uint8 *pEventCode, const uint8 **ppUserData,
                                        uint32 *pUserDataSize) {
    Std_ReturnType result;

    if (pEventQueue->read != pEventQueue->write) {
        *pPacketID = pEventQueue->queue[pEventQueue->read].packetID;
        *pEventCode = pEventQueue->queue[pEventQueue->read].eventCode;

        /* DD138. A pointer into the entry, not a copy: the entry is not released until
         * Xcp_EventQueuePop, which Xcp_CanIfTxConfirmation calls only once the frame it describes
         * has been confirmed. Until this, userData was written by Xcp_EventQueuePush, zeroed at
         * Xcp_Init and read nowhere -- the queue carried a payload it could not deliver. */
        *ppUserData = &pEventQueue->queue[pEventQueue->read].userData[0x00u];
        *pUserDataSize = pEventQueue->queue[pEventQueue->read].userDataSize;

        result = E_OK;
    } else {
        result = E_NOT_OK;
    }

    return result;
}
```

Update its forward declaration to match wherever it appears.

- [ ] **Step 5: Transmit the user data.** In `Xcp_TransmitOneFrame`'s event branch, declare `const uint8 *p_user_data;` and `uint32 user_data_size;` beside the existing `event_packet_id` / `event_code`, pass them to the getter, and replace the fixed finalize:

```c
            Xcp_Internal.event.pdu_info.SduDataPtr[0x00u] = event_packet_id;
            Xcp_Internal.event.pdu_info.SduDataPtr[0x01u] = event_code;

            /* DD138. 1.1/1.1.3.4 and 1.1/1.1.3.5 both put optional data at 2..MAX_CTO-1, for EV and
             * SERV alike. Xcp_EventQueuePush bounds userDataSize by XCP_EVENT_USER_DATA_SIZE and
             * Xcp_SendServiceText bounds it by maxCto as well, so this loop needs no bound of its
             * own -- unlike Xcp_FillErrorPacketWithData, whose missing one was D18.
             *
             * This replaces a literal 0x02u added on 2026-09-16, which fixed a defect where
             * SduLength was never set at all and every EV_* went out as an empty frame. That fix
             * was right; it was also true only while every packet was two bytes. SERV_TEXT is not,
             * and test_an_event_carrying_no_user_data_is_still_exactly_two_bytes pins the case it
             * did fix. */
            for (user_data_idx = 0x00000000u; user_data_idx < user_data_size; user_data_idx++)
            {
                Xcp_Internal.event.pdu_info.SduDataPtr[0x02u + user_data_idx] = p_user_data[user_data_idx];
            }

            Xcp_FinalizeResPacket((PduLengthType)(0x02u + user_data_size), &Xcp_Internal.event.pdu_info);
```

Declare `uint32_least user_data_idx;` with the other locals.

- [ ] **Step 6: Update the other caller.** `Xcp_CanIfTxConfirmation`'s `EV_CMD_PENDING` check (`:2391`) passes the two new parameters and ignores them — it asks only which code is at the head of the queue. Declare locals for them beside its existing `event_packet_id` / `event_code`.

- [ ] **Step 7: DD141 — stop pushing the dead status bytes.** At `source/Xcp.c:1600`, `:1683` and `:1747`, replace the `&..._status, 0x00000001u` arguments with `NULL_PTR, 0x00000000u`. Add above the first of them:

```c
            /* DD141. The status byte pushed here went nowhere: nothing read userData. 1.2 defines
             * event information for no code this module sends -- EV_STORE_CAL, EV_STORE_DAQ,
             * EV_CLEAR_DAQ, EV_RESUME_MODE, EV_CMD_PENDING and EV_DAQ_OVERLOAD are all pure
             * two-byte notifications, and only EV_USER and EV_TRANSPORT are carriers. Now that
             * DD138 transmits userData, pushing it would put content on the wire the specification
             * does not define for this code. Xcp_EventQueuePush tolerates NULL_PTR at size 0
             * (source/Xcp_Internal.h). */
```

- [ ] **Step 8: Run the full suite.** Expect **13019 passed, 29 skipped**, exit 0 — the pin plus no change. Any other failure means an EV packet was carrying data that now reaches the wire; read it rather than adjusting the guard.

- [ ] **Step 9: Commit.**

```bash
git add source/Xcp.c source/Xcp_Internal.h test/event_frame_length_test.py
git commit -m "feat: transmit the event queue's user data (DD138, DD141)"
```

---

### Task 2: SERV_RESET (DD140, first half)

**Files:** Modify `interface/Xcp.h`, `source/Xcp.c`; create `test/serv_codes_test.py`
**Interfaces consumed:** the transmit path from Task 1.
**Interfaces produced:** `Std_ReturnType Xcp_RequestServiceReset(void)`.

- [ ] **Step 1: Write the failing test** — create `test/serv_codes_test.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest.mock import ANY

from .parameter import *
from .conftest import XcpTest


def test_service_reset_reaches_the_master_as_a_serv_packet():
    """1.1/1.3's SERV_RESET (0x00), "Slave requesting to be reset", carried by 1.1/1.1.3.5's SERV
    packet: PID 0xFC at position 0, the service request code at 1. Two bytes, no data.

    It requests a reset OF the slave BY the master, so this changes no module state -- the slave
    resetting itself on its own say-so is not what the code means (DD140)."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    assert handle.lib.Xcp_RequestServiceReset() == handle.define('E_OK')

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    frame = handle.can_if_transmit.call_args[0][1]
    assert tuple(frame.SduDataPtr[0:2]) == (0xFC, 0x00), 'SERV_RESET'
    assert frame.SduLength == 0x02
    handle.det_report_error.assert_not_called()
```

- [ ] **Step 2: Run it.** Expect FAIL — `Xcp_RequestServiceReset` does not exist, so the CFFI lookup raises `AttributeError`. That is the right failure.

- [ ] **Step 3: Declare it** in `interface/Xcp.h`, beside the other slave-initiated entry points:

```c
/**
 * @brief Requests the master to reset this slave.
 * @details Queues a SERV packet carrying SERV_RESET (XCP part 2 - Protocol Layer Specification
 * 1.1/1.3), transmitted by Xcp_MainFunction like any event. Changes no module state: 1.1/1.3 makes
 * this a request TO the master, and a slave that reset itself on its own say-so would be doing
 * something the code does not mean.
 * @note 1.1/1.3: "Service request packets sent from the slave device to the master device are not
 * acknowledged, therefore the transmission is not guaranteed." E_OK means queued, not delivered.
 * @return E_OK when the request was queued; E_NOT_OK when the event queue is full, which also
 * reports @ref XCP_E_EVENT_QUEUE_FULL to Det.
 */
Std_ReturnType Xcp_RequestServiceReset(void);
```

- [ ] **Step 4: Define it** in `source/Xcp.c`, beside the other public slave-initiated functions:

```c
Std_ReturnType Xcp_RequestServiceReset(void)
{
    Std_ReturnType result = Xcp_EventQueuePush(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue,
                                               XCP_PID_SERV, XCP_SERV_RESET,
                                               NULL_PTR, 0x00000000u);

    if (result != E_OK)
    {
        Xcp_ReportError(0x00u, XCP_MAIN_FUNCTION_API_ID, XCP_E_EVENT_QUEUE_FULL);
    }

    return result;
}
```

If `XCP_MAIN_FUNCTION_API_ID` is not the right API id for a caller-invoked entry point, use the id the neighbouring public functions use; check `Xcp_ResumeComplete`.

- [ ] **Step 5: Run the full suite.** Expect **13020 passed, 29 skipped**, exit 0.

- [ ] **Step 6: Commit.**

```bash
git add interface/Xcp.h source/Xcp.c test/serv_codes_test.py
git commit -m "feat: add SERV_RESET (DD140)"
```

---

### Task 3: SERV_TEXT and its bounds (DD140, second half)

**Files:** Modify `interface/Xcp.h`, `source/Xcp.c`, `test/serv_codes_test.py`
**Interfaces produced:** `Std_ReturnType Xcp_SendServiceText(const uint8 *pText, uint16 length)`, `XCP_E_SERVICE_TEXT_INVALID` (0x0D).

- [ ] **Step 1: Write the failing tests** — append to `test/serv_codes_test.py`:

```python
def test_service_text_reaches_the_master_with_its_terminator():
    """1.1/1.3's SERV_TEXT (0x01): "The remaining data bytes of the packet contain plain ASCII text
    ... The text must be null terminated to indicate the end of the overall packet." The terminator
    is part of the payload, so a 4-byte "Hi\\0" -- three characters and the null -- is SduLength
    2 + 4."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    text = (0x48, 0x65, 0x79, 0x00)  # "Hey\0"
    assert handle.lib.Xcp_SendServiceText(text, len(text)) == handle.define('E_OK')

    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    frame = handle.can_if_transmit.call_args[0][1]
    assert tuple(frame.SduDataPtr[0:6]) == (0xFC, 0x01) + text
    assert frame.SduLength == 0x06
    handle.det_report_error.assert_not_called()
```

```python
@pytest.mark.parametrize('text, expected_det', (
    (None, 'XCP_E_PARAM_POINTER'),
    ((), 'XCP_E_SERVICE_TEXT_INVALID'),
    ((0x48, 0x65), 'XCP_E_SERVICE_TEXT_INVALID'),          # no terminator
    (tuple([0x41] * 7) + (0x00,), 'XCP_E_SERVICE_TEXT_INVALID'),   # 8 bytes, MAX_CTO 8 needs <= 6
))
def test_service_text_refuses_what_it_cannot_transmit(text, expected_det):
    """Each rejection asserts three things: E_NOT_OK returned, the right Det id, and that NOTHING
    was transmitted. The third is the one this codebase keeps learning to make -- D18's Finding 4,
    GET_SEED, SHORT_UPLOAD and the event frame length all survived because tests asserted bytes or
    Det without asserting what reached the transport.

    Refused rather than truncated (DD129's reasoning): a truncated null-terminated string loses the
    terminator 1.1/1.3 makes its end-of-packet marker, so a master cannot tell it was cut."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, max_cto=8))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    transmit_calls = handle.can_if_transmit.call_count

    if text is None:
        result = handle.lib.Xcp_SendServiceText(handle.ffi.NULL, 4)
    else:
        result = handle.lib.Xcp_SendServiceText(text, len(text))

    handle.lib.Xcp_MainFunction()

    assert result == handle.define('E_NOT_OK')
    assert handle.can_if_transmit.call_count == transmit_calls, 'nothing may reach the transport'
    handle.det_report_error.assert_called_once_with(ANY, ANY, ANY, handle.define(expected_det))
```

Add `import pytest` to the file.

- [ ] **Step 2: Run them.** Expect FAIL — the function does not exist.

- [ ] **Step 3: Add the Det id** to `interface/Xcp.h`, after `XCP_E_EVENT_QUEUE_FULL`:

```c
/**
 * @brief The text handed to Xcp_SendServiceText cannot be transmitted as a SERV_TEXT payload.
 * @details Reported for a zero length, for text whose last byte is not the null terminator XCP
 * part 2 - Protocol Layer Specification 1.1/1.3 requires, and for text too long for either MAX_CTO
 * or XCP_EVENT_USER_DATA_SIZE. The request is refused, never truncated: a truncated
 * null-terminated string loses the terminator that marks the end of the packet, so a master cannot
 * tell it was cut (the reasoning DD129 applied to the USER_CMD response).
 * @note One id for four checks, because they are one fault -- the text is not a transmissible
 * payload. A null pointer reports @ref XCP_E_PARAM_POINTER instead, the id the USER_CMD path
 * already uses for that mistake. DD140.
 */
#define XCP_E_SERVICE_TEXT_INVALID (0x0Du)
```

- [ ] **Step 4: Declare the function** in `interface/Xcp.h`:

```c
/**
 * @brief Sends plain ASCII text to the master as a SERV_TEXT service request.
 * @param pText the text, INCLUDING its null terminator, which 1.1/1.3 makes the end-of-packet
 * marker and which therefore counts toward @p length.
 * @param length how many bytes of @p pText to send, terminator included. Must satisfy
 * 0x02 + length <= MAX_CTO and length <= XCP_EVENT_USER_DATA_SIZE; the two are independent bounds,
 * since MAX_CTO may be 255 while the queue entry holds 16.
 * @details The module never writes into @p pText and never reads past @p length: the terminator is
 * validated, not appended, and the length is given rather than measured. Taking a C string and
 * calling strlen here would be an unbounded read over integrator memory.
 * @note 1.1/1.3: service requests are not acknowledged, so E_OK means queued, not delivered.
 * @return E_OK when queued; E_NOT_OK on a full queue (@ref XCP_E_EVENT_QUEUE_FULL), a null pointer
 * (@ref XCP_E_PARAM_POINTER) or an untransmittable text (@ref XCP_E_SERVICE_TEXT_INVALID).
 */
Std_ReturnType Xcp_SendServiceText(const uint8 *pText, uint16 length);
```

- [ ] **Step 5: Define it** in `source/Xcp.c`, beside `Xcp_RequestServiceReset`:

```c
Std_ReturnType Xcp_SendServiceText(const uint8 *pText, uint16 length)
{
    Std_ReturnType result = E_NOT_OK;

    if (pText == NULL_PTR)
    {
        Xcp_ReportError(0x00u, XCP_MAIN_FUNCTION_API_ID, XCP_E_PARAM_POINTER);
    }
    /* DD140. Four checks, one fault: the text is not a transmissible SERV_TEXT payload. The last
     * two bounds are independent -- MAX_CTO may be 255 while the queue entry holds
     * XCP_EVENT_USER_DATA_SIZE bytes. 1.1/1.3 makes the null terminator the end-of-packet marker,
     * so it is validated here rather than appended: appending would write into the integrator's
     * buffer, and measuring instead of validating would read past the length given. */
    else if ((length == 0x0000u) ||
             (pText[length - 0x0001u] != 0x00u) ||
             ((uint32)(0x02u + length) > (uint32)Xcp_Ptr->general->maxCto) ||
             (length > XCP_EVENT_USER_DATA_SIZE))
    {
        Xcp_ReportError(0x00u, XCP_MAIN_FUNCTION_API_ID, XCP_E_SERVICE_TEXT_INVALID);
    }
    else
    {
        result = Xcp_EventQueuePush(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue,
                                    XCP_PID_SERV, XCP_SERV_TEXT,
                                    pText, (uint32)length);

        if (result != E_OK)
        {
            Xcp_ReportError(0x00u, XCP_MAIN_FUNCTION_API_ID, XCP_E_EVENT_QUEUE_FULL);
        }
    }

    return result;
}
```

- [ ] **Step 6: Run the full suite.** Expect **13025 passed, 29 skipped** (13020 + 1 + 4), exit 0.

- [ ] **Step 7: Commit.**

```bash
git add interface/Xcp.h source/Xcp.c test/serv_codes_test.py
git commit -m "feat: add SERV_TEXT and its bounds (DD140)"
```

---

### Task 4: Ordering and queue-full

**Files:** Modify `test/serv_codes_test.py`

- [ ] **Step 1: Write the tests** — append:

```python
def test_a_service_request_and_an_event_both_reach_the_wire_in_push_order():
    """The property DD139 claims by reusing one queue rather than adding a second. A SERV that
    displaced an EV, or vice versa, would make the shared queue the wrong choice."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    marker = handle.can_if_transmit.call_count

    assert handle.lib.Xcp_RequestServiceReset() == handle.define('E_OK')
    text = (0x41, 0x00)
    assert handle.lib.Xcp_SendServiceText(text, len(text)) == handle.define('E_OK')

    for _ in range(4):
        handle.lib.Xcp_MainFunction()
        handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    frames = [tuple(c[0][1].SduDataPtr[0:2]) for c in handle.can_if_transmit.call_args_list[marker:]]
    assert frames[0] == (0xFC, 0x00), 'SERV_RESET first, pushed first'
    assert frames[1] == (0xFC, 0x01), 'SERV_TEXT second'


def test_a_full_queue_refuses_a_service_request():
    """E_NOT_OK and XCP_E_EVENT_QUEUE_FULL, the existing path -- at 0x0C since 2026-09-16 moved it
    off its collision with AUTOSAR's XCP_E_INIT_FAILED at 0x04."""
    handle = XcpTest(DefaultConfig(channel_rx_pdu_ref=0x0001, event_queue_size=2))

    handle.lib.Xcp_CanIfRxIndication(0x0001, handle.get_pdu_info((0xFF, 0x00)))
    handle.lib.Xcp_MainFunction()
    handle.lib.Xcp_CanIfTxConfirmation(0x0001, handle.define('E_OK'))

    results = [handle.lib.Xcp_RequestServiceReset() for _ in range(4)]

    assert handle.define('E_NOT_OK') in results, 'a queue of capacity 1 must fill'
    handle.det_report_error.assert_called_with(ANY, ANY, ANY, handle.define('XCP_E_EVENT_QUEUE_FULL'))
```

If `event_queue_size` is not a `DefaultConfig` keyword, use the name `test/set_request_test.py`'s own queue-size parametrisation uses.

- [ ] **Step 2: Run the full suite.** Expect **13027 passed, 29 skipped**, exit 0.

- [ ] **Step 3: Commit.**

```bash
git add test/serv_codes_test.py
git commit -m "test: SERV ordering against events, and a full queue"
```

---

### Task 5: Roadmap

**Files:** Modify `docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md`

- [ ] **Step 1:** Pass count 13018 → 13027.

- [ ] **Step 2:** Replace §2.6's `Service request codes (SERV_*)` row — currently "absent — `SERV_RESET`, `SERV_TEXT`. Optional for a slave" — with a **done** entry naming both codes, the two API functions, and the design doc.

- [ ] **Step 3:** In §4's SP5 section, record that SERV is shipped and that the interleaved communication model is now SP5's only remaining item.

- [ ] **Step 4:** Add the DAQ transmit-length spike's negative result beside the CTO invariant's entry: `Xcp_DaqRuntime.c` sets `SduLength` from the queued frame's own `length`, that length is `Xcp_DaqWriteIdentificationField`'s return plus the timestamp plus the elements (`:416`), and an ODT copying nothing returns `E_NOT_OK` so a header-only frame is never enqueued (`:318`, `:1203`). Recorded so nobody re-runs the investigation.

- [ ] **Step 5: Commit.**

```bash
git add docs/superpowers/specs/2026-08-29-xcp-part2-roadmap.md
git commit -m "docs: record SERV and the DAQ frame-length spike"
```

---

## Verification before the PR

- [ ] Full suite in Docker at the final commit: **13027 passed, 29 skipped**, 2/2 ctest targets, exit 0.
- [ ] `git status --porcelain` clean.
- [ ] `XCP_PYTEST_ARGS` back to `""` if it was seeded at any point.
