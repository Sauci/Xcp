/**
 * @file Xcp_Pgm.c
 * @author
 * @date
 *
 * @defgroup XCP_PGM_C NON-VOLATILE MEMORY PROGRAMMING command group implementation
 * @ingroup XCP
 */

#include "Xcp_Internal.h"

#if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON)

/*------------------------------------------------------------------------------------------------*/
/* local function declarations (static).                                                          */
/*------------------------------------------------------------------------------------------------*/

/**
 * @brief Finishes PROGRAM_START, building the positive response or ERR_GENERIC from statusCode.
 * @details Forward-declared because Xcp_DTOCmdPgmProgramStart below calls it directly for an
 * integrator whose work completes instantaneously (spec §4) -- the same function
 * Xcp_PgmCompletePendingCommand dispatches to when the same command instead completes on a later
 * Xcp_MainFunction poll.
 */
static void Xcp_PgmCompleteProgramStart(uint8 statusCode);

/**
 * @brief Finishes PROGRAM_RESET, building the positive response or ERR_GENERIC from statusCode.
 * @details Forward-declared for the same reason Xcp_PgmCompleteProgramStart above is:
 * Xcp_DTOCmdPgmProgramReset below calls it directly for an integrator whose work completes
 * instantaneously (spec Section 4) -- the same function Xcp_PgmCompletePendingCommand dispatches
 * to when the same command instead completes on a later Xcp_MainFunction poll.
 */
static void Xcp_PgmCompleteProgramReset(uint8 statusCode);

/**
 * @brief Finishes PROGRAM_PREPARE, building the positive response or ERR_GENERIC from statusCode.
 * @details Forward-declared for the same reason Xcp_PgmCompleteProgramStart above is:
 * Xcp_DTOCmdPgmProgramPrepare below calls it directly for an integrator whose work completes
 * instantaneously (spec Section 4) -- the same function Xcp_PgmCompletePendingCommand dispatches
 * to when the same command instead completes on a later Xcp_MainFunction poll.
 */
static void Xcp_PgmCompleteProgramPrepare(uint8 statusCode);

/*------------------------------------------------------------------------------------------------*/
/* command handler definitions.                                                                   */
/*------------------------------------------------------------------------------------------------*/

