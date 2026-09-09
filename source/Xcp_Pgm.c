/**
 * @file Xcp_Pgm.c
 * @author
 * @date
 *
 * @defgroup XCP_PGM_C NON-VOLATILE MEMORY PROGRAMMING command group implementation
 * @ingroup XCP
 */

#include "Xcp_Internal.h"

/* Xcp_PgmRequestPending (below) reads Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue, the same way
 * Xcp.c/Xcp_Pag.c/Xcp_Daq.c/Xcp_DaqRuntime.c each already do -- and, like them, needs its own
 * #include: Xcp_Internal.h does not carry one, and interface/Xcp.h's own `extern Xcp_RtType
 * Xcp_Rt[];` is wrapped in `#ifdef CFFI_ENABLE`, invisible to a real (non-CFFI) build. Found
 * while proving final-review F1's fix compiles for real: XCP_MAX_CTO/XCP_PGM_MAX_BLOCK_SIZE were
 * the only undeclared identifiers the review's own repro reached (Xcp_Internal.h is the first
 * thing every translation unit includes, so the build stopped there before make ever reached this
 * file), but this file alone was still one #include short of compiling once that fix let the
 * build get this far. */
#include "Xcp_Rt.h"

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

/**
 * @brief Finishes PROGRAM_CLEAR, building the positive response or ERR_ACCESS_DENIED from
 * statusCode.
 * @details Forward-declared for the same reason Xcp_PgmCompleteProgramStart above is:
 * Xcp_DTOCmdPgmProgramClear below calls it directly for an integrator whose work completes
 * instantaneously (spec Section 4) -- the same function Xcp_PgmCompletePendingCommand dispatches
 * to when the same command instead completes on a later Xcp_MainFunction poll.
 */
static void Xcp_PgmCompleteProgramClear(uint8 statusCode);

/**
 * @brief Finishes PROGRAM, PROGRAM_MAX and PROGRAM_NEXT, building the positive response or
 * ERR_ACCESS_DENIED from statusCode, and advancing the MTA on success only (DD66).
 * @details Forward-declared for the same reason Xcp_PgmCompleteProgramStart above is:
 * Xcp_DTOCmdPgmProgram, Xcp_DTOCmdPgmProgramMax and Xcp_DTOCmdPgmProgramNext below all call it
 * directly for an integrator whose work completes instantaneously (spec Section 4) -- the same
 * function Xcp_PgmCompletePendingCommand dispatches to when any of the three instead completes on
 * a later Xcp_MainFunction poll. Shared between all three commands (PROGRAM and PROGRAM_MAX since
 * Task 3; PROGRAM_NEXT joins them in Task 4, DD63) because all three write through the identical
 * Xcp_ProgramWrite contract, from the identical Xcp_Internal.pgm_block standing state -- there is
 * nothing left to distinguish once the write itself has been issued, whether that buffer holds one
 * frame's own bytes or several PROGRAM_NEXT frames' accumulated ones.
 */
static void Xcp_PgmCompleteProgramWrite(uint8 statusCode);

/**
 * @brief Finishes PROGRAM_VERIFY, building the positive response or ERR_VERIFY from statusCode.
 * @details Forward-declared for the same reason Xcp_PgmCompleteProgramStart above is:
 * Xcp_DTOCmdPgmProgramVerify below calls it directly for an integrator whose work completes
 * instantaneously (spec Section 4) -- the same function Xcp_PgmCompletePendingCommand dispatches to
 * when the same command instead completes on a later Xcp_MainFunction poll.
 */
static void Xcp_PgmCompleteProgramVerify(uint8 statusCode);

/**
 * @brief Whether a PGM master block mode block is currently open, awaiting a PROGRAM_NEXT.
 * @details Task 4 fix round 1, finding 1. Reads Xcp_Internal.pgm_block.requested_elements, PGM's
 * OWN counter -- deliberately not Xcp_BlockTransferIsActive()/Xcp_Internal.block_transfer, which
 * Xcp_CanIfTxConfirmation (source/Xcp.c) also reads, unconditionally, to decide whether to keep
 * streaming an UPLOAD. A PGM block staying open across several unrelated command/response
 * exchanges -- a refused PROGRAM_MAX, legal mid-sequence per 1.1/1.6.5.1.1 -- must never look like
 * an outstanding UPLOAD to that confirmation path, or it disclosed slave memory on the wire
 * (source/Xcp_Internal.h, pgm_block's own comment; task-4-report.md, "Fix round 1", finding 1).
 * Mirrors Xcp_BlockTransferIsActive()'s own shape exactly, against pgm_block instead of
 * block_transfer.
 *
 * SET_MTA used to be named here as a second such exchange and no longer is: since final review F1
 * it ABORTS the open block (Xcp_PgmFormatReset below), so no block survives it to be confirmed
 * across. The separate-state argument above is unchanged and still load-bearing -- a refused
 * PROGRAM_MAX still leaves a block open across its own confirmed error response, which is trigger
 * enough on its own, and F1's abort is a fix for a different defect that must not be mistaken for
 * this one's.
 */
static boolean Xcp_PgmBlockIsActive(void);

/**
 * @brief Subtracts the current frame's own contribution from what a PGM block still needs.
 * @details Task 4 fix round 1, finding 1. Mirrors Xcp_BlockTransferAcknowledgeFrame()'s own shape
 * exactly, against Xcp_Internal.pgm_block instead of block_transfer -- see Xcp_PgmBlockIsActive
 * above for why the two must not share state.
 */
static void Xcp_PgmBlockAcknowledgeFrame(void);

/**
 * @brief Whether DD90's REQUIRED gate refuses a data transfer request right now.
 * @details SP4c Task 3. Design doc DD90, 1.1/1.6.5.2.4: "If modified data transmission is expected
 * by the slave and no PROGRAM_FORMAT command is transmitted, the slave responds with
 * ERR_SEQUENCE." A compound condition, one term per REQUIRED bit, checked against
 * Xcp_Internal.pgm_format's own matching field rather than against a separate "has PROGRAM_FORMAT
 * been called" flag: 1.1/1.6.5.2.4 makes an all-defaults request the same thing as the command
 * never having been sent, and DD85 already resets pgm_format to that same all-defaults state at
 * every session boundary and at SET_MTA -- so a field still reading 0x00u here means exactly what
 * this gate needs to know, with no state of its own to keep in step. Shared by
 * Xcp_DTOCmdPgmProgram, Xcp_DTOCmdPgmProgramMax and Xcp_DTOCmdPgmProgramNext below, all three of
 * which DD90 names by name ("listed in all three rows").
 */
static boolean Xcp_PgmDataTransferRefusedByFormat(void);

/**
 * @brief Counts one accepted data transfer request into the Block Sequence Counter.
 * @details SP4c Task 6. Design doc DD86, 1.1/1.6.5.1.3: "Its value is incremented by 1 for each
 * subsequent data transfer request. At the maximum value the Block Sequence Counter rolls over and
 * starts at 0x00 with the next data transfer request message." Called from Xcp_DTOCmdPgmProgram,
 * Xcp_DTOCmdPgmProgramMax and Xcp_DTOCmdPgmProgramNext below -- the three commands DD86 names --
 * at the point each one accepts a frame's data, so a refused request never counts and a master
 * that was told ERR_SEQUENCE or ERR_CMD_SYNTAX stays in step with this slave's own count.
 * See Xcp_Internal.pgm_block_sequence_counter's own comment (source/Xcp_Internal.h) for why the
 * advance happens BEFORE the value is used, and for why the rollover needs no branch here.
 */
static void Xcp_PgmAdvanceBlockSequenceCounter(void);

/**
 * @brief Hands the block currently in Xcp_Internal.pgm_block to whichever write callback this
 * stream's access mode calls for, and reports what it answered.
 * @details SP4c Task 6, design doc DD84/DD85. PROGRAM_FORMAT's own access method
 * (Xcp_Internal.pgm_format.access_method) selects between Xcp_ProgramWrite -- absolute access, the
 * MTA is an address -- and Xcp_ProgramWriteFunctional, which takes no address at all and receives
 * the Block Sequence Counter instead (1.6.5.1.3: "the ECU software knows the start address for the
 * new flash content automatically"). Any non-zero access method selects the functional callback,
 * user-defined values (0x80..0xFF) included, matching Xcp_DTOCmdPgmProgramFormat's own fourth DD89
 * term, which admits them on the identical FUNCTIONAL_MODE bit and gives them no separate meaning.
 *
 * One helper rather than the same if/else written out four times, and specifically so that
 * Xcp_PgmPollPendingCommand below cannot dispatch a later poll to a DIFFERENT callback than the
 * handler's own first call reached: both go through this function, reading the same standing state.
 * That is the defect PROGRAM_CLEAR needed a dedicated pending_command.program_clear_functional flag
 * to avoid (Task 5) -- not needed here, because pgm_format is standing session state that DD55's
 * ERR_CMD_BUSY gate keeps stable for the duration of a deferred command, exactly as it keeps the
 * MTA and pgm_block stable, whereas PROGRAM_CLEAR's own mode arrives in the request and is gone.
 *
 * Final review F1: DD55's gate is the whole of the argument only for the DEFERRED window, where
 * pending_command.active is TRUE (source/Xcp.c). It never covered the OTHER window this state has
 * to survive -- a master block mode block open between an intermediate PROGRAM and its completing
 * PROGRAM_NEXT, where no command is pending and cto_response.successful_transmission_pending is
 * FALSE, so DD55's gate is wide open and both PROGRAM_FORMAT (0xCB) and SET_MTA (0xF6) dispatch
 * normally. Two additions close it, and between them the "reading the same standing state" claim
 * above is now true for both windows rather than only one: Xcp_DTOCmdPgmProgramFormat below refuses
 * ERR_SEQUENCE while a block is open, and Xcp_PgmFormatReset below aborts the block, so no path
 * reaches this function with an access method other than the one the block's own opening frame was
 * accepted under. Each carries its own specification reasoning at its own site.
 */
