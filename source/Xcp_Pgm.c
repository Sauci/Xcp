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
 * @brief Finishes PROGRAM and PROGRAM_MAX, building the positive response or ERR_ACCESS_DENIED
 * from statusCode, and advancing the MTA on success only (DD66).
 * @details Forward-declared for the same reason Xcp_PgmCompleteProgramStart above is:
 * Xcp_DTOCmdPgmProgram and Xcp_DTOCmdPgmProgramMax below both call it directly for an integrator
 * whose work completes instantaneously (spec Section 4) -- the same function
 * Xcp_PgmCompletePendingCommand dispatches to when either command instead completes on a later
 * Xcp_MainFunction poll. Shared between the two commands (Task 3) because both write through the
 * identical Xcp_ProgramWrite contract, from the identical Xcp_Internal.pgm_block standing state --
 * there is nothing left to distinguish once the write itself has been issued.
 */
static void Xcp_PgmCompleteProgramWrite(uint8 statusCode);

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
    /* Fix round 2. 1.6.5.1.2 defines exactly two mode bytes, 0x00 (absolute access mode, default)
     * and 0x01 (functional access mode), as a table -- an enumeration of the values this command
     * recognises, not a bit field with reserved-but-harmless positions -- and this slave offers
     * only the first (DD68's PGM_PROPERTIES says so on the wire too). There is therefore exactly
     * one mode byte to ACCEPT, not one to refuse: testing `!= 0x00u` refuses 0x01 and every value
     * neither this slave nor the specification itself gives a meaning to (0x02..0xFF), where
     * testing `== 0x01u` (the first form of this check) refused only 0x01 and silently accepted
     * every one of those undefined values as if it were 0x00 -- absolute mode, on a field that is
     * about to be read as a byte length and handed to an erase. Refused ERR_OUT_OF_RANGE, whose
     * own 1.7.3.2.5 row lists the action "retry other parameter", correct for ANY mode byte this
     * slave does not implement, not only for 0x01 specifically. Checked, and refused, BEFORE the
     * clear range is even read below: 1.6.5.1.2 gives that same DWORD field completely different
     * readings depending on the mode -- a length in absolute mode, a bit mask of memory areas in
     * functional mode -- so a handler that read it as a length first would already have called
     * Xcp_ProgramClear with whatever the DWORD means as a length, under a mode byte the master may
     * not have meant as absolute at all. */
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
    else
    {
        const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];

        /* DD64. 1.1/1.6.5.1.3: "The end of the memory segment is indicated, when the number of
         * data elements is 0." Distinct from programming zero bytes: there is no block open to
         * flush (Task 3 never opens one -- that is Task 4's PROGRAM_NEXT), so this simply ends the
         * segment and answers, without ever reaching Xcp_ProgramWrite. It does NOT end the
         * programming sequence -- 1.6.5.1.3 gives that to PROGRAM_RESET, which SP4a implements. */
        if (number_of_data_elements == 0x00u)
        {
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

            Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
        }
        else
        {
            const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
            const uint8 alignment = (uint8)Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
            const uint8 frame_elements = Xcp_BlockTransferFrameElements(number_of_data_elements, element_size);
            const uint16 length = (uint16)(frame_elements * element_size);

            /* Task 3 is "PROGRAM without block mode" (design doc title): a declared count this
             * module cannot receive within the one frame it arrived on is refused up front, the
             * same choice Xcp_DTOCmdCalDownload makes through Xcp_DataTransferInitialize when ITS
             * OWN masterBlockModeSupported is FALSE (source/Xcp.c) --
             * test_download_returns_err_out_of_range_when_the_count_exceeds_a_single_packet
             * (test/download_test.py) pins the identical condition for that sibling command.
             * Task 4's PROGRAM_NEXT is what turns this into an opened block instead of a refusal;
             * nothing here touches Xcp_Internal.block_transfer, which stays entirely Task 4's to
             * introduce. Checked before anything past the header is read, so an oversized count
             * never reaches the checks below on a false pretense. */
            if (frame_elements != number_of_data_elements)
            {
                Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
            }
            /* The buffer this write stages through is sized (source/Xcp_Internal.h) as the LARGER
             * of XCP_PGM_MAX_BLOCK_SIZE*(XCP_MAX_CTO-2) and XCP_MAX_CTO-1, so it always holds at
             * least one full PROGRAM frame's own (MAX_CTO-2)-byte ceiling -- this condition is
             * unreachable for every schema-legal programming.max_block_size (fix round 1, finding
             * 1) and is kept anyway: a handler must never trust a generated bound merely because
             * the formula that produced it is believed correct, and deleting a guard because
             * analysis says it cannot fire is exactly how the sizing bug this round found would
             * have gone unnoticed a second time. Answers the one code 1.7.3.2.5's own PROGRAM row
             * shares with DD63's own multi-frame overflow -- the same fact, that this module cannot
             * hold what was declared, reached here (were it ever reached) by configuration rather
             * than by accumulation. */
            else if (length > (uint16)sizeof(Xcp_Internal.pgm_block.data))
            {
                Xcp_FillErrorPacket(XCP_E_ASAM_MEMORY_OVERFLOW, &Xcp_Internal.cto_response.pdu_info);
            }
            else if (pPduInfo->SduLength < (PduLengthType)(0x02u + alignment + length))
            {
                /* The frame is shorter than the payload it announces -- mirrors
                 * Xcp_DTOCmdCalDownload's own identical guard (source/Xcp_Cal.c). Without this the
                 * handler copies whatever follows the received PDU into pgm_block, and from there
                 * into flash. */
                Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
            }
            else
            {
                uint8_least idx;
                uint8 status_code = 0x00u;

                /* DD63/design Section 5: copied into pgm_block even though this one frame is the
                 * whole block by itself here -- Task 4 changes only how many frames contribute
                 * before this same write fires, never the write itself. */
                for (idx = 0x00u; idx < length; idx++)
                {
                    Xcp_Internal.pgm_block.data[idx] = pPduInfo->SduDataPtr[0x02u + alignment + idx];
                }

                Xcp_Internal.pgm_block.length = length;

                /* The FIRST call happens here, not on the next Xcp_MainFunction, for the same
                 * reason PROGRAM_CLEAR's own first call does above: an integrator whose work is
                 * instantaneous returns E_OK from it and the master is answered on this very
                 * exchange. Spec Section 4. */
                if (Xcp_ProgramWrite(Xcp_Internal.memory_transfer.address,
                                     Xcp_Internal.pgm_block.data,
                                     Xcp_Internal.pgm_block.length,
                                     &status_code) == E_OK)
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
    /* DD65. 1.6.5.2.6: "This command does not support block transfer and it may not be used
     * within a block transfer sequence." Its own 1.7.3.2.5 row lists ERR_SEQUENCE for it. No
     * PROGRAM in this build ever leaves Xcp_BlockTransferIsActive() TRUE: Task 3's own
     * Xcp_DTOCmdPgmProgram above never opens one, and Task 4's PROGRAM_NEXT, which does, does not
     * exist yet -- so this branch has no test that can reach it today (task report). Implemented
     * ahead of its user regardless, the same relationship PROGRAM_CLEAR's own pgm_state gate had
     * with SP4a before this task existed to call it (design doc Section 2). */
    else if (Xcp_BlockTransferIsActive() == TRUE)
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

            if (Xcp_ProgramWrite(Xcp_Internal.memory_transfer.address,
                                 Xcp_Internal.pgm_block.data,
                                 Xcp_Internal.pgm_block.length,
                                 &status_code) == E_OK)
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
                                        Xcp_Internal.pending_command.args.program_prepare_code_size,
                                        pStatusCode);
            break;
        }
        case XCP_PID_CMD_PROGRAM_CLEAR:
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
            break;
        }
        case XCP_PID_CMD_PROGRAM:
        case XCP_PID_CMD_PROGRAM_MAX:
        {
            /* Both commands write through the identical Xcp_ProgramWrite contract, from the
             * identical Xcp_Internal.pgm_block standing state (Task 3) -- pData and length are
             * re-read directly from it on every poll, exactly as the MTA is re-read from
             * Xcp_Internal.memory_transfer.address just below, and for the same reason: stable
             * for the duration, since DD55's ERR_CMD_BUSY gate refuses any interloping command
             * that could touch either. Neither handler stores anything in pending_command.args --
             * pgm_block already IS that storage, and a union member here would only duplicate
             * it. */
            result = Xcp_ProgramWrite(Xcp_Internal.memory_transfer.address,
                                      Xcp_Internal.pgm_block.data,
                                      Xcp_Internal.pgm_block.length,
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
            {
                Xcp_PgmCompleteProgramWrite(statusCode);
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

        /* DD62, revising DD56: MAX_BS_PGM is its own configured value (XCP_PGM_MAX_BLOCK_SIZE),
         * not the live protocol_layer maxBS -- unlike MAX_CTO_PGM just above and MIN_ST_PGM/
         * QUEUE_SIZE_PGM just below, which stay the live Xcp_Ptr->general fields exactly as DD56
         * left them. A compile-time macro, not a runtime field, because it is what Xcp_Internal
         * .pgm_block (source/Xcp_Internal.h) is actually sized from -- reporting anything else
         * here would let this response promise a block the buffer cannot hold. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = XCP_PGM_MAX_BLOCK_SIZE;
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
         * on, leaving a hole in the programmed image that no error reported. */
        Xcp_Internal.memory_transfer.address += Xcp_Internal.pgm_block.length;

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
         * function between the two commands makes the natural, and now documented, choice. */
        Xcp_FillErrorPacket(XCP_E_ASAM_ACCESS_DENIED, &Xcp_Internal.cto_response.pdu_info);
    }

    /* Publishes for both outcomes alike, matching Xcp_PgmCompleteProgramStart above. */
    Xcp_Internal.cto_response.successful_transmission_pending = TRUE;
}

#endif /* #if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON) */