uint8 Xcp_DTOCmdPgmProgramStart(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    /* 1.1/1.6.5.1.1: the sequence is opened once and closed by PROGRAM_RESET. A second
     * PROGRAM_START inside an open session is out of sequence, and 1.1/1.7.3.2.4 lists
     * ERR_SEQUENCE for the programming commands. */
    if (Xcp_Internal.pgm_state != XCP_PGM_IDLE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        uint8 status_code = 0x00u;

        Xcp_Internal.pgm_state = XCP_PGM_STARTING;

        /* The FIRST call happens here, not on the next Xcp_MainFunction, and it is what makes the
         * deferral optional rather than mandatory: an integrator whose work is instantaneous
         * returns E_OK from it and the master is answered on this very exchange, with no
         * main-function cycle and no EV_CMD_PENDING in between. Spec §4. */
        if (Xcp_ProgramStart(&status_code) == E_OK)
        {
            Xcp_PgmCompleteProgramStart(status_code);
        }
        else
        {
            Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM_START;
            Xcp_Internal.pending_command.active = TRUE;
            Xcp_Internal.pending_command.abandoned = FALSE;
            Xcp_Internal.pending_command.event_outstanding = FALSE;

            /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
            *responseExpected = FALSE;
        }
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmProgramReset(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8 status_code = 0x00u;

    (void)pPduInfo;

    *responseExpected = TRUE;

    /* 1.1/1.6.5.1.4: "This command may be used to force a slave device reset for other purposes."
     * Unlike PROGRAM_START just above, this carries no gate on Xcp_Internal.pgm_state -- it is
     * accepted from XCP_PGM_IDLE exactly as it is from XCP_PGM_ACTIVE. DD57. */
    if (Xcp_ProgramReset(&status_code) == E_OK)
    {
        Xcp_PgmCompleteProgramReset(status_code);
    }
    else
    {
        Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM_RESET;
        Xcp_Internal.pending_command.active = TRUE;
        Xcp_Internal.pending_command.abandoned = FALSE;
        Xcp_Internal.pending_command.event_outstanding = FALSE;

        /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
        *responseExpected = FALSE;
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmProgramPrepare(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8 status_code = 0x00u;
    uint16 code_size;

    *responseExpected = TRUE;

    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &code_size, Xcp_Ptr->general->byteOrder);

    /* 1.1/1.6.5.2.3: "This optional command is used to indicate the begin of a code download as a
     * precondition for non-volatile memory programming." Unlike PROGRAM_START above, this carries
     * no gate on Xcp_Internal.pgm_state at all -- a precondition FOR a sequence precedes it, so it
     * is legal from XCP_PGM_IDLE and from XCP_PGM_ACTIVE alike. Design §4.
     *
     * The FIRST call happens here, not on the next Xcp_MainFunction, for the same reason
     * PROGRAM_START's own first call does above: an integrator whose work is instantaneous returns
     * E_OK from it and the master is answered on this very exchange. Spec §4. */
    if (Xcp_ProgramPrepare(Xcp_Internal.memory_transfer.address, code_size, &status_code) == E_OK)
    {
        Xcp_PgmCompleteProgramPrepare(status_code);
    }
    else
    {
        Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM_PREPARE;
        Xcp_Internal.pending_command.active = TRUE;
        Xcp_Internal.pending_command.abandoned = FALSE;
        Xcp_Internal.pending_command.event_outstanding = FALSE;
        /* Xcp_ProgramPrepare's contract takes codeSize on every call, not only this first one, and
         * Xcp_PgmPollPendingCommand (below) has no other way to recover it once this handler
         * returns -- the MTA needs no equivalent, since Xcp_Internal.memory_transfer.address is
         * itself standing state it can re-read directly. */
        Xcp_Internal.pending_command.program_prepare_code_size = code_size;

        /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
        *responseExpected = FALSE;
    }

    return E_OK;
}

/*------------------------------------------------------------------------------------------------*/
/* deferred-response machinery, called from Xcp_MainFunction (DD53).                              */
/*------------------------------------------------------------------------------------------------*/

Std_ReturnType Xcp_PgmPollPendingCommand(uint8 *pStatusCode)
{
    Std_ReturnType result;

    /* A switch on the pending PID, not a function pointer stored in the slot: this keeps each
     * command's poll and its response shape (built by the matching *Complete* function below)
     * adjacent in this one file instead of splitting them across a pointer and its target. Tasks 4
     * and 5 add one case each here; a hard-coded single-command function would block both. */
    switch (Xcp_Internal.pending_command.pid)
    {
        case XCP_PID_CMD_PROGRAM_START:
        {
            result = Xcp_ProgramStart(pStatusCode);
            break;
        }
        case XCP_PID_CMD_PROGRAM_RESET:
        {
            result = Xcp_ProgramReset(pStatusCode);
            break;
        }
        case XCP_PID_CMD_PROGRAM_PREPARE:
        {
            /* Unlike the two cases above, Xcp_ProgramPrepare's contract also takes address and
             * codeSize on every call. The MTA is re-read from Xcp_Internal.memory_transfer.address
             * directly -- stable for the duration, since DD55's ERR_CMD_BUSY gate refuses any
             * interloping SET_MTA -- and codeSize comes from the slot, which is the only place
             * left holding it once the handler that parsed it from the request has returned. */
            result = Xcp_ProgramPrepare(Xcp_Internal.memory_transfer.address,
                                        Xcp_Internal.pending_command.program_prepare_code_size,
                                        pStatusCode);
            break;
        }
        default:
        {
            /* Unreachable: pending_command.pid is set only by a handler in this file, to one of
             * the PIDs handled above, at the same time pending_command.active is set to TRUE. */
            result = E_OK;
            break;
        }
    }

    return result;
}

void Xcp_PgmCompletePendingCommand(uint8 statusCode)
{
    const uint8 pid = Xcp_Internal.pending_command.pid;
    const boolean abandoned = Xcp_Internal.pending_command.abandoned;

    /* Released before dispatching, not after: the per-command completion function below is what
     * fills Xcp_Internal.cto_response, and pending_command has nothing further to say once its
     * PID has been read into a local above. */
    Xcp_Internal.pending_command.pid = 0x00u;
    Xcp_Internal.pending_command.active = FALSE;
    Xcp_Internal.pending_command.abandoned = FALSE;

    /* abandoned (set by SYNCH, Task 3) means the master has already moved on: the response is
     * built by nobody and transmitted to nobody. Polling still ran to completion either way --
     * Xcp_MainFunction only stops polling once this function is reached at all -- so the
     * integrator's callback was always called until it finished. */
    if (abandoned == FALSE)
    {
        switch (pid)
        {
            case XCP_PID_CMD_PROGRAM_START:
            {
                Xcp_PgmCompleteProgramStart(statusCode);
                break;
            }
            case XCP_PID_CMD_PROGRAM_RESET:
            {
                Xcp_PgmCompleteProgramReset(statusCode);
                break;
            }
            case XCP_PID_CMD_PROGRAM_PREPARE:
            {
                Xcp_PgmCompleteProgramPrepare(statusCode);
                break;
            }
            default:
            {
                /* Unreachable: see Xcp_PgmPollPendingCommand above. */
                break;
            }
        }
    }
}

void Xcp_PgmRequestPending(void)
{
    /* 1.1/1.7.2.4.2: the slave asks the master to restart its time-out. Bounded to ONE outstanding
     * event, never emitted on a schedule: Xcp_MainFunction is cyclic per SWS_Xcp_00824 but the
     * module may never depend on its period, so any counter here would set a rate out of a number
     * the module is not allowed to know. With the bound, the rate follows TxConfirmation, which
     * SWS_Xcp_00859 already makes the module wait for -- a property of the bus, which is real. */
    if (Xcp_Internal.pending_command.event_outstanding == FALSE)
    {
        Std_ReturnType push_result;

        /* Only the push is inside the area; it shares the event queue with Xcp_MainFunction's
         * EV_STORE_CAL and Xcp_TriggerEventChannel's EV_DAQ_OVERLOAD, and Xcp_TransmitOneFrame
         * reads read/write under the same area. */
        SchM_Enter_Xcp_DtoQueue();
        push_result = Xcp_EventQueuePush(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue,
                                         XCP_PID_EVENT,
                                         XCP_EVENT_CMD_PENDING,
                                         NULL_PTR,
                                         0x00000000u);
        SchM_Exit_Xcp_DtoQueue();

        /* Review finding 5: a failed push must leave event_outstanding FALSE, not TRUE -- only a
         * successful pop clears it (Xcp_CanIfTxConfirmation), so marking one outstanding here
         * without actually queuing it would starve every later busy poll of a retry, permanently,
         * for the rest of this operation. Deliberately does not report XCP_E_EVENT_QUEUE_FULL the
         * way Xcp_MainFunction's EV_STORE_CAL push does (Xcp_MainFunction, STORE_CAL_REQ block):
         * EV_STORE_CAL is one-shot, so a failed push loses that notification forever and is worth
         * a diagnostic; EV_CMD_PENDING already retries here on every subsequent busy poll while
         * event_outstanding stays FALSE, and a busy erase can hold that poll open for a long time,
         * so reporting on every failed attempt would itself become the kind of flood DD54 exists
         * to prevent applied to the diagnostic channel instead of the wire. */
        if (push_result == E_OK)
        {
            Xcp_Internal.pending_command.event_outstanding = TRUE;
            Xcp_Internal.event.successful_transmission_pending = TRUE;
        }
    }
}

void Xcp_PgmAbandonPendingCommand(void)
{
    /* DD55. Called from Xcp_CanIfRxIndication's ERR_CMD_BUSY gate (Xcp.c), and only while
     * pending_command.active is TRUE -- there is nothing to abandon otherwise, and this function
     * must not be the thing that decides that.
     *
     * `active` is deliberately left untouched. Xcp_MainFunction polls only while it is TRUE
     * (Xcp_MainFunction, Xcp.c), so clearing it here would stop that polling and strand the
     * integrator mid-operation: its callback would never be called again, would never report
     * completion, and a later PROGRAM_START would start a second operation on top of one still
     * running. `abandoned` alone tells Xcp_PgmCompletePendingCommand to discard the response
     * instead of transmitting it once polling finally reaches E_OK.
     *
     * pgm_state is reset to XCP_PGM_IDLE ONLY when the abandoned command is PROGRAM_START (DD55,
     * corrected by Task 5's review). PROGRAM_START is the one command whose handler sets a
     * TRANSIENT state (XCP_PGM_STARTING, Xcp_DTOCmdPgmProgramStart above) before deferring, and
     * undoing exactly that transient state is what this reset means -- as far as the master is
     * concerned, the sequence it started never happened. PROGRAM_RESET and PROGRAM_PREPARE set no
     * such transient state before deferring: both can be pending while pgm_state is
     * XCP_PGM_ACTIVE, a real, already-established session (PROGRAM_RESET legally from ACTIVE per
     * DD57; PROGRAM_PREPARE legally from ACTIVE too, e.g. a second code block mid-session). An
     * earlier, unconditional version of this reset ended such a session silently on any ordinary
     * SYNCH, which 1.1/1.7.1.1 requires to stay available throughout one: DD51's gate stopped
     * firing for the rest of the session, and a second PROGRAM_START was then accepted where DD49
     * requires ERR_SEQUENCE, with the master told nothing. The design doc's own DD55 text
     * previously read "pgm_state returns to IDLE" with no such qualification; both the code and
     * that sentence are corrected together here.
     *
     * pending_command.active staying TRUE regardless of which command it is is what still refuses
     * a new one with ERR_CMD_BUSY (DD55 in Xcp.c), because that gate reads active, not pgm_state;
     * the two facts are real and different, and deliberately not merged into one flag. */
    Xcp_Internal.pending_command.abandoned = TRUE;

    if (Xcp_Internal.pending_command.pid == XCP_PID_CMD_PROGRAM_START)
    {
        Xcp_Internal.pgm_state = XCP_PGM_IDLE;
    }
}

/*------------------------------------------------------------------------------------------------*/
/* local function definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

static void Xcp_PgmCompleteProgramStart(uint8 statusCode)
{
    if (statusCode == 0x00u)
    {
        /* 1.1/1.6.5.1.1's COMM_MODE_PGM byte, built from the same three flags
         * Xcp_DTOCmdStdGetCommModeInfo (Xcp_Std.c) reads for GET_COMM_MODE_INFO's COMM_MODE_OPTIONAL,
         * at the bit positions this byte's own layout gives them (DD56). */
        uint8 comm_mode_pgm = 0x00u;

        Xcp_Internal.pgm_state = XCP_PGM_ACTIVE;

        if (Xcp_Ptr->general->masterBlockModeSupported == TRUE)
        {
            comm_mode_pgm |= (0x01u << 0x00u);
        }

        if (Xcp_Ptr->general->interleavedModeSupported == TRUE)
        {
            comm_mode_pgm |= (0x01u << 0x01u);
        }

        if (Xcp_Ptr->general->slaveBlockModeSupported == TRUE)
        {
            comm_mode_pgm |= (0x01u << 0x06u);
        }

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = comm_mode_pgm;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = (uint8)Xcp_Ptr->general->maxCto;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = Xcp_Ptr->general->maxBS;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = Xcp_Ptr->general->minST;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u] = Xcp_Ptr->general->ctoQueueSize;

        Xcp_FinalizeResPacket(0x07u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* 1.1/1.6.5.1.1 names ERR_GENERIC for a slave "not in a state which permits programming".
         * pgm_state returns to IDLE, not STARTING: a module that stayed STARTING here would refuse
         * every later PROGRAM_START with ERR_SEQUENCE instead of letting the master retry. */
        Xcp_Internal.pgm_state = XCP_PGM_IDLE;

        Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC, &Xcp_Internal.cto_response.pdu_info);
    }

    /* Publishes for both outcomes alike, matching the STORE_CAL_REQ path in Xcp_MainFunction. */
    Xcp_Internal.cto_response.successful_transmission_pending = TRUE;
}