static Std_ReturnType Xcp_PgmCallProgramWrite(uint8 *pStatusCode);

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
        Xcp_Internal.pending_command.args.program_prepare_code_size = code_size;

        /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
        *responseExpected = FALSE;
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmProgramClear(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    *responseExpected = TRUE;

    /* 1.1/1.6.5.1.1 requires PROGRAM_CLEAR, PROGRAM, PROGRAM_NEXT and PROGRAM_MAX refused until
     * PROGRAM_START has succeeded -- SP4a implemented pgm_state for exactly this gate and had no
     * command yet to test it against (design doc Section 2); this is that gate's first real user.
     * 1.7.3.2.5 lists ERR_SEQUENCE on PROGRAM_CLEAR's own row for exactly this condition, unlike
     * PROGRAM_START's own ERR_GENERIC two hundred lines above -- the two commands fail closed in
     * different directions, and Xcp_DTOCmdPgmProgramStart's own comment above already explains why
     * the two codes must not be conflated. */
    if (Xcp_Internal.pgm_state != XCP_PGM_ACTIVE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    /* SP4c Task 5, design doc DD84/DD93: functional access mode. Checked here, ahead of the
     * unrecognised-mode refusal just below, so that refusal's own `!= 0x00u` no longer has to (and
     * no longer does) speak for 0x01 -- this branch does. DD93 is explicit that this mode byte is
     * independent of PROGRAM_FORMAT's own access method: read directly off THIS request, never off
     * Xcp_Internal.pgm_format.access_method, so a master may clear functionally and program
     * absolutely, or the reverse (1.1/1.6.5.2.4: "It is possible to use different access modes for
     * clearing and programming"). */
    else if (pPduInfo->SduDataPtr[0x01u] == 0x01u)
    {
        uint32 clear_range;

        /* Harmless ahead of the capability/reserved-bit checks just below: this only copies the
         * request's own raw bytes into a local, the same DWORD offset absolute mode reads, and
         * commits to no interpretation of them yet -- unlike calling Xcp_ProgramClear itself, which
         * the comment on the unrecognised-mode branch below warns against doing before the mode
         * byte is settled. 1.6.5.1.2 (both revisions): "The MTA has no influence on the clearing
         * functionality" under this mode, so Xcp_Internal.memory_transfer.address is never read in
         * this branch, unlike the absolute-mode branch below. */
        Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &clear_range, Xcp_Ptr->general->byteOrder);

        if (Xcp_Ptr->general->pgmClearFunctionalSupported != TRUE)
        {
            /* This build's own configuration does not offer Xcp_ProgramClearFunctional
             * (xcp_program_clear_functional_api_enable, config/xcp.schema.json) -- refused before
             * the area bitmask below is even validated, the same "nothing this build cannot honour
             * reaches the integrator" discipline Xcp_DTOCmdPgmProgramFormat's own DD89 check
             * follows against pgmProperties. */
            Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
        }
        /* 1.6.5.1.2 (both revisions) reserves 0x00000008..0x00000080 of the area bitmask; checked
         * as one mask (0x000000F8u covers exactly those five bits together), not five separate
         * equality checks, the same reasoning Xcp_DTOCmdPgmProgramVerify's own verificationType
         * check above gives: a master is free to combine a reserved bit with a defined one in the
         * same request, which a chain of `==` comparisons against only the single-bit values would
         * not catch. 0x00000001/0x02/0x04 (the three defined areas) and 0x00000100..0xFFFFFF00
         * (user defined) both pass this check untouched -- the latter is, by this same paragraph's
         * own words, the integrator's to interpret, not this module's to refuse. */
        else if ((clear_range & 0x000000F8u) != 0x00000000u)
        {
            Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
        }
        else
        {
            uint8 status_code = 0x00u;

            /* The FIRST call happens here, not on the next Xcp_MainFunction, for the identical
             * reason the absolute-mode branch below calls Xcp_ProgramClear at this same point. */
            if (Xcp_ProgramClearFunctional(clear_range, &status_code) == E_OK)
            {
                Xcp_PgmCompleteProgramClear(status_code);
            }
            else
            {
                Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM_CLEAR;
                Xcp_Internal.pending_command.active = TRUE;
                Xcp_Internal.pending_command.abandoned = FALSE;
                Xcp_Internal.pending_command.event_outstanding = FALSE;
                /* Told apart from an absolute-mode deferral by pid alone until now -- both share
                 * XCP_PID_CMD_PROGRAM_CLEAR, since DD93 keeps this one request's own mode byte from
                 * ever becoming a separate command -- so Xcp_PgmPollPendingCommand (below) also
                 * needs this flag to know which callback to re-invoke (source/Xcp_Internal.h,
                 * program_clear_functional's own comment). */
                Xcp_Internal.pending_command.program_clear_functional = TRUE;
                /* Xcp_ProgramClearFunctional's contract takes the area bitmask on every call, not
                 * only this first one, for the identical reason the absolute-mode branch below
                 * holds onto its own clear range the same way. */
                Xcp_Internal.pending_command.args.program_clear_range = clear_range;

                /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
                *responseExpected = FALSE;
            }
        }
    }
    /* 1.6.5.1.2 defines exactly two mode bytes, 0x00 (absolute access mode, default) and 0x01
     * (functional access mode, the branch immediately above) -- a table, an enumeration of the
     * values this command recognises at all, not a bit field with reserved-but-harmless positions.
     * Every other byte (0x02..0xFF) is therefore unrecognised regardless of what this build
     * configures for either mode, and is refused ERR_OUT_OF_RANGE, whose own 1.7.3.2.5 row lists
     * the action "retry other parameter". Checked, and refused, BEFORE the clear range is even read
     * below: 1.6.5.1.2 gives that same DWORD field completely different readings depending on the
     * mode -- a length in absolute mode, a bit mask of memory areas in functional mode -- so a
     * handler that read it as a length first would already have called Xcp_ProgramClear with
     * whatever the DWORD means as a length, under a mode byte the master may not have meant as
     * absolute at all. */
    else if (pPduInfo->SduDataPtr[0x01u] != 0x00u)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        uint8 status_code = 0x00u;
        uint32 clear_range;

        Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &clear_range, Xcp_Ptr->general->byteOrder);

        /* The FIRST call happens here, not on the next Xcp_MainFunction, for the same reason
         * PROGRAM_PREPARE's own first call does above: an integrator whose work is instantaneous
         * returns E_OK from it and the master is answered on this very exchange. Spec Section 4. */
        if (Xcp_ProgramClear(Xcp_Internal.memory_transfer.address, clear_range, &status_code) == E_OK)
        {
            Xcp_PgmCompleteProgramClear(status_code);
        }
        else
        {
            Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM_CLEAR;
            Xcp_Internal.pending_command.active = TRUE;
            Xcp_Internal.pending_command.abandoned = FALSE;
            Xcp_Internal.pending_command.event_outstanding = FALSE;
            /* SP4c Task 5: explicit, not merely defaulted -- this slot is shared with the
             * functional-mode branch above, so a stale TRUE left over from a previous deferral
             * must never be allowed to survive into this one. */
            Xcp_Internal.pending_command.program_clear_functional = FALSE;
            /* Xcp_ProgramClear's contract takes the clear range on every call, not only this
             * first one, and Xcp_PgmPollPendingCommand (below) has no other way to recover it once
             * this handler returns -- the same reason PROGRAM_PREPARE's own codeSize is held in
             * this union (source/Xcp_Internal.h). The MTA needs no equivalent, since
             * Xcp_Internal.memory_transfer.address is itself standing state it can re-read
             * directly. */
            Xcp_Internal.pending_command.args.program_clear_range = clear_range;

            /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
            *responseExpected = FALSE;
        }
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmProgram(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    *responseExpected = TRUE;

    /* Same session gate Xcp_DTOCmdPgmProgramClear's own handler carries above, and for the
     * identical reason: 1.1/1.6.5.1.1 refuses PROGRAM until PROGRAM_START has succeeded, and
     * 1.7.3.2.5 lists ERR_SEQUENCE on THIS command's own row for exactly that condition. */
    if (Xcp_Internal.pgm_state != XCP_PGM_ACTIVE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    /* SP4c Task 3, DD90: a data transfer request arriving while this build expects modified data
     * (a REQUIRED capability configured) but no PROGRAM_FORMAT has told this module how to decode
     * it is refused the same code as the session gate just above, for the same 1.7.3.2.5 row. */
    else if (Xcp_PgmDataTransferRefusedByFormat() == TRUE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];

        /* DD64, corrected by final-review finding 3. 1.1/1.6.5.1.3: "The end of the memory
         * segment is indicated, when the number of data elements is 0." Distinct from programming
         * zero bytes.
         *
         * DD64 originally said this "flushes" a block still open, written when Task 3 could never
         * open one (that is Task 4's PROGRAM_NEXT, added afterward without revisiting this
         * branch) -- so the word was never implemented and, on inspection, was also the wrong
         * word: §1.6.5.1.3 has the slave acknowledge only the LAST PROGRAM_NEXT, so a partial
         * block has no data the master ever agreed was final, and writing it to flash regardless
         * would be worse than leaving it alone. Aborting it, not flushing it, is what actually
         * matches "ends the segment": Xcp_PgmBlockAbort() (shared with PROGRAM_NEXT's own
         * wrong-count and short-frame paths, and now with Xcp_CTOCmdStdConnect/
         * Xcp_PgmCompleteProgramReset, final-review F2) is a harmless no-op when no block is open,
         * so it is called unconditionally rather than behind its own Xcp_PgmBlockIsActive() check.
         * Measured before this fix: with 4 elements of an open block still outstanding, `D0 00`
         * answered FF while leaving the block open, so a following PROGRAM_MAX was refused
         * ERR_SEQUENCE (DD65) and a following PROGRAM_NEXT could still resume the very segment
         * this response had just claimed was ended.
         *
         * Still does NOT end the programming sequence -- 1.6.5.1.3 gives that to PROGRAM_RESET,
         * which SP4a implements. */
        if (number_of_data_elements == 0x00u)
        {
            Xcp_PgmBlockAbort();

            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

            Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
        }
        else
        {
            const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
            const uint8 alignment = (uint8)Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
            const uint8 frame_elements = Xcp_BlockTransferFrameElements(number_of_data_elements, element_size);
            const uint16 frame_length = (uint16)(frame_elements * element_size);
            const uint16 total_length = (uint16)(number_of_data_elements * element_size);

            /* Task 3 was "PROGRAM without block mode" (design doc title): a declared count this
             * module cannot receive within the one frame it arrived on was refused up front,
             * unconditionally. Task 4/DD63 makes that refusal conditional on master block mode
             * actually being unsupported -- when it IS supported (Xcp_Ptr->general->
             * masterBlockModeSupported, the same flag Xcp_DTOCmdCalDownload's own
             * Xcp_DataTransferInitialize call reads for DOWNLOAD, and the one
             * Xcp_PgmCompleteProgramStart above reports as COMM_MODE_PGM's own MASTER_BLOCK_MODE
             * bit), an oversized count instead OPENS a block below and waits for PROGRAM_NEXT to
             * continue it, mirroring Xcp_DTOCmdCalDownload's own identical choice when ITS OWN
             * masterBlockModeSupported IS TRUE.
             * test_program_declaring_more_elements_than_fit_a_single_frame_is_refused_err_out_of_range_without_master_block_mode
             * (test/pgm_program_test.py) is Task 3's own original test, now pinning this exact
             * condition explicitly (master_block_mode=False) rather than by construction. Checked
             * before anything past the header is read, so an oversized count never reaches the
             * checks below on a false pretense. */
            if ((frame_elements != number_of_data_elements) &&
                (Xcp_Ptr->general->masterBlockModeSupported == FALSE))
            {
                Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
            }
            /* The buffer this write stages through is sized (source/Xcp_Internal.h) as the LARGER
             * of XCP_PGM_MAX_BLOCK_SIZE*(XCP_MAX_CTO-2) and XCP_MAX_CTO-1 -- DD63's own bound on a
             * whole BLOCK's declared length, checked here against the FULL count this frame
             * declares (total_length), not merely against what THIS frame alone carries
             * (frame_length, checked below): a block that will never fit is refused on the
             * opening PROGRAM itself, before a single byte of it is copied anywhere, exactly as
             * DD63 requires. Still unreachable for every schema-legal programming.max_block_size
             * when block mode is OFF (fix round 1, finding 1's own single-frame case, preserved),
             * and kept anyway for the reason that finding gives: a handler must never trust a
             * generated bound merely because the formula that produced it is believed correct.
             * Answers the one code 1.7.3.2.5's own PROGRAM row shares with DD63's own multi-frame
             * overflow -- the same fact, that this module cannot hold what was declared, reached
             * here by configuration rather than by accumulation across PROGRAM_NEXT frames.
             *
             * This is also the ONLY bound Xcp_DTOCmdPgmProgramNext's own append relies on: each
             * PROGRAM_NEXT frame is checked against the count it must match exactly
             * (pgm_block.requested_elements) but never against sizeof(pgm_block.data) directly, so
             * the argument that the running total can never overrun the buffer rests entirely on
             * this check having already bounded the FULL declared count before the first
             * PROGRAM_NEXT is ever received (review, fix round 1, "verified sound"). The one path
             * that could otherwise defeat it -- a CAL DOWNLOAD block opened first, so that
             * Xcp_Internal.block_transfer.requested_elements (a completely separate counter,
             * Xcp_BlockTransferFrameElements's own budget for THAT block, fix round 1 finding 1)
             * somehow fed a PROGRAM_NEXT frame larger than this PROGRAM's own declared total -- is
             * closed one level up: PROGRAM_START itself is refused ERR_CMD_BUSY/ERR_SEQUENCE by
             * DD55's guard while any interloping DOWNLOAD/DOWNLOAD_NEXT sequence has the CTO
             * response pipeline occupied, and a PGM session cannot open at all until PROGRAM_START
             * succeeds -- so a CAL block and a PGM block can never both be open at once, and
             * Xcp_DTOCmdPgmProgramNext's own frame_elements computation never draws on anything
             * but this command's own, already-bounded count.
             *
             * Finding 5 (low): at programming.max_block_size=1 this buffer is MAX_CTO-1 (7 at this
             * suite's default), one byte more than a single frame's own MAX_CTO-2 (6) ceiling --
             * PROGRAM_START's own MAX_BS_PGM=1 (DD62) advertises a ONE-frame block, but a 7-element
             * count fits this buffer and is accepted as a genuine two-frame block (6 then 1) despite
             * exceeding what was advertised. Leniency, not harm: the buffer is sized for
             * PROGRAM_MAX's own fixed MAX_CTO-1 transfer (source/Xcp_Internal.h), which has nothing
             * to do with MAX_BS_PGM, and a master that only ever sends what MAX_BS_PGM advertised
             * never notices the difference -- but the two numbers this module publishes
             * (MAX_BS_PGM) and enforces (this buffer) are genuinely not the same number at that one
             * configuration. */
            else if (total_length > (uint16)sizeof(Xcp_Internal.pgm_block.data))
            {
                Xcp_FillErrorPacket(XCP_E_ASAM_MEMORY_OVERFLOW, &Xcp_Internal.cto_response.pdu_info);
            }
            else if (pPduInfo->SduLength < (PduLengthType)(0x02u + alignment + frame_length))
            {
                /* The frame is shorter than the payload it actually carries -- mirrors
                 * Xcp_DTOCmdCalDownload's own identical guard (source/Xcp_Cal.c), checked against
                 * frame_length (THIS frame's own share of a possibly larger block), not
                 * total_length: a multi-frame block's opening PROGRAM never carries the whole
                 * declared count in one packet by design, so checking against total_length here
                 * would refuse every legitimate block-opening frame. Without this the handler
                 * copies whatever follows the received PDU into pgm_block, and from there into
                 * flash. */
                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
            }
            else
            {
                uint8_least idx;

                /* SP4c Task 6, DD86: this frame is an accepted data transfer request, so it counts
                 * -- whether it completes a block by itself or opens a multi-frame one. Counted
                 * here, past every refusal above (the session and format gates, the oversized
                 * count, the buffer bound and the short frame), so nothing this module answered
                 * with an error ever advances a counter the master is keeping in step with. The
                 * zero-element PROGRAM branch above does NOT reach this point and does not count
                 * either: 1.6.5.1.3 gives it no data to transfer, DD64 makes it the end of a
                 * segment rather than a transfer, and it never calls a write callback at all. */
                Xcp_PgmAdvanceBlockSequenceCounter();

                /* DD63/design Section 5: copied into pgm_block from index 0 by direct assignment,
                 * not accumulated onto whatever the buffer already held -- this IS the opening
                 * frame of a (possibly new) block, so it always starts one, the same way it did in
                 * Task 3 when this one frame was the whole block by itself. Xcp_DTOCmdPgmProgramNext
                 * below is the only handler that ever appends past this point. */
                for (idx = 0x00u; idx < frame_length; idx++)
                {
                    Xcp_Internal.pgm_block.data[idx] = pPduInfo->SduDataPtr[0x02u + alignment + idx];
                }

                Xcp_Internal.pgm_block.length = frame_length;

                /* Task 4 fix round 1, finding 1 (critical): Xcp_Internal.pgm_block's OWN counters,
                 * NOT Xcp_Internal.block_transfer -- the first version of this task shared the
                 * latter with DOWNLOAD/DOWNLOAD_NEXT's own Xcp_DataTransferInitialize +
                 * Xcp_BlockTransferAcknowledgeFrame pair, on DD63's own advice, and that shared
                 * state is also read by Xcp_CanIfTxConfirmation (source/Xcp.c) to decide whether an
                 * UPLOAD is still owed to the master. A PGM block staying open across an unrelated
                 * command's own confirmed response -- a refused PROGRAM_MAX, legal mid-sequence per
                 * 1.1/1.6.5.1.1 -- made that confirmation path read slave memory and transmit it
                 * unsolicited (source/Xcp_Internal.h, pgm_block's own comment). SET_MTA was a second
                 * such exchange until final review F1 made it abort the block instead
                 * (Xcp_PgmFormatReset below); see Xcp_PgmBlockIsActive's own forward declaration for
                 * why that changes nothing about this choice of state.
                 * Xcp_PgmBlockAcknowledgeFrame (below) is Xcp_BlockTransferAcknowledgeFrame's own
                 * shape, against this separate pair instead. Set to the FULL declared count here,
                 * then immediately brought down by this frame's own contribution. A count that fits
                 * entirely within this one frame drives requested_elements back to 0 in the same
                 * handler call that set it, so Xcp_PgmBlockIsActive() is never observably TRUE for a
                 * single-frame PROGRAM -- Task 3's own single-frame behaviour is therefore unaffected
                 * by this task, and PROGRAM_MAX's own DD65 guard below only ever sees TRUE once a
                 * PROGRAM_NEXT is genuinely awaited. */
                Xcp_Internal.pgm_block.requested_elements = number_of_data_elements;
                Xcp_Internal.pgm_block.frame_elements = frame_elements;
                Xcp_PgmBlockAcknowledgeFrame();

                if (Xcp_Internal.pgm_block.requested_elements == 0x00u)
                {
                    uint8 status_code = 0x00u;

                    /* The block is complete -- whether because it fit entirely in this one frame
                     * (Task 3's own original shape) or because number_of_data_elements was small
                     * enough that this single opening frame already satisfies it under block mode
                     * too. Either way this is the ONLY call to Xcp_ProgramWrite for this block, the
                     * FIRST one happening here rather than on the next Xcp_MainFunction, for the
                     * same reason PROGRAM_CLEAR's own first call does above: an integrator whose
                     * work is instantaneous returns E_OK from it and the master is answered on this
                     * very exchange. Spec Section 4.
                     *
                     * SP4c Task 6: through Xcp_PgmCallProgramWrite (below), not Xcp_ProgramWrite
                     * directly -- this stream's own access method decides which of the two write
                     * callbacks receives the block (DD84), and routing every call site through one
                     * helper is what keeps a later poll from reaching the other one. */
                    if (Xcp_PgmCallProgramWrite(&status_code) == E_OK)
                    {
                        Xcp_PgmCompleteProgramWrite(status_code);
                    }
                    else
                    {
                        Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM;
                        Xcp_Internal.pending_command.active = TRUE;
                        Xcp_Internal.pending_command.abandoned = FALSE;
                        Xcp_Internal.pending_command.event_outstanding = FALSE;
                        /* Neither pData nor length needs a slot in pending_command.args the way
                         * PROGRAM_PREPARE's codeSize and PROGRAM_CLEAR's clear range do:
                         * Xcp_Internal.pgm_block IS that standing state here, re-read directly by
                         * Xcp_PgmPollPendingCommand on every poll -- stable for the duration, since
                         * DD55's ERR_CMD_BUSY gate refuses any interloping command that could touch
                         * it, the same reason the MTA needs no slot of its own either. */

                        /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
                        *responseExpected = FALSE;
                    }
                }
                else
                {
                    /* DD63: the block is open but not yet complete -- more PROGRAM_NEXT frames are
                     * expected. "Intermediate frames answer nothing and complete entirely in
                     * receive context ... no callback, no polling, no pending slot." This opening
                     * PROGRAM frame is exactly such an intermediate frame whenever it does not
                     * complete the block by itself. */
                    *responseExpected = FALSE;
                }
            }
        }
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmProgramMax(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    *responseExpected = TRUE;

    /* Same session gate as Xcp_DTOCmdPgmProgram above. */
    if (Xcp_Internal.pgm_state != XCP_PGM_ACTIVE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    /* SP4c Task 3, DD90: same gate Xcp_DTOCmdPgmProgram's own handler carries above, and for the
     * identical reason -- PROGRAM_MAX is the second of the three commands DD90 names by name. */
    else if (Xcp_PgmDataTransferRefusedByFormat() == TRUE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    /* DD65 (H1). 1.6.5.2.6: "This command does not support block transfer and it may not be used
     * within a block transfer sequence." Its own 1.7.3.2.5 row lists ERR_SEQUENCE for it. Task 3
     * left this branch untested: nothing yet opened a block, so it could never be TRUE here on the
     * way in. Task 4's own Xcp_DTOCmdPgmProgram and Xcp_DTOCmdPgmProgramNext (below) are what
     * finally drive it.
     *
     * Reads Xcp_PgmBlockIsActive(), PGM's OWN block-open flag, not Xcp_BlockTransferIsActive() --
     * Task 4 fix round 1, finding 1 (critical). The first version of this task's own guard DID read
     * Xcp_BlockTransferIsActive(), on the reasoning that DD63 says to reuse Xcp_Internal.
     * block_transfer and that this guard already read the right shared state. Both were true, and
     * both missed that Xcp_CanIfTxConfirmation (source/Xcp.c) also reads that same state,
     * unconditionally, to decide whether an UPLOAD is still owed to the master -- so a PGM block
     * staying open past this guard's own check, across an unrelated command's confirmed response,
     * made the slave read slave memory and transmit it unsolicited (source/Xcp_Internal.h,
     * pgm_block's own comment; task-4-report.md, "Fix round 1", finding 1). Xcp_PgmBlockIsActive()
     * reads Xcp_Internal.pgm_block.requested_elements instead, which nothing outside this file
     * reads for any other purpose.
     * test_program_max_inside_an_open_block_is_refused_err_sequence (test/pgm_program_test.py) is
     * this guard's first real test, and mutation-verified both ways: deleting this branch falls
     * through to the length/copy logic below and answers 0xFF instead of ERR_SEQUENCE, and the
     * confirmation-path regression above is pinned separately by
     * test_confirming_a_response_while_a_program_block_is_open_does_not_leak_slave_memory. */
    else if (Xcp_PgmBlockIsActive() == TRUE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (pPduInfo->SduLength < (PduLengthType)Xcp_Ptr->general->maxCto)
    {
        /* A second recorded deviation, in DD57's own form, task 3 review fix round 1 finding 2:
         * PROGRAM_MAX's own 1.7.3.2.5 row is exactly ERR_CMD_BUSY, ERR_CMD_UNKNOWN, ERR_SEQUENCE
         * and ERR_MEMORY_OVERFLOW -- no ERR_CMD_SYNTAX, unlike DOWNLOAD_MAX's own row for the
         * identical request shape, which lists it. None of the four listed codes fits a frame that
         * arrived physically shorter than this fixed-size command needs: ERR_CMD_BUSY and
         * ERR_CMD_UNKNOWN are dispatch-level conditions this point has already passed, ERR_SEQUENCE
         * is this handler's own session and block-active gates above (a statement about ordering,
         * not about this frame's own length), and ERR_MEMORY_OVERFLOW is the buffer-overflow guard
         * below (a statement about the configured buffer, not about what was actually received) --
         * so no listed code describes this condition without also misdescribing a different one
         * this same handler already answers correctly. ERR_CMD_SYNTAX is kept as the deviation:
         * Xcp_DTOCmdCalDownloadMax's own choice for the identical condition (source/Xcp_Cal.c), and
         * exactly what the generic pre-dispatch length gate (Xcp_CanIfRxIndication, source/Xcp.c)
         * would itself answer had PROGRAM_MAX's row carried the bit that lets that gate consult
         * this command's ctoInfo minimum at all -- which it does not, so this handler's own check
         * is the ONLY protection against reading past the received PDU below, not merely a
         * stylistic mirror of DOWNLOAD_MAX's identical-looking one. */
        Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
        /* 1.1/1.6.5.2.6, and 1.0's identical wording, both read literally "MAX_CTO(_PGM)-1
         * elements" / "post-incremented by MAX_CTO(_PGM)-1" -- confirmed by hand against both
         * PDFs via pdftotext -layout, unlike DOWNLOAD_MAX's own explicitly AG-divided
         * MAX_CTO/AG-1 (Xcp_DTOCmdCalDownloadMax, source/Xcp_Cal.c). That literal reading is safe,
         * and exactly what this computes, when AG is BYTE (element_size 1, this suite's default
         * and the only granularity any test here exercises): MAX_CTO-1 elements of one byte each
         * is MAX_CTO-1 bytes, which is what a MAX_CTO-1-elements-undivided reading and a
         * divided-by-AG reading both give when AG is 1. It stops being safe for AG WORD or DWORD:
         * both PDFs give this same command an "AG..MAX_CTO-AG" data position range immediately
         * above the sentence quoted, which bounds the data to MAX_CTO-AG bytes and is
         * self-consistent with "MAX_CTO-1 elements" only when AG is 1 -- for AG 2 or 4, MAX_CTO-1
         * elements taken literally would need (MAX_CTO-1)*AG data bytes, larger than MAX_CTO
         * itself and therefore larger than the one CTO frame this command is ever carried in.
         * Divided by AG, as below, this collapses to exactly MAX_CTO-1 at AG=1 -- so nothing
         * changes for the configuration this task's own tests build against -- and stays inside
         * the frame at every other AG, mirroring DOWNLOAD_MAX's own formula for the identical
         * layout instead of re-deriving a new one. Flagged in the task report as a deliberate
         * reading of an ambiguous pair of sentences, resolved in the only direction that does not
         * read past the received PDU below. Runtime Xcp_Ptr->general->maxCto throughout, never
         * the compile-time XCP_MAX_CTO macro -- every existing handler reads the runtime field
         * (source/Xcp_Cal.c, source/Xcp_Pgm.c above), and on a multi-configuration build the macro
         * is the largest max_cto across every configuration while this field is the one actually
         * in force. */
        const uint8 number_of_data_elements = (uint8)((Xcp_Ptr->general->maxCto / element_size) - 0x01u);
        const uint16 length = (uint16)(number_of_data_elements * element_size);

        if (length > (uint16)sizeof(Xcp_Internal.pgm_block.data))
        {
            /* Same buffer safety net as Xcp_DTOCmdPgmProgram above, and the demand this command's
             * own fixed transfer places is what the buffer's XCP_MAX_CTO-1 floor
             * (source/Xcp_Internal.h) exists for: at AG BYTE it needs MAX_CTO-1 bytes, one more
             * than a single PROGRAM frame's own (MAX_CTO-2)-byte ceiling, because PROGRAM_MAX
             * carries no element-count byte of its own reserving that position -- so before fix
             * round 1 finding 1, XCP_PGM_MAX_BLOCK_SIZE=1 (then schema-legal) already overflowed
             * the buffer here where it did not for PROGRAM, refusing every PROGRAM_MAX at that
             * block size regardless of what the master sent. Sized correctly, this condition is
             * unreachable for every schema-legal programming.max_block_size and is kept anyway,
             * for the reason Xcp_DTOCmdPgmProgram's own identical comment gives. ERR_MEMORY_OVERFLOW
             * is PROGRAM_MAX's own row's answer for exactly this shape of failure (1.7.3.2.5). */
            Xcp_FillErrorPacket(XCP_E_ASAM_MEMORY_OVERFLOW, &Xcp_Internal.cto_response.pdu_info);
        }
        else
        {
            uint8_least idx;
            uint8 status_code = 0x00u;

            /* SP4c Task 6, DD86: PROGRAM_MAX is the second of the three commands DD86 counts, and
             * this is the point past every refusal above at which its own fixed-size transfer is
             * accepted -- the same placement Xcp_DTOCmdPgmProgram's own call carries, and for the
             * same reason. */
            Xcp_PgmAdvanceBlockSequenceCounter();

            /* Data starts at position AG (== element_size): 1.6.5.2.6's own layout is "1..AG-1
             * alignment, only if AG>1" then "AG..MAX_CTO-AG data" -- Xcp_DTOCmdCalDownloadMax's
             * identical arithmetic for the identical layout (source/Xcp_Cal.c). Copied into
             * pgm_block for the same reason Xcp_DTOCmdPgmProgram above is: one write path shared
             * by both commands, through the identical Xcp_ProgramWrite contract. */
            for (idx = 0x00u; idx < length; idx++)
            {
                Xcp_Internal.pgm_block.data[idx] = pPduInfo->SduDataPtr[element_size + idx];
            }

            Xcp_Internal.pgm_block.length = length;

            /* SP4c Task 6: through Xcp_PgmCallProgramWrite, for the reason Xcp_DTOCmdPgmProgram's
             * own identical call above gives. */
            if (Xcp_PgmCallProgramWrite(&status_code) == E_OK)
            {
                Xcp_PgmCompleteProgramWrite(status_code);
            }
            else
            {
                Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM_MAX;
                Xcp_Internal.pending_command.active = TRUE;
                Xcp_Internal.pending_command.abandoned = FALSE;
                Xcp_Internal.pending_command.event_outstanding = FALSE;

                /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
                *responseExpected = FALSE;
            }
        }
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmProgramNext(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    *responseExpected = TRUE;

    /* Same session gate Xcp_DTOCmdPgmProgram's own handler carries above, and for the identical
     * reason: 1.1/1.6.5.1.1 lists PROGRAM_NEXT as the fourth of the four commands refused until
     * PROGRAM_START has succeeded. Checked BEFORE Xcp_PgmBlockIsActive() below, not merely beside
     * it: pgm_state is what this module owns to tell an open PGM session from a closed one, and a
     * PROGRAM_NEXT arriving with no PGM session open must not be answered by whatever the PGM block
     * state happens to hold left over. */
    if (Xcp_Internal.pgm_state != XCP_PGM_ACTIVE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    /* SP4c Task 3, DD90: same gate Xcp_DTOCmdPgmProgram's own handler carries above, and for the
     * identical reason -- PROGRAM_NEXT is the third of the three commands DD90 names by name.
     * Checked here, before Xcp_PgmBlockIsActive() below, mirroring the pgm_state check immediately
     * above it: both are about whether this sequence is in a state that permits a data transfer at
     * all, which this handler settles before it ever asks whether a block happens to be open. */
    else if (Xcp_PgmDataTransferRefusedByFormat() == TRUE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    /* DD63. 1.1/1.6.5.2.5: "It contains the remaining number of data elements to transmit. The
     * slave device will use this information to detect lost packets. If a sequence error has been
     * detected, the error code ERR_SEQUENCE will be returned." Mirrors Xcp_DTOCmdCalDownloadNext's
     * own identical shape (source/Xcp_Cal.c), which is the worked precedent this handler follows
     * throughout -- with two structural differences explained at the point of use below:
     * Xcp_BlockTransferWriteSlaveMemory is not reusable here, because it writes RAM through
     * Xcp_WriteSlaveMemoryTable synchronously, and flash is neither (design Section 2); and the
     * block-open state itself is Xcp_Internal.pgm_block's own pair, not Xcp_Internal.block_transfer
     * (Task 4 fix round 1, finding 1 -- see Xcp_PgmBlockIsActive's own comment above for why the two
     * must not be shared). */
    else if (Xcp_PgmBlockIsActive() == TRUE)
    {
        const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
        const uint8 alignment = (uint8)Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
        const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];
        const uint8 expected = Xcp_Internal.pgm_block.requested_elements;

        if (number_of_data_elements != expected)
        {
            /* PROGRAM_NEXT's negative response is distinctive: ERR_SEQUENCE carrying the number
             * of elements the slave expected, in byte 2 -- Xcp_FillErrorPacketWithData is exactly
             * this shape, and Xcp_DTOCmdCalDownloadNext already uses it for the identical
             * condition. */
            Xcp_FillErrorPacketWithData(XCP_E_ASAM_SEQUENCE,
                                        &expected,
                                        0x01u,
                                        &Xcp_Internal.cto_response.pdu_info);

            /* DD63: a block that goes wrong is discarded, not resumed -- 1.7.3.2.5 gives
             * PROGRAM_NEXT the pre-action SYNCH+PROGRAM, so the master restarts from its own
             * PROGRAM rather than retrying the failed PROGRAM_NEXT, and this module keeps no
             * partial-block state to reconcile. Mirrors Xcp_DTOCmdCalDownloadNext's own identical
             * call for the identical reason -- Xcp_PgmBlockAbort() is Xcp_BlockTransferAbort()'s own
             * shape, against Xcp_Internal.pgm_block instead (Task 4 fix round 1, finding 1). */
            Xcp_PgmBlockAbort();
        }
        else
        {
            const uint8 frame_elements = Xcp_BlockTransferFrameElements(number_of_data_elements, element_size);
            const uint16 frame_length = (uint16)(frame_elements * element_size);

            if (pPduInfo->SduLength < (PduLengthType)(0x02u + alignment + frame_length))
            {
                /* The frame is shorter than the payload it actually carries -- mirrors
                 * Xcp_DTOCmdCalDownloadNext's own identical guard (source/Xcp_Cal.c). Without this
                 * the handler copies whatever follows the received PDU into pgm_block, and from
                 * there into flash. Aborted for the identical reason the wrong-count branch above
                 * is: this frame is unusable, and the block it would have continued is discarded,
                 * not left open for whatever the master sends next. */
                Xcp_PgmBlockAbort();

                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
            }
            else
            {
                /* DD63: "Each PROGRAM_NEXT appends." Unlike Xcp_DTOCmdPgmProgram's own opening
                 * frame above, which always starts a block from index 0, this copy begins at
                 * Xcp_Internal.pgm_block.length -- wherever the block's accumulated bytes so far
                 * end -- and grows it by this frame's own contribution. Bounded safely without a
                 * separate overflow check here: the opening PROGRAM already refused any block
                 * whose FULL declared length would not fit the buffer, and the sum of every
                 * frame's own frame_length can never exceed that same declared length -- see the
                 * note beside Xcp_DTOCmdPgmProgram's own equivalent bound for the one path that
                 * could otherwise have violated it. */
                const uint16 offset = Xcp_Internal.pgm_block.length;
                uint8_least idx;

                /* SP4c Task 6, DD86: PROGRAM_NEXT is the third of the three commands DD86 counts,
                 * so EVERY frame of a master block mode block advances the counter -- not only the
                 * one that completes it and calls the integrator. DD86's own table says "each data
                 * transfer request", and 1.6.5.1.3's rollover sentence is phrased against a request
                 * message arriving ("rolls over and starts at 0x00 with the next data transfer
                 * request message"), not against a write completing. The alternative reading is
                 * recorded rather than dismissed: the same paragraph also says the MTA IS this
                 * counter, and the MTA advances once per completed BLOCK here (DD66,
                 * Xcp_PgmCompleteProgramWrite below), so a per-block counter would have been
                 * defensible too. test/pgm_functional_test.py's own
                 * test_every_frame_of_a_master_block_counts_as_its_own_data_transfer_request pins
                 * the reading actually taken, so it cannot drift silently. */
                Xcp_PgmAdvanceBlockSequenceCounter();

                for (idx = 0x00u; idx < frame_length; idx++)
                {
                    Xcp_Internal.pgm_block.data[offset + idx] = pPduInfo->SduDataPtr[0x02u + alignment + idx];
                }

                Xcp_Internal.pgm_block.length = (uint16)(offset + frame_length);

                /* Xcp_PgmBlockAcknowledgeFrame() is Xcp_BlockTransferAcknowledgeFrame()'s own
                 * shape, against Xcp_Internal.pgm_block instead of block_transfer (Task 4 fix
                 * round 1, finding 1). */
                Xcp_Internal.pgm_block.frame_elements = frame_elements;
                Xcp_PgmBlockAcknowledgeFrame();

                if (Xcp_Internal.pgm_block.requested_elements == 0x00u)
                {
                    uint8 status_code = 0x00u;

                    /* This is the frame that completes the block (1.1/1.6.5.1.3: "The slave
                     * device will acknowledge only the last PROGRAM_NEXT command packet"), and the
                     * ONLY call to Xcp_ProgramWrite for the whole block -- exactly as
                     * Xcp_DTOCmdPgmProgram's own single-frame completion above calls it, from the
                     * identical Xcp_Internal.pgm_block standing state, now carrying every frame's
                     * accumulated contribution rather than only the first one's. The FIRST call
                     * happens here, not on the next Xcp_MainFunction, for the same reason it does
                     * there: an integrator whose work is instantaneous returns E_OK from it and
                     * the master is answered on this very exchange. Spec Section 4. Through
                     * Xcp_PgmCallProgramWrite since SP4c Task 6, for the reason
                     * Xcp_DTOCmdPgmProgram's own identical call above gives. */
                    if (Xcp_PgmCallProgramWrite(&status_code) == E_OK)
                    {
                        Xcp_PgmCompleteProgramWrite(status_code);
                    }
                    else
                    {
                        Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM_NEXT;
                        Xcp_Internal.pending_command.active = TRUE;
                        Xcp_Internal.pending_command.abandoned = FALSE;
                        Xcp_Internal.pending_command.event_outstanding = FALSE;
                        /* Neither pData nor length needs a slot in pending_command.args, for the
                         * identical reason Xcp_DTOCmdPgmProgram's own identical comment gives
                         * above: Xcp_Internal.pgm_block IS that standing state here. */

                        /* Withheld; Xcp_MainFunction answers, however long the integrator takes.
                         * DD53. */
                        *responseExpected = FALSE;
                    }
                }
                else
                {
                    /* DD63: "Intermediate frames answer nothing and complete entirely in receive
                     * context ... They set *responseExpected = FALSE, copy their bytes, and return
                     * -- no callback, no polling, no pending slot." This is the property that
                     * makes master block mode work at all: were a callback triggered on every
                     * frame instead, a master pacing frames by MIN_ST_PGM would deliver the next
                     * one while a write was still pending, and SP4a's ERR_CMD_BUSY guard would
                     * refuse it -- breaking a block-transfer sequence with an error that exists to
                     * protect a response buffer. */
                    *responseExpected = FALSE;
                }
            }
        }
    }
    else
    {
        /* No block is open -- either none was ever requested, or DD63's own discard above (or
         * Xcp_Init) closed the one that was. 1.7.3.2.5's own PROGRAM_NEXT row lists ERR_SEQUENCE
         * for this, the same code the session gate above answers, and this command's negative
         * response always carries the expected element count (1.1/1.6.5.2.5) -- 0 here, since
         * none was ever requested. Mirrors Xcp_DTOCmdCalDownloadNext's own identical `else` for
         * the identical condition (source/Xcp_Cal.c), down to reporting the same expected value
         * of 0 through the same Xcp_FillErrorPacketWithData call. */
        const uint8 expected = 0x00u;

        Xcp_FillErrorPacketWithData(XCP_E_ASAM_SEQUENCE,
                                    &expected,
                                    0x01u,
                                    &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmGetPgmProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    /* 1.0/1.6.5.2.1: "This command returns general information on programming." No request
     * parameters beyond the command code, no gate on Xcp_Internal.pgm_state, and no integrator
     * call -- this function's own @details in Xcp_Internal.h explains why, and unlike every other
     * handler above in this file, this is the only path it ever takes: Xcp_CTOErrorMatrix[0xCE]
     * (source/Xcp.c) carries neither XCP_INTERNAL_ERR_SEQUENCE nor XCP_INTERNAL_ERR_PGM_ACTIVE, and
     * §1.6.5.1.1's "not allowed until PROGRAM_START" list names PROGRAM_CLEAR, PROGRAM, PROGRAM_MAX
     * and PROGRAM_NEXT, not this command. DD68.
     *
     * PGM_PROPERTIES: SP4c Task 3 replaces the hardcoded XCP_PGM_PROPERTIES_ABSOLUTE_MODE literal
     * with this build's own generated byte, Xcp_Ptr->general->pgmProperties
     * (script/source_cfg.c.jinja2). ABSOLUTE_MODE (bit 0) is still unconditional -- this module
     * offers absolute access in every build -- and bits 2..7, the COMPRESSION_SUPPORTED/_REQUIRED,
     * ENCRYPTION_SUPPORTED/_REQUIRED and NON_SEQ_PGM_SUPPORTED/_REQUIRED pairs (Xcp_Internal.h),
     * now follow this build's own programming.compression_..., .encryption_... and
     * .non_sequential_... flags:
     * PROGRAM_FORMAT (Xcp_DTOCmdPgmProgramFormat, below) reads this SAME field to decide what it
     * accepts (design doc DD89), so the two commands cannot advertise and enforce different
     * things. Bit 1, FUNCTIONAL_MODE, is SP4c Task 6's own addition to that same generated
     * expression (DD92) and the only one this handler needed no change for: it is set exactly when
     * this build configures BOTH functional callbacks -- Xcp_ProgramClearFunctional and
     * Xcp_ProgramWriteFunctional (interface/Xcp.h) -- which generation refuses to let a
     * configuration offer one at a time, so what this byte advertises and what
     * Xcp_DTOCmdPgmProgramFormat accepts are the same fact rather than two that must be kept in
     * step. (MAX_SECTOR, the byte immediately below, is untouched by this change -- SP4c Task 2
     * made it config-driven; see its own comment there.) */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_Ptr->general->pgmProperties;

    /* MAX_SECTOR: the configured sector count (interface/Xcp_Types.h's Xcp_SectorType array,
     * config/xcp.schema.json's programming.sectors, script/source_cfg.c.jinja2). SP4b's DD68
     * hardcoded this at 0, with no sector configuration to derive it from yet, and predicted here
     * that GET_SECTOR_INFO would answer ERR_OUT_OF_RANGE for a sector that is not available
     * (1.0/1.6.5.2.2's own prose). SP4c's DD88
     * (docs/superpowers/specs/2026-09-08-xcp-pgm-sp4c-design.md) corrects that prediction before it
     * ever shipped: 1.7.3.2.5's own row for GET_SECTOR_INFO lists ERR_MODE_NOT_VALID and
     * ERR_SEGMENT_NOT_VALID, not ERR_OUT_OF_RANGE, and Xcp_DTOCmdPgmGetSectorInfo (below) answers
     * accordingly. This is still a slave with no sector description whenever maxSector reads back
     * 0, exactly as DD68 intended -- only the byte's SOURCE changed, from a literal to this count.
     * (PGM_PROPERTIES, the byte immediately above, is untouched by this change -- later SP4c tasks
     * make it config-driven and set a bit within it; see their own comments there.) */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = Xcp_Ptr->general->maxSector;

    Xcp_FinalizeResPacket(0x03u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

uint8 Xcp_DTOCmdPgmProgramVerify(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint16 verification_type;

    *responseExpected = TRUE;

    /* verificationType (the WORD at bytes 2-3) has to be parsed before anything else in this
     * handler runs: the one structural check 1.1/1.6.5.2.7 permits a slave to make (design doc
     * DD91) is over this field's own reserved bits, and reading it out of order would either check
     * stale bytes or, worse, read verificationValue's own bytes by mistake. No gate on
     * Xcp_Internal.pgm_state, unlike PROGRAM_CLEAR/PROGRAM/PROGRAM_MAX/PROGRAM_NEXT above:
     * 1.1/1.6.5.1.1's "not allowed until PROGRAM_START" list does not name PROGRAM_VERIFY, and
     * design doc Section 1 records this command as consuming nothing from the rest of the module --
     * no address, no session state -- unlike every other PGM command in this file. */
    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &verification_type, Xcp_Ptr->general->byteOrder);

    /* Design doc DD91: "1.6.5.2.7 marks verification types 0x0008...0x0080 reserved, so a master
     * setting those bits is refused ERR_OUT_OF_RANGE (in the row)." Checked as a bit mask
     * (0x00F8u covers exactly 0x0008, 0x0010, 0x0020, 0x0040 and 0x0080 together), not as five
     * separate equality checks: 1.6.5.2.7 reserves the whole 0x0008..0x0080 range, and a master is
     * free to combine a reserved bit with a defined one (e.g. 0x0001 | 0x0008) in the same request,
     * which a chain of `== ` comparisons against only the single-bit values would not catch. Bits
     * 0x0001/0x0002/0x0004 (calibration areas/code areas/complete flash) and 0x0100..0xFF00 (user
     * defined) both pass this check untouched: the former are this specification's own defined
     * values, and the latter are, by the same paragraph's own words, the integrator's to interpret,
     * not this module's to refuse. */
    if ((verification_type & 0x00F8u) != 0x0000u)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        uint8 status_code = 0x00u;
        const uint8 verification_mode = pPduInfo->SduDataPtr[0x01u];
        uint32 verification_value;

        Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &verification_value, Xcp_Ptr->general->byteOrder);

        /* The FIRST call happens here, not on the next Xcp_MainFunction, for the same reason
         * PROGRAM_CLEAR's own first call does above: an integrator whose work is instantaneous
         * returns E_OK from it and the master is answered on this very exchange. Spec Section 4. */
        if (Xcp_ProgramVerify(verification_mode, verification_type, verification_value, &status_code) == E_OK)
        {
            Xcp_PgmCompleteProgramVerify(status_code);
        }
        else
        {
            Xcp_Internal.pending_command.pid = XCP_PID_CMD_PROGRAM_VERIFY;
            Xcp_Internal.pending_command.active = TRUE;
            Xcp_Internal.pending_command.abandoned = FALSE;
            Xcp_Internal.pending_command.event_outstanding = FALSE;
            /* Xcp_ProgramVerify's contract takes mode, type and value on every call, not only this
             * first one, and Xcp_PgmPollPendingCommand (below) has no other way to recover any of
             * the three once this handler returns -- unlike every other PGM command in this file,
             * PROGRAM_VERIFY has no address of its own to fall back on either (source/Xcp_Internal.h,
             * pending_command.args' own program_verify member). */
            Xcp_Internal.pending_command.args.program_verify.mode = verification_mode;
            Xcp_Internal.pending_command.args.program_verify.type = verification_type;
            Xcp_Internal.pending_command.args.program_verify.value = verification_value;

            /* Withheld; Xcp_MainFunction answers, however long the integrator takes. DD53. */
            *responseExpected = FALSE;
        }
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmGetSectorInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 sector_number = pPduInfo->SduDataPtr[0x02u];

    *responseExpected = TRUE;

    /* 1.0/1.6.5.2.2: mode 0 = SECTOR_INFO is the SECTOR's start address, mode 1 = SECTOR_INFO is
     * its length. No other mode byte is defined, and unlike PROGRAM_CLEAR's own mode byte a few
     * functions above -- refused ERR_OUT_OF_RANGE, because its own 1.7.3.2.5 row has no
     * ERR_MODE_NOT_VALID to answer with (DD67) -- this command's own row DOES list
     * ERR_MODE_NOT_VALID, so that is what an undefined mode byte answers here, checked before
     * SECTOR_NUMBER (below) so a request that gets both wrong is answered for the reason a reader
     * checking the request top-to-bottom would expect. */
    if ((mode != 0x00u) && (mode != 0x01u))
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_MODE_NOT_VALID, &Xcp_Internal.cto_response.pdu_info);
    }
    /* DD88 (docs/superpowers/specs/2026-09-08-xcp-pgm-sp4c-design.md): the specification
     * contradicts itself on what an out-of-range SECTOR_NUMBER answers. 1.6.5.2.2's own prose says
     * ERR_OUT_OF_RANGE; 1.7.3.2.5's row for this same command lists ERR_MODE_NOT_VALID and
     * ERR_SEGMENT_NOT_VALID, and not ERR_OUT_OF_RANGE. DD65 (SP4b) already settled this class of
     * contradiction, on PROGRAM_MAX's own self-contradictory length: where a listed code fits, use
     * it and take no deviation. ERR_SEGMENT_NOT_VALID fits -- in a command whose only parameters
     * are a mode and a sector number, it can mean nothing else -- so that is what this branch
     * answers, not the prose's ERR_OUT_OF_RANGE. maxSector is this build's own configured sector
     * count (Xcp_Ptr->general->maxSector, script/source_cfg.c.jinja2), so SECTOR_NUMBER in
     * [0, maxSector) is exactly the valid range 1.6.5.2.2's own [0, MAX_SECTOR-1] describes. */
    else if (sector_number >= Xcp_Ptr->general->maxSector)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEGMENT_NOT_VALID, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        const Xcp_SectorType *p_sector = &Xcp_Ptr->config->sector[sector_number];
        const uint32 sector_info = (mode == 0x00u) ? p_sector->address : p_sector->length;

        /* Bytes 1-3: the two SEQUENCE_NUMBERs and PROGRAMMING_METHOD, reported verbatim regardless
         * of MODE (1.0/1.6.5.2.2's own response layout puts them ahead of SECTOR_INFO, unconditional
         * on the mode byte that only selects what SECTOR_INFO itself, bytes 4-7, means). Neither
         * derived nor enforced by this module -- Xcp_SectorType's own @note (interface/Xcp_Types.h)
         * records why. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = p_sector->clearSequenceNumber;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = p_sector->programSequenceNumber;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = p_sector->programmingMethod;

        /* SECTOR_INFO, bytes 4-7: the DWORD mode selects, in the configured byte order -- never
         * converted against addressGranularity here, in either direction: p_sector->length is
         * already in BYTES (Xcp_SectorType's own @note), and generation (script/source_cfg.c.jinja2)
         * is what refuses a configured length that is not a multiple of AG, per DD87. A handler
         * that instead divided by the element size for AG WORD/DWORD would report a DIFFERENT,
         * smaller value here -- test/pgm_sector_test.py's own mode-1 test is deliberately run at an
         * AG wider than BYTE so such a regression could not hide behind AG=BYTE's trivial equality
         * of the two readings. */
        Xcp_CopyFromU32WithOrder(sector_info,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                 Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdPgmProgramFormat(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 compression_method = pPduInfo->SduDataPtr[0x01u];
    const uint8 encryption_method = pPduInfo->SduDataPtr[0x02u];
    const uint8 programming_method = pPduInfo->SduDataPtr[0x03u];
    const uint8 access_method = pPduInfo->SduDataPtr[0x04u];

    *responseExpected = TRUE;

    /* Final review F1: a PROGRAM_FORMAT arriving while a master block mode PGM block is still open
     * is refused ERR_SEQUENCE, before any of DD89's own parameter checks below and before anything
     * is stored. Both revisions' 1.6.5.2.4 make this command's whole subject the format of
     * "following, UNINTERRUPTED data transfer", "set direct at begin of the programming sequence" --
     * so one arriving midway through a transfer it did not describe is out of sequence by the
     * command's own definition, and ERR_SEQUENCE is in its own 1.7.3.2.5 row in BOTH revisions
     * (1.0 p.144, 1.1 p.156), so no deviation is taken. Mirrors PROGRAM_MAX's own DD65 gate
     * (Xcp_DTOCmdPgmProgramMax above) exactly: the one other command that refuses ERR_SEQUENCE for
     * no reason but an open block, checked the same way, before its own payload is read.
     *
     * Measured before this gate existed (final review F1's own frame sequence): with a functional
     * block open, `CB 00 00 00 00` was answered 0xFF and reset access_method to 0, and the
     * completing PROGRAM_NEXT then handed the WHOLE accumulated block to Xcp_ProgramWrite at
     * whatever the MTA held -- an absolute flash write the master never asked for, reported
     * successful. The mirror case (absolute block open, `CB 00 00 00 01`) sent it to
     * Xcp_ProgramWriteFunctional instead. Refusing is preferred over silently latching the mode the
     * block opened under: a latch would answer 0xFF to a format change this module then declined to
     * apply, leaving the master to program the REST of its image under a format the slave never
     * adopted, and it would also leave DD86's counter re-based mid-block -- so the master's own
     * count and this slave's would diverge exactly where the counter exists to agree. */
    if (Xcp_PgmBlockIsActive() == TRUE)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    /* SP4c Task 3, design doc DD89: "a non-default value is accepted only if the corresponding
     * property is advertised, and refused ERR_OUT_OF_RANGE otherwise". One term per request field,
     * each checked against Xcp_Ptr->general->pgmProperties -- the SAME byte
     * Xcp_DTOCmdPgmGetPgmProcessorInfo reports, so acceptance here can never drift from what was
     * advertised (DD89's own "closes the gap by construction", not by discipline). The default
     * value (0x00u) of every field is accepted unconditionally, whatever this build advertises --
     * DD89 is a rule about NON-default values only, and 1.1/1.6.5.2.4 makes an all-defaults
     * request the same thing as PROGRAM_FORMAT never having been sent at all.
     *
     * Checked before Xcp_ProgramFormat is ever called, not folded into its own contract: the
     * module owns the structural fact of what this build advertises, and the integrator is asked
     * only to judge what it cannot -- a user-defined value's own specific meaning (DD91). */
    else if ((compression_method != 0x00u) &&
             ((Xcp_Ptr->general->pgmProperties & XCP_PGM_PROPERTIES_COMPRESSION_SUPPORTED) == 0x00u))
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else if ((encryption_method != 0x00u) &&
             ((Xcp_Ptr->general->pgmProperties & XCP_PGM_PROPERTIES_ENCRYPTION_SUPPORTED) == 0x00u))
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else if ((programming_method != 0x00u) &&
             ((Xcp_Ptr->general->pgmProperties & XCP_PGM_PROPERTIES_NON_SEQ_PGM_SUPPORTED) == 0x00u))
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    /* access_method's own "advertised" bit is FUNCTIONAL_MODE, covering both 0x01 (functional) and
     * the 0x80..0xFF user-defined range alike -- PGM_PROPERTIES carries no third access-mode bit to
     * distinguish them, and 1.1/1.6.5.2.4 gives user-defined access methods no meaning of their own
     * for this module to check beyond "functional access is available at all". Never TRUE in this
     * build today: no configuration this task's own schema exposes can set FUNCTIONAL_MODE (design
     * doc DD92, a later task's own addition once the two functional callbacks it depends on
     * exist) -- see test/pgm_format_test.py's own module docstring. */
    else if ((access_method != 0x00u) &&
             ((Xcp_Ptr->general->pgmProperties & XCP_PGM_PROPERTIES_FUNCTIONAL_MODE) == 0x00u))
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        uint8 status_code = 0x00u;

        /* Design doc DD91: synchronous, not polled, breaking every other PGM callback's own
         * contract in this file on purpose -- PROGRAM_FORMAT only sets four bytes, so there is
         * nothing here worth deferring to Xcp_MainFunction, and this command adds no case to
         * Xcp_PgmPollPendingCommand/Xcp_PgmCompletePendingCommand below for exactly that reason.
         * Both a non-E_OK return and a non-zero status_code are treated identically -- refused
         * ERR_OUT_OF_RANGE, PROGRAM_FORMAT's own 1.7.3.2.5 row's only code for an integrator that
         * cannot honour a request this module has already confirmed is structurally permitted
         * (interface/Xcp.h, Xcp_ProgramFormat's own @retval documentation). */
        if ((Xcp_ProgramFormat(compression_method, encryption_method, programming_method,
                               access_method, &status_code) != E_OK) ||
            (status_code != 0x00u))
        {
            Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
        }
        else
        {
            /* Stored only now that both the structural check above and the integrator have
             * accepted the request -- a refused PROGRAM_FORMAT, either way, leaves
             * Xcp_Internal.pgm_format exactly as it was (Xcp_Internal.h, pgm_format's own
             * comment). */
            Xcp_Internal.pgm_format.compression_method = compression_method;
            Xcp_Internal.pgm_format.encryption_method = encryption_method;
            Xcp_Internal.pgm_format.programming_method = programming_method;
            Xcp_Internal.pgm_format.access_method = access_method;

            /* SP4c Task 6, DD86. 1.1/1.6.5.1.3: the Block Sequence Counter "shall be initialized to
             * one (1) when receiving a PROGRAM_FORMAT request message. This means that the first
             * PROGRAM request message following the PROGRAM_FORMAT request message starts with a
             * Block Sequence Counter of one (1)." Written as 0x00u here, which is that same
             * statement rather than a different one: this field holds the counter of the data
             * transfer request being served, and every data transfer request advances it BEFORE
             * reading it (Xcp_PgmAdvanceBlockSequenceCounter, below), so the first PROGRAM after
             * this command reads exactly the 1 the sentence names. Storing 1 here and advancing
             * after the read would need a second copy of the value for the deferred path --
             * Xcp_PgmPollPendingCommand must hand Xcp_ProgramWriteFunctional the SAME counter on
             * every poll of one transfer, which a field already advanced past that transfer's own
             * value cannot supply.
             *
             * Inside the acceptance branch, not at the top of this handler: 1.6.5.1.3's "when
             * receiving" taken to the letter would re-base the counter for a request this slave
             * then REFUSES, and a master answered ERR_OUT_OF_RANGE has no reason to restart its own
             * count -- so re-basing this one alone would manufacture exactly the divergence the
             * counter exists to detect. The same reasoning DD85 already applies to pgm_format's own
             * four fields immediately above, which a refused request likewise leaves untouched. */
            Xcp_Internal.pgm_block_sequence_counter = 0x00000000u;

            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

            Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
        }
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
     * adjacent in this one file instead of splitting them across a pointer and its target. Task 4
     * adds the PROGRAM_NEXT case below; a hard-coded single-command function would have blocked it.
     * Task 5 adds none: GET_PGM_PROCESSOR_INFO (Xcp_DTOCmdPgmGetPgmProcessorInfo below) reports this
     * build's own fixed configuration synchronously and never defers, so there is nothing of its
     * own for this switch to ever poll. Design doc §5's "one case each" sketch predates DD68, which
     * settles this -- the same way PROGRAM_MAX and PROGRAM_NEXT already share PROGRAM's own case
     * just below rather than each getting a distinct one. */
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
                                        Xcp_Internal.pending_command.args.program_prepare_code_size,
                                        pStatusCode);
            break;
        }
        case XCP_PID_CMD_PROGRAM_CLEAR:
        {
            /* SP4c Task 5: PROGRAM_CLEAR's own PID is shared by both access modes (DD93), so which
             * callback a deferred poll must re-invoke is no longer implied by pid alone --
             * program_clear_functional says which (source/Xcp_Internal.h, its own comment). */
            if (Xcp_Internal.pending_command.program_clear_functional == TRUE)
            {
                /* Xcp_ProgramClearFunctional's contract also takes the area bitmask on every call,
                 * the same shape the absolute-mode branch just below has -- but no address: DD93's
                 * "the MTA has no influence on the clearing functionality" holds just as much on a
                 * later poll as it does on the handler's own first call. */
                result = Xcp_ProgramClearFunctional(
                        Xcp_Internal.pending_command.args.program_clear_range, pStatusCode);
            }
            else
            {
                /* Xcp_ProgramClear's contract also takes address and clearRange on every call, the
                 * same shape Xcp_ProgramPrepare's own case just above has and for the same reason: the
                 * MTA is re-read from Xcp_Internal.memory_transfer.address directly -- stable for the
                 * duration, since DD55's ERR_CMD_BUSY gate refuses any interloping SET_MTA -- and the
                 * clear range comes from the slot, the only place left holding it once the handler
                 * that parsed it has returned. */
                result = Xcp_ProgramClear(Xcp_Internal.memory_transfer.address,
                                          Xcp_Internal.pending_command.args.program_clear_range,
                                          pStatusCode);
            }
            break;
        }
        case XCP_PID_CMD_PROGRAM:
        case XCP_PID_CMD_PROGRAM_MAX:
        case XCP_PID_CMD_PROGRAM_NEXT:
        {
            /* All three commands write through the identical write contract, from the identical
             * Xcp_Internal.pgm_block standing state (Task 3; PROGRAM_NEXT joins it in Task 4,
             * DD63) -- pData and length are re-read directly from it on every poll, exactly as the
             * MTA is re-read from Xcp_Internal.memory_transfer.address, and for the same reason:
             * stable for the duration, since DD55's ERR_CMD_BUSY gate refuses any interloping
             * command that could touch either. None of the three handlers stores anything in
             * pending_command.args -- pgm_block already IS that storage, and a union member here
             * would only duplicate it.
             *
             * SP4c Task 6: WHICH write contract is Xcp_PgmCallProgramWrite's own question (below),
             * asked here through the very same helper each handler's own first call went through,
             * so a poll can never continue a functional write through the absolute callback or the
             * reverse. The Block Sequence Counter that helper passes is likewise re-read from
             * standing state, and is still this transfer's own value: nothing advances it until the
             * NEXT data transfer request, which DD55's gate cannot let in while this one is still
             * pending. */
            result = Xcp_PgmCallProgramWrite(pStatusCode);
            break;
        }
        case XCP_PID_CMD_PROGRAM_VERIFY:
        {
            /* Xcp_ProgramVerify's contract also takes mode, type and value on every call, the same
             * shape PROGRAM_PREPARE's and PROGRAM_CLEAR's own cases above have -- all three are
             * re-read from pending_command.args directly, since none of them is standing module
             * state elsewhere the way the MTA is for every other PGM command's own case here. */
            result = Xcp_ProgramVerify(Xcp_Internal.pending_command.args.program_verify.mode,
                                       Xcp_Internal.pending_command.args.program_verify.type,
                                       Xcp_Internal.pending_command.args.program_verify.value,
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
            case XCP_PID_CMD_PROGRAM_CLEAR:
            {
                Xcp_PgmCompleteProgramClear(statusCode);
                break;
            }
            case XCP_PID_CMD_PROGRAM:
            case XCP_PID_CMD_PROGRAM_MAX:
            case XCP_PID_CMD_PROGRAM_NEXT:
            {
                Xcp_PgmCompleteProgramWrite(statusCode);
                break;
            }
            case XCP_PID_CMD_PROGRAM_VERIFY:
            {
                Xcp_PgmCompleteProgramVerify(statusCode);
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
     * silently ended an established session on any ordinary SYNCH -- 1.1/1.7.1.2 requires SYNCH to
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

static boolean Xcp_PgmBlockIsActive(void)
{
    boolean result;

    if (Xcp_Internal.pgm_block.requested_elements != 0x00u)
    {
        result = TRUE;
    }
    else
    {
        result = FALSE;
    }

    return result;
}

static void Xcp_PgmBlockAcknowledgeFrame(void)
{
    Xcp_Internal.pgm_block.requested_elements -= Xcp_Internal.pgm_block.frame_elements;
}

static boolean Xcp_PgmDataTransferRefusedByFormat(void)
{
    boolean result;

    /* One term per REQUIRED bit, each checked against pgm_format's own matching field -- see this
     * function's own forward declaration for why pgm_format itself, and not a separate flag, is
     * what each term reads. Mutation-verified per term (task report): deleting or inverting any
     * ONE of the three below must fail only that capability's own parametrisation in
     * test/pgm_format_test.py, not the other two. */
    if (((Xcp_Ptr->general->pgmProperties & XCP_PGM_PROPERTIES_COMPRESSION_REQUIRED) != 0x00u) &&
        (Xcp_Internal.pgm_format.compression_method == 0x00u))
    {
        result = TRUE;
    }
    else if (((Xcp_Ptr->general->pgmProperties & XCP_PGM_PROPERTIES_ENCRYPTION_REQUIRED) != 0x00u) &&
             (Xcp_Internal.pgm_format.encryption_method == 0x00u))
    {
        result = TRUE;
    }
    else if (((Xcp_Ptr->general->pgmProperties & XCP_PGM_PROPERTIES_NON_SEQ_PGM_REQUIRED) != 0x00u) &&
             (Xcp_Internal.pgm_format.programming_method == 0x00u))
    {
        result = TRUE;
    }
    else
    {
        result = FALSE;
    }

    return result;
}

void Xcp_PgmBlockAbort(void)
{
    Xcp_Internal.pgm_block.requested_elements = 0x00u;
    Xcp_Internal.pgm_block.frame_elements = 0x00u;

    /* Final review F2/F3: length is cleared too, unlike this function's original two fields alone.
     * PROGRAM_NEXT's own two callers (wrong count, short frame) never needed it -- a following
     * PROGRAM always overwrites pgm_block.length by direct assignment, never accumulation, so a
     * stale value between an abort and the next PROGRAM was harmless there. It is not harmless at
     * a session boundary: DD63's own cross-session hygiene note in Xcp_Internal.h already clears
     * this same field from Xcp_Init for exactly that reason, and this function is now ALSO the
     * one Xcp_CTOCmdStdConnect (Xcp_Std.c, F2), Xcp_PgmCompleteProgramReset (F2) and
     * Xcp_DTOCmdPgmProgram's own zero-element branch (F3) call, so it has to leave the same
     * complete, empty state Xcp_Init does. */
    Xcp_Internal.pgm_block.length = 0x0000u;
}

void Xcp_PgmFormatReset(void)
{
    /* SP4c Task 3, DD85: all four fields back to their own spec-default values -- see this
     * function's own forward declaration (Xcp_Internal.h) and pgm_format's own comment there for
     * why this is the whole of the format's lifetime, with no separate flag to keep in step. */
    Xcp_Internal.pgm_format.compression_method = 0x00u;
    Xcp_Internal.pgm_format.encryption_method = 0x00u;
    Xcp_Internal.pgm_format.programming_method = 0x00u;
    Xcp_Internal.pgm_format.access_method = 0x00u;

    /* SP4c Task 6, DD86: the counter goes with the format it belongs to. DD86's own table names
     * PROGRAM_RESET and CONNECT as its reset points, and both of those reach here -- so does
     * SET_MTA, which DD86 does not name, and resetting there too is deliberate rather than
     * incidental: the counter counts ONE stream, the stream is the one PROGRAM_FORMAT opened, and
     * DD85 ends that format's life at SET_MTA. Nothing can observe the difference either way, since
     * every path back to the functional callback runs through a fresh PROGRAM_FORMAT, which
     * re-initialises this field regardless (Xcp_DTOCmdPgmProgramFormat above) -- and, since final
     * review F1, because the abort below leaves no in-flight block that could reach a write callback
     * carrying the re-based value. Before that abort existed the claim was too strong: a functional
     * block open across a SET_MTA had its counter re-based here and then advanced back to 1 by the
     * completing frame, so the integrator was handed 1 for a frame the master had counted as 2. */
    Xcp_Internal.pgm_block_sequence_counter = 0x00000000u;

    /* Final review F1, the half PROGRAM_FORMAT's own ERR_SEQUENCE gate cannot reach. A format that
     * has just died cannot go on describing a transfer still in flight: 1.6.5.2.4 puts the two in
     * ONE sentence -- the format "is valid till end of this sequence. The sequence will be
     * terminated by other commands e.g. SET_MTA" -- so whatever ends the format ends the transfer it
     * described, and a block half-delivered inside that sequence is part of what was terminated.
     *
     * Placed here rather than in Xcp_DTOCmdStdSetMta (source/Xcp_Std.c), which is the caller that
     * needs it: SET_MTA is the ONE door out of the three that did not already abort the block on its
     * own (Xcp_CTOCmdStdConnect and Xcp_PgmCompleteProgramReset both call Xcp_PgmBlockAbort()
     * immediately beside their own call to this function, so for them this line is an idempotent
     * no-op), and putting the abort inside the format's own reset makes the invariant hold at every
     * door there will ever be instead of at the two somebody remembered.
     *
     * Aborting rather than refusing, and that asymmetry with PROGRAM_FORMAT above is forced by the
     * specification rather than chosen: 1.6.5.1.1 lists SET_MTA FIRST among the commands that "must
     * always be available during a memory programming sequence", and SET_MTA's own 1.7.3.2.1 row
     * carries no ERR_SEQUENCE to refuse it with (1.0: ERR_CMD_BUSY, ERR_PGM_ACTIVE,
     * ERR_CMD_UNKNOWN, ERR_CMD_SYNTAX, ERR_OUT_OF_RANGE). So SET_MTA still answers 0xFF and still
     * moves the MTA; what it may not do is leave a block behind that a later PROGRAM_NEXT completes
     * into the wrong callback, or at an address the opening PROGRAM never named. The master learns
     * on its next PROGRAM_NEXT, which is refused ERR_SEQUENCE by Xcp_DTOCmdPgmProgramNext's own
     * block gate -- a code in THAT command's 1.7.3.2.5 row, whose stated master action is
     * "SYNCH+PROGRAM", i.e. re-open the block, which is exactly the recovery this state calls for.
     *
     * Discarding the partial block loses nothing the master was ever promised: 1.6.5.1.3 has the
     * slave acknowledge only the LAST frame of a block transfer, so nothing in an incomplete one was
     * agreed final -- DD64's own reasoning for the zero-element PROGRAM, which discards rather than
     * flushes for that same reason (Xcp_DTOCmdPgmProgram above). */
    Xcp_PgmBlockAbort();
}

static void Xcp_PgmAdvanceBlockSequenceCounter(void)
{
    /* One statement, and the rollover comes free with it: 1.1/1.6.5.1.3's "at the maximum value the
     * Block Sequence Counter rolls over and starts at 0x00 with the next data transfer request
     * message" is exactly what an unsigned addition past this type's maximum already does, by C's
     * own definition of unsigned arithmetic. An explicit `== 0xFFFFFFFFu ? 0x00u : n + 0x01u`
     * would restate that in a branch this suite could never execute -- reaching it takes 2^32 data
     * transfer requests -- and an unreachable branch is one nothing can prove right; see this
     * field's own comment in source/Xcp_Internal.h, and the task report, for how the rollover was
     * verified instead. */
    Xcp_Internal.pgm_block_sequence_counter += 0x00000001u;
}

static Std_ReturnType Xcp_PgmCallProgramWrite(uint8 *pStatusCode)
{
    Std_ReturnType result;

    /* See this function's own forward declaration above for why one helper serves all four call
     * sites, and why any non-zero access method -- not only 0x01 -- selects the functional
     * callback. */
    if (Xcp_Internal.pgm_format.access_method != 0x00u)
    {
        result = Xcp_ProgramWriteFunctional(Xcp_Internal.pgm_block_sequence_counter,
                                            Xcp_Internal.pgm_block.data,
                                            Xcp_Internal.pgm_block.length,
                                            pStatusCode);
    }
    else
    {
        result = Xcp_ProgramWrite(Xcp_Internal.memory_transfer.address,
                                  Xcp_Internal.pgm_block.data,
                                  Xcp_Internal.pgm_block.length,
                                  pStatusCode);
    }

    return result;
}

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

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.5.1.3
         * INTERLEAVED_MODE (bit 1) "indicates whether the Interleaved Mode is available during
         * Programming", sized by QUEUE_SIZE_PGM. Hardcoded clear for the same reason
         * Xcp_DTOCmdStdGetCommModeInfo (source/Xcp_Std.c) clears COMM_MODE_OPTIONAL's bit 1: this
         * module implements no receipt queue in either mode, and a master told it may send
         * QUEUE_SIZE_PGM consecutive commands would be refused ERR_CMD_BUSY on the second.
         * QUEUE_SIZE_PGM below reports 0 to match. */

        if (Xcp_Ptr->general->slaveBlockModeSupported == TRUE)
        {
            comm_mode_pgm |= (0x01u << 0x06u);
        }

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = comm_mode_pgm;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = (uint8)Xcp_Ptr->general->maxCto;

        /* DD62, revising DD56, corrected by final-review F4: MAX_BS_PGM is its own configured
         * value (programming.max_block_size), not the live protocol_layer maxBS -- exactly like
         * MAX_CTO_PGM just above and MIN_ST_PGM/QUEUE_SIZE_PGM just below, all four now the live
         * Xcp_Ptr->general field for THIS configuration, not a value shared across every
         * configuration in the build.
         *
         * Xcp_Ptr->general->maxBsPgm (script/source_cfg.c.jinja2), not the compile-time
         * XCP_PGM_MAX_BLOCK_SIZE macro this byte read until F4: that macro is deliberately the
         * LARGEST programming.max_block_size across every configuration, because
         * Xcp_Internal.pgm_block is sized once for a module compiled once for all of them -- so on
         * a build holding a max_block_size=1 configuration beside a max_block_size=200 one, the
         * macro reported 200 from the FIRST configuration's own response, a block its own master
         * was never told to expect and this build's buffer would still have refused
         * ERR_MEMORY_OVERFLOW had it actually tried. The runtime field is the per-configuration
         * value DD62/§9 criterion 5 always meant; the macro stays exactly what it was for sizing
         * the buffer (Xcp_Internal.h), which must still be at least as large as the largest
         * configuration's own advertised maximum -- reporting anything larger than the runtime
         * field here would still be the promise-a-block-the-buffer-cannot-hold hazard this
         * comment used to warn about, and the buffer macro's own bound is exactly what keeps this
         * field from ever exceeding it. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = Xcp_Ptr->general->maxBsPgm;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = Xcp_Ptr->general->minST;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u] = 0x00u; /* QUEUE_SIZE_PGM, see above */

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

        /* Final review F2, the same defence-in-depth reasoning the paragraph above already gives
         * for pgm_state itself: PROGRAM_RESET mid-block disconnects without this, and the CONNECT
         * that necessarily follows (DISCONNECT is refused ERR_PGM_ACTIVE while ACTIVE, so CONNECT
         * is the only door back) already clears it on its own door (Xcp_CTOCmdStdConnect,
         * Xcp_Std.c, F2) -- making this line as unobservable on its own as the pgm_state write
         * above already is, and kept for the identical reason: the command that ends a sequence is
         * where that sequence's state belongs, not correct only by virtue of a line in another
         * file. */
        Xcp_PgmBlockAbort();

        /* SP4c Task 3, DD85: PROGRAM_RESET ends the format's own lifetime exactly as it ends the
         * session's -- the identical defence-in-depth reasoning the two paragraphs above already
         * give for pgm_state and pgm_block, and the identical unobservability, for the identical
         * reason: the CONNECT that necessarily follows a disconnect (Xcp_CTOCmdStdConnect,
         * Xcp_Std.c) already calls this same function on its own door. */
        Xcp_PgmFormatReset();

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

static void Xcp_PgmCompleteProgramClear(uint8 statusCode)
{
    if (statusCode == 0x00u)
    {
        /* 1.1/1.6.5.1.2 specifies no response payload beyond the standard positive response --
         * matching PROGRAM_RESET's and PROGRAM_PREPARE's own success responses above. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* 1.1/1.6.5.1.2 names no error at all for a failed erase -- it describes the modes and
         * parameters and stops -- so 1.7.3.2.5's own PROGRAM_CLEAR row is the only guide, and this
         * answers a code that row actually lists: no deviation, unlike PROGRAM_RESET's DD57 two
         * hundred lines above. ERR_ACCESS_DENIED, not ERR_GENERIC -- and not merely because it is
         * one of the row's six (ERR_CMD_BUSY, ERR_CMD_SYNTAX, ERR_OUT_OF_RANGE, ERR_ACCESS_DENIED,
         * ERR_ACCESS_LOCKED, ERR_SEQUENCE), but because its own definition in the 1.0 error-code
         * table -- "The memory location is not accessible" -- is the precise description of an
         * integrator that could not erase the sector the master asked for, where ERR_GENERIC is
         * merely "Generic error". The asymmetry with PROGRAM_START's and PROGRAM_PREPARE's own
         * ERR_GENERIC above is deliberate, not an oversight: 1.6.5.1.1 names ERR_GENERIC itself
         * for a slave "not in a state which permits programming" -- a statement about the SLAVE --
         * where a failed PROGRAM_CLEAR is a statement about the MEMORY, and ERR_ACCESS_DENIED is
         * what the specification's own vocabulary calls that. DD67 (fix round 1) records this. */
        Xcp_FillErrorPacket(XCP_E_ASAM_ACCESS_DENIED, &Xcp_Internal.cto_response.pdu_info);
    }

    /* Publishes for both outcomes alike, matching Xcp_PgmCompleteProgramStart above. */
    Xcp_Internal.cto_response.successful_transmission_pending = TRUE;
}

static void Xcp_PgmCompleteProgramWrite(uint8 statusCode)
{
    if (statusCode == 0x00u)
    {
        /* DD66. 1.1/1.6.5.1.3: "The MTA will be post-incremented by the number of data bytes."
         * Only on success: 1.7.3.2.5 gives PROGRAM the pre-action SYNCH+SET_MTA, so a master
         * recovering from a failure re-points the MTA itself -- a slave that had already advanced
         * it would have moved a pointer the master believes it still controls, and a master
         * trusting the slave's position instead of re-setting it would resume one block further
         * on, leaving a hole in the programmed image that no error reported.
         *
         * Unchanged by Task 4: Xcp_Internal.pgm_block.length already holds the block's TRUE total
         * length by the time this runs, whether it was set once by a single-frame PROGRAM/
         * PROGRAM_MAX (Task 3) or accumulated across a PROGRAM plus however many PROGRAM_NEXT
         * frames a master block mode sequence needed (DD63) -- this line has no way to tell the
         * two shapes apart, and does not need to.
         *
         * SP4c Task 6 conditions it on the access mode, and the specification's own layout is why:
         * the sentence quoted above sits under 1.6.5.1.3's *Absolute Access mode* heading, while
         * its *Functional Access mode* paragraph -- the one that says "the ECU software knows the
         * start address for the new flash content automatically" -- replaces the MTA's meaning
         * entirely with the Block Sequence Counter (DD86) and never post-increments an address.
         * Advancing it anyway would be silent and, for a master that programmed functionally and
         * then switched to absolute access without re-sending SET_MTA, wrong by one whole block.
         * test/pgm_functional_test.py's own test_a_functional_write_never_moves_the_mta observes
         * exactly that, through the only window the harness has on this field: a following absolute
         * write's own address argument. */
        if (Xcp_Internal.pgm_format.access_method == 0x00u)
        {
            Xcp_Internal.memory_transfer.address += Xcp_Internal.pgm_block.length;
        }

        /* 1.1/1.6.5.1.3 and 1.6.5.2.6 both specify no response payload beyond the standard
         * positive response, matching PROGRAM_RESET's, PROGRAM_PREPARE's and PROGRAM_CLEAR's own
         * success responses above. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* For PROGRAM, no deviation: its own 1.7.3.2.5 row lists ERR_ACCESS_DENIED (and not
         * ERR_GENERIC, absent from that row entirely, unlike PROGRAM_START's and PROGRAM_PREPARE's
         * own rows above) -- exactly the asymmetry DD67 already records for PROGRAM_CLEAR's own
         * failure path, generalised from a failed erase to a failed write: the memory that could
         * not be reached is what failed, not the slave's own state.
         *
         * For PROGRAM_MAX, sharing this completion IS a deviation, task 3 review fix round 1
         * finding 2 caught unrecorded, in DD57's own form (the deviation DD57 itself records for
         * PROGRAM_RESET's ERR_GENERIC): PROGRAM_MAX's own 1.7.3.2.5 row is exactly ERR_CMD_BUSY,
         * ERR_CMD_UNKNOWN, ERR_SEQUENCE and ERR_MEMORY_OVERFLOW -- no ERR_ACCESS_DENIED, and,
         * unlike PROGRAM's row, no ERR_CMD_SYNTAX or ERR_ACCESS_LOCKED either. None of the four
         * listed codes fits a write that reached the integrator and failed: ERR_CMD_BUSY and
         * ERR_CMD_UNKNOWN are dispatch-level conditions this point in the code has already passed,
         * ERR_SEQUENCE is this handler's own session and block-active gates above, and
         * ERR_MEMORY_OVERFLOW is the buffer-overflow guard just above -- both already spoken for by
         * conditions checked before the integrator is ever called, so pressing either into service
         * here would make two structurally different failures answer identically. ERR_ACCESS_DENIED
         * is kept as the recorded deviation: the same code, and the same reasoning, PROGRAM's own
         * (non-deviating) row already gives for the identical situation -- a write the integrator
         * could not complete because the memory was not reachable -- which sharing one completion
         * function between the two commands makes the natural, and now documented, choice.
         *
         * For PROGRAM_NEXT, joining this shared completion in Task 4 is NOT a deviation, unlike
         * PROGRAM_MAX just above: its own 1.7.3.2.5 row (Xcp_CTOErrorMatrix[0xCA], source/Xcp.c)
         * already lists ERR_ACCESS_DENIED alongside ERR_SEQUENCE, ERR_MEMORY_OVERFLOW and the
         * others -- the same code PROGRAM's own row gives for the identical situation, so no new
         * recorded exception is needed for this third command to reach it. */
        Xcp_FillErrorPacket(XCP_E_ASAM_ACCESS_DENIED, &Xcp_Internal.cto_response.pdu_info);
    }

    /* Publishes for both outcomes alike, matching Xcp_PgmCompleteProgramStart above. */
    Xcp_Internal.cto_response.successful_transmission_pending = TRUE;
}

static void Xcp_PgmCompleteProgramVerify(uint8 statusCode)
{
    if (statusCode == 0x00u)
    {
        /* 1.1/1.6.5.2.7 specifies no response payload beyond the standard positive response --
         * matching PROGRAM_RESET's, PROGRAM_PREPARE's and PROGRAM_CLEAR's own success responses
         * above. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* Design doc DD91: "ERR_VERIFY, also in the row, is answered when the integrator reports
         * failure." Unlike PROGRAM_CLEAR's and PROGRAM_WRITE's own ERR_ACCESS_DENIED just above --
         * both statements about memory that could not be reached -- a failed verification is a
         * statement about content that WAS reached and read, but did not pass the check, which is
         * the more precise condition XCP part 2 - Protocol Layer Specification 1.7.3.2.5's own
         * ERR_VERIFY names directly for this row. No deviation: this is the listed code, not a
         * substitute for one the row omits. */
        Xcp_FillErrorPacket(XCP_E_ASAM_VERIFY, &Xcp_Internal.cto_response.pdu_info);
    }

    /* Publishes for both outcomes alike, matching Xcp_PgmCompleteProgramStart above. */
    Xcp_Internal.cto_response.successful_transmission_pending = TRUE;
}

#endif /* #if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON) */
