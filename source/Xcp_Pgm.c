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

        if (push_result == E_OK)
        {
            Xcp_Internal.pending_command.event_outstanding = TRUE;
            Xcp_Internal.event.successful_transmission_pending = TRUE;
        }
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

#endif /* #if (XCP_FLASH_PROGRAMMING_ENABLED == STD_ON) */