static void Xcp_PgmCompleteProgramReset(uint8 statusCode)
{
    if (statusCode == 0x00u)
    {
        /* 1.1/1.6.5.1.4's response is PID only -- no COMM_MODE_PGM/MAX_CTO_PGM/etc. the way
         * PROGRAM_START's is, and no error table of its own either (§1.7.3.2.4 lists none for this
         * command), so success is simply this one byte. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);

        /* DD57 (fix round 1): the disconnect happens here, in the completion, immediately after
         * the response is built -- not deferred to the response's confirmation. That deferred form
         * was tried first and broke twice over, both measured on the shipped tree: nothing can bind
         * a later confirmation to THIS specific response, since cto_response.pdu_info is one shared
         * buffer and Xcp_MainFunction is aperiodic, so any command arriving before the next poll
         * silently replaced the response and the slave disconnected on THAT frame's confirmation
         * instead -- and it skipped the DAQ_DYNAMIC unwind entirely, leaking an allocation into the
         * next session. Xcp_DisconnectSession (Xcp_Std.c) is the identical unwind
         * Xcp_CTOCmdStdDisconnect calls, shared so the two doors cannot diverge again; the
         * in-handler ordering is immune to the first problem for the same reason DISCONNECT's own
         * answer already is -- Xcp_CanIfRxIndication's disconnected-state gate (Xcp.c) drops any
         * further command before it can touch the buffer, once connection_status is set below.
         *
         * pgm_state returns to IDLE here too, which Xcp_DisconnectSession does not do on its own
         * (plain DISCONNECT has no programming session to end). The only other writer of pgm_state
         * while a session is ACTIVE is Xcp_PgmAbandonPendingCommand (DD55), and it is conditioned
         * to touch pgm_state only when the abandoned command is PROGRAM_START -- which can only be
         * pending while pgm_state is XCP_PGM_STARTING, never XCP_PGM_ACTIVE, since
         * Xcp_DTOCmdPgmProgramStart refuses a second PROGRAM_START with ERR_SEQUENCE before ever
         * reaching ACTIVE. So nothing else resets an ACTIVE pgm_state, and leaving it ACTIVE here
         * would refuse a later, genuinely new session's own PROGRAM_START with ERR_SEQUENCE. No
         * device reset is performed here or anywhere else in this module: DD50. */
        Xcp_Internal.pgm_state = XCP_PGM_IDLE;
        Xcp_DisconnectSession();
    }
    else
    {
        /* Spec §4 (this module's own polled-callback contract, copied from
         * Xcp_StoreCalibrationDataToNonVolatileMemory and Xcp_ProgramStart above): E_OK with a
         * non-zero statusCode means the operation finished, but unsuccessfully. Answered
         * ERR_GENERIC, matching Xcp_PgmCompleteProgramStart's own failure path; nothing about the
         * session or the connection changes -- there is no positive response here to hang a
         * disconnect off of, and the master may simply try again. */
        Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC, &Xcp_Internal.cto_response.pdu_info);
    }

    /* Publishes for both outcomes alike, matching Xcp_PgmCompleteProgramStart above. */
    Xcp_Internal.cto_response.successful_transmission_pending = TRUE;
}

static void Xcp_PgmCompleteProgramPrepare(uint8 statusCode)
{
    if (statusCode == 0x00u)
    {
        /* 1.1/1.6.5.2.3 specifies no response payload beyond the standard positive response --
         * unlike PROGRAM_START's COMM_MODE_PGM byte and friends, there is nothing else to report
         * here, matching PROGRAM_RESET's own success response just above. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* 1.1/1.6.5.2.3: "The slave device has to make sure that the target memory area is
         * available and it is in a operational state which permits the download of code. If not,
         * a ERR_GENERIC will be returned." */
        Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC, &Xcp_Internal.cto_response.pdu_info);
    }

    /* Publishes for both outcomes alike, matching Xcp_PgmCompleteProgramStart above. */
    Xcp_Internal.cto_response.successful_transmission_pending = TRUE;
}

#endif /* #if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON) */
