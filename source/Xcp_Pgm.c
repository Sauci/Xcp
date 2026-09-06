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
     * PROGRAM_START inside an open session is refused ERR_GENERIC (0x31), not ERR_SEQUENCE.
     *
     * Final-review finding 4 corrected this, and the correction is a statement about THIS command's
     * own row: §1.7.3.2.5 -- the PGM error-handling matrix; §1.7.3.2.4 is DAQ's, and every citation
     * of it for a PGM row in this sub-project was a numbering mistake -- lists ERR_CMD_BUSY,
     * ERR_DAQ_ACTIVE, ERR_CMD_SYNTAX, ERR_ACCESS_LOCKED and ERR_GENERIC for PROGRAM_START and
     * nothing else. Xcp_CTOErrorMatrix[0xD2] (source/Xcp.c) agrees: it carries no
     * XCP_INTERNAL_ERR_SEQUENCE. §1.6.5.1.1 then names the code for exactly this condition -- "If
     * the slave device is not in a state which permits programming, a ERR_GENERIC will be returned"
     * -- whose prescribed master action, "restart session", is also the only recovery available to
     * a master that has lost track of a sequence it left open.
     *
     * ERR_SEQUENCE, which DD49 originally chose, is right for a different thing: §1.7.3.2.5 does
     * list it for PROGRAM_CLEAR, PROGRAM and PROGRAM_MAX, so it is the code for the gate those
     * commands will meet in SP4b when they are asked to run outside a session. It is not this
     * command's own refusal, and the two must not be conflated again. */
    if (Xcp_Internal.pgm_state != XCP_PGM_IDLE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_GENERIC, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        uint8 status_code = 0x00u;

        /* No transient state is entered here before deferring, and Xcp_PgmStateType consequently
         * has two values rather than three (source/Xcp_Internal.h). DD49 gave the third one,
         * XCP_PGM_STARTING, the job of telling Xcp_MainFunction whether a finished PROGRAM_START
         * should move to ACTIVE or back to IDLE; Xcp_PgmCompleteProgramStart below decides that
         * from statusCode alone and never reads pgm_state, and no other reader could distinguish
         * STARTING from IDLE either -- Xcp.c's DD51 gate tests != XCP_PGM_ACTIVE, and this
         * handler's own != XCP_PGM_IDLE test above is unreachable throughout the deferral because
         * DD55's ERR_CMD_BUSY gate refuses every command but SYNCH while pending_command.active is
         * TRUE. It was written and never read (final-review finding 6), so the enumerator is gone
         * and pgm_state stays XCP_PGM_IDLE until the operation actually succeeds.
         *
         * The FIRST call happens here, not on the next Xcp_MainFunction, and it is what makes the
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
     * pgm_state is deliberately NOT touched here, and that is a correction to DD55 as written.
     * Two earlier forms of this function did touch it. The first reset it unconditionally, which
     * silently ended an established session on any ordinary SYNCH -- 1.1/1.7.1.1 requires SYNCH to
     * stay available throughout one -- because PROGRAM_RESET and PROGRAM_PREPARE can both be
     * pending while pgm_state is XCP_PGM_ACTIVE (PROGRAM_RESET legally from ACTIVE per DD57;
     * PROGRAM_PREPARE legally too, e.g. a second code block mid-session). The second reset it only
     * for a pending PROGRAM_START, on the premise that PROGRAM_START's handler had entered a
     * TRANSIENT XCP_PGM_STARTING before deferring and that this undid exactly that. Final-review
     * finding 6 removed that transient state, because nothing ever read it: Xcp_DTOCmdPgmProgramStart
     * above now leaves pgm_state at XCP_PGM_IDLE for the whole deferral, so a PROGRAM_START
     * abandoned here has no state to undo and the write became a provable no-op rather than a
     * guard. It is deleted rather than kept as one, so no later reader mistakes it for something a
     * test could reach.
     *
     * The invariant that replaces it: an abandoned PROGRAM_START never reaches
     * Xcp_PgmCompleteProgramStart at all (Xcp_PgmCompletePendingCommand's `abandoned == FALSE`
     * guard above), and that function is this module's only writer of XCP_PGM_ACTIVE -- so the
     * session the master walked away from is never opened, which is what the old reset was reaching
     * for. Should a future command's handler ever move pgm_state before deferring, that handler
     * owns the unwind and this function has to be revisited alongside it.
     *
     * pending_command.active staying TRUE regardless of which command it is is what still refuses
     * a new one with ERR_CMD_BUSY (DD55 in Xcp.c), because that gate reads active, not pgm_state;
     * the two facts are real and different, and deliberately not merged into one flag. */
    Xcp_Internal.pending_command.abandoned = TRUE;
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
         *
         * pgm_state is NOT written here, and the absence is deliberate. A revision of this branch
         * assigned XCP_PGM_IDLE, justified by a third enumerator XCP_PGM_STARTING that a deferring
         * PROGRAM_START used to enter -- with that gone, the handler only accepts from IDLE and
         * nothing writes the field in between, so the assignment stored a value the field already
         * held. Deleted rather than left as a comment describing a module that no longer exists,
         * the same way Xcp_PgmAbandonPendingCommand's equivalent was. */
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
         * PROGRAM_START's is -- so success is simply this one byte.
         *
         * An earlier version of this comment added "and no error table of its own either
         * (§1.7.3.2.4 lists none for this command)". Both halves were wrong, and final-review
         * finding 5 replaced them with what the specification actually says. The PGM error matrix
         * is §1.7.3.2.5 (§1.7.3.2.4 is DAQ's), and PROGRAM_RESET's row there lists five codes:
         * ERR_CMD_BUSY, ERR_PGM_ACTIVE, ERR_CMD_SYNTAX and ERR_SEQUENCE in 1.0, plus
         * ERR_ACCESS_LOCKED and ERR_RES_TEMP_NOT_ACCESSIBLE in 1.1. Xcp_CTOErrorMatrix[0xCF]
         * (source/Xcp.c) deviates from that row in two directions, both deliberate:
         *
         *  - It DROPS XCP_INTERNAL_ERR_PGM_ACTIVE, and must. DD51 makes an ACTIVE session fire the
         *    generic ERR_PGM_ACTIVE gate (Xcp_CanIfRxIndication, Xcp.c), so a row carrying that bit
         *    would refuse the one command whose entire purpose is to leave the state -- the same
         *    unrecoverable session final-review finding 1 closed from the other end. Dropping
         *    XCP_INTERNAL_ERR_SEQUENCE alongside it is cosmetic: no code path produces it here.
         *  - It ADDS XCP_INTERNAL_ERR_GENERIC, which neither revision lists for this command. The
         *    else branch below needs a code for an integrator that reports failure, and of the
         *    listed five only ERR_SEQUENCE could be pressed into service -- a worse fit, since
         *    nothing about the request is out of sequence. ERR_GENERIC is kept as the recorded
         *    deviation (DD57) rather than exchanged for a listed code that would mislead. */
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
         * pgm_state returns to IDLE here too, which Xcp_DisconnectSession does not do on its own.
         * The reason given for that used to be "plain DISCONNECT has no programming session to
         * end", and it was simply false: a plain DISCONNECT arriving during a session is refused
         * ERR_PGM_ACTIVE by DD51's gate and never reaches that unwind at all, so the sentence
         * described a case that cannot happen while claiming it as the justification (final-review
         * finding 1). The real reason is ownership: this is the command that ENDS a sequence, so
         * this is where the sequence's own state is cleared, and Xcp_DisconnectSession stays the
         * connection-level unwind DISCONNECT and PROGRAM_RESET genuinely share. The session state
         * that a master abandoning its connection would otherwise leak into the next session is
         * cleared by Xcp_CTOCmdStdConnect (Xcp_Std.c) instead, on the one door that is always
         * reachable.
         *
         * Xcp_PgmAbandonPendingCommand (DD55) no longer writes pgm_state at all (final-review
         * finding 6), so this and Xcp_CTOCmdStdConnect are its two writers outside Xcp_Init -- and
         * the honest consequence of that pair is that THIS write is no longer observable. A
         * successful PROGRAM_RESET disconnects on the next line; the disconnected-state gate
         * (Xcp_CanIfRxIndication, Xcp.c) then admits nothing but CONNECT; and CONNECT resets
         * pgm_state itself. Deleting this line therefore changes no wire behaviour and fails no
         * test -- measured, not assumed. It is kept anyway, as documented defence in depth beside
         * the two guards in Xcp.c (design §9 criterion 7): the command that ends a programming
         * sequence is where that sequence's state belongs, and the alternative would leave this
         * function correct only by virtue of a line in Xcp_Std.c. The invariant it rests on is
         * that CONNECT is the only way back from the disconnected state; a change that let any
         * other command through would make this line load-bearing again, with no test to notice.
         *
         * No device reset is performed here or anywhere else in this module: DD50. */
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
