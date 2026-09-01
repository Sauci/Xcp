/**
 * @file Xcp_DaqRuntime.c
 * @author
 * @date
 *
 * @defgroup XCP_DAQ_RUNTIME_C DATA ACQUISITION runtime: sampling, framing and the DTO queue
 * @ingroup XCP
 */

#include "Xcp_Internal.h"

#include "Xcp_Rt.h"

/*------------------------------------------------------------------------------------------------*/
/* local variable definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

/**
 * @brief PduInfoType handed to CanIf for the frame currently at the head of the ring.
 * @details CanIf_Transmit is asynchronous, so the frame it points at must stay in the ring until
 * its confirmation; only Xcp_DaqQueuePop releases it. Filled by Xcp_DaqQueuePeek, called from the
 * DAQ arm of Xcp_TransmitOneFrame's arbitration (Xcp.c).
 */
static PduInfoType Xcp_DaqTxPduInfo;

/*------------------------------------------------------------------------------------------------*/
/* local function definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

/**
 * @brief Writes the identification field of one ODT into a frame.
 * @return Number of bytes written: 1, 2, 3 or 4 depending on the configured type.
 * @details Data bytes sampled after this are pass-through -- whatever Xcp_ReadSlaveMemoryU8/16/32
 * writes goes into the frame verbatim. byteOrder governs only the protocol's own multi-byte
 * fields, here the DAQ list number of the two WORD forms, exactly as it does for UPLOAD.
 * @note XCP part 2 - Protocol Layer Specification 1.1/1.1.2.1.
 */
static uint8 Xcp_DaqWriteIdentificationField(Xcp_DtoFrameType *pFrame,
                                             uint16 daqListNumber,
                                             uint8 odtNumber)
{
    uint8 length;

    switch (Xcp_Ptr->general->identificationFieldType)
    {
        case RELATIVE_BYTE:
        {
            pFrame->data[0x00u] = odtNumber;
            pFrame->data[0x01u] = (uint8)daqListNumber;
            length = 0x02u;

            break;
        }
        case RELATIVE_WORD:
        {
            pFrame->data[0x00u] = odtNumber;
            Xcp_CopyFromU16WithOrder(daqListNumber, &pFrame->data[0x01u], Xcp_Ptr->general->byteOrder);
            length = 0x03u;

            break;
        }
        case RELATIVE_WORD_ALIGNED:
        {
            pFrame->data[0x00u] = odtNumber;
            /* 1.1/1.1.2.1 gives the FILL byte no defined value; the trailing value the rest of
             * the module already pads with (Xcp_FinalizeResPacket) is the natural choice. */
            pFrame->data[0x01u] = Xcp_Ptr->general->trailingValue;
            Xcp_CopyFromU16WithOrder(daqListNumber, &pFrame->data[0x02u], Xcp_Ptr->general->byteOrder);
            length = 0x04u;

            break;
        }
        default:
        {
            /* ABSOLUTE: absolute_ODT_NUMBER = FIRST_PID(list) + relative ODT_NUMBER. */
            pFrame->data[0x00u] = (uint8)(Xcp_Ptr->config->daqList[daqListNumber].firstPid + odtNumber);
            length = 0x01u;

            break;
        }
    }

    return length;
}

/**
 * @brief Assembles one ODT into one DTO frame.
 * @return E_OK when the ODT held at least one written entry and pFrame was filled; E_NOT_OK when
 * every entry was empty, in which case pFrame must not be queued.
 * @details DD14: Xcp_DaqListClearEntries (source/Xcp_Daq.c) resets an entry's address to 0 field
 * by field, with no ordering guarantee relative to a concurrent reader, and CLEAR_DAQ_LIST may run
 * in CanIf's receive context while this walks the same array from a task or an interrupt --
 * including this sampler itself running in an interrupt that preempts a clear already in progress
 * at task level, which is exactly the context Xcp_TriggerEventChannel's own public documentation
 * invites. Reading address and length as two separate accesses against the live, shared entry
 * could therefore observe a stale (not-yet-cleared) address together with an already-cleared
 * length, or the reverse -- and dereferencing a stale address while length still reads non-zero is
 * exactly the address-0 dereference this guards against. So every entry this function is about to
 * read memory through is copied field by field, under the exclusive area, into a local buffer, and
 * the area is released before any copy is dereferenced. Xcp_DaqListClearEntries takes the same
 * area around its own per-ODT entry-reset loop, so the exclusion is mutual: a concurrent clear
 * yields, at worst, a stale address paired with the copy's own consistent length, or a zero
 * length -- never a dereference of address 0.
 * @note The local buffer is sized XCP_MAX_DTO, not maxOdtEntries -- deliberately: maxOdtEntries is
 * how many entry *slots* the ODT was configured with, which bounds nothing about how many can be
 * simultaneously non-empty. That bound comes from WRITE_DAQ (source/Xcp_Daq.c), which refuses a
 * write once the entries of one ODT would sum past odtEntrySizeDaq = XCP_MAX_DTO -
 * <identification field size> bytes, and every entry that contributes at all contributes at least
 * one byte. So at most XCP_MAX_DTO - 1 entries can ever be simultaneously non-empty, regardless of
 * maxOdtEntries or which slots they occupy. The scan below therefore walks every configured slot
 * (cheap: one length comparison, no per-slot storage) but copies only the non-empty ones,
 * compacted, and stops copying -- defensively; the bound above says this cannot trigger -- once
 * XCP_MAX_DTO copies have been made. This is what keeps a function that may run in an interrupt
 * from putting up to 255 (a uint8 count) full entries, or roughly 1 KB, on its stack.
 * @note The exclusive area is modelled in the CFFI harness (test/conftest.py): the
 * SchM_Enter_Xcp_DtoQueue/SchM_Exit_Xcp_DtoQueue mocks track a boolean "held" state via a side
 * effect, and an autouse fixture asserts, after every test in the suite, that the area was never
 * double-entered, never exited without a matching enter, and never left held at teardown (a
 * leaked lock). test/daq_concurrency_test.py::test_clear_daq_list_takes_the_exclusive_area
 * asserts Xcp_DaqListClearEntries enters the area at all; its
 * ::test_a_clear_arriving_between_two_entry_reads_does_not_corrupt_the_frame exercises DD14's
 * guarantee directly by injecting a CLEAR_DAQ_LIST from inside the memory-read callback while
 * this function's second (read) loop is already running, and checking that the resulting frame
 * is unaffected. See the Task 15 report, "Fix round 1" and "Fix round 2", for what was verified
 * and how.
 */
static Std_ReturnType Xcp_DaqSampleOdt(Xcp_DtoFrameType *pFrame, uint16 daqListNumber, uint8 odtNumber)
{
    Xcp_OdtEntryType entry[XCP_MAX_DTO];
    uint8 copied = 0x00u;
    uint8_least idx;
    uint8 offset;
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    Std_ReturnType result = E_NOT_OK;

    SchM_Enter_Xcp_DtoQueue();

    for (idx = 0x00u; idx < Xcp_Ptr->config->daqList[daqListNumber].maxOdtEntries; idx++)
    {
        const Xcp_OdtEntryType *p_live =
                &Xcp_Ptr->config->daqList[daqListNumber].odt[odtNumber].odtEntry[idx];

        if ((p_live->length != 0x00u) && (copied < XCP_MAX_DTO))
        {
            /* Field by field, not `entry[copied] = *p_live;`: .number is declared const, and
             * .number is never read back below -- ascending scan order already IS ascending ODT
             * entry order, which is the frame layout 1.1/1.1.4.1 wants. */
            entry[copied].address = p_live->address;
            entry[copied].bitOffset = p_live->bitOffset;
            entry[copied].addressExtension = p_live->addressExtension;
            entry[copied].length = p_live->length;
            copied++;
        }
    }

    SchM_Exit_Xcp_DtoQueue();

    offset = Xcp_DaqWriteIdentificationField(pFrame, daqListNumber, odtNumber);

    for (idx = 0x00u; idx < copied; idx++)
    {
        uint8_least element;

        /* 1.1/1.6.4.1.1.2, DD8: BIT_OFFSET is validated and stored by WRITE_DAQ but does not
         * change what is sampled here. For DIRECTION = DAQ the master applies BIT_MASK to what it
         * receives; the slave transmits the element unmodified, so entry[idx].bitOffset is not
         * read here. */
        for (element = 0x00u; element < (uint8_least)(entry[idx].length / element_size); element++)
        {
            Xcp_ReadSlaveMemoryTable[Xcp_Ptr->general->addressGranularity](
                    (void *)&((uint8 *)entry[idx].address)[element * element_size],
                    entry[idx].addressExtension,
                    &pFrame->data[offset]);

            offset = (uint8)(offset + element_size);
        }

        result = E_OK;
    }

    pFrame->length = offset;
    pFrame->txPduId = Xcp_Ptr->config->daqList[daqListNumber].dto[0x00u].dto2PduMapping.txPdu.id;

    return result;
}

/**
 * @brief Appends one assembled frame to the ring.
 * @retval E_NOT_OK the ring was full; the frame was dropped and never written.
 * @details Caller-side locking: the exclusive area is taken here, not by the caller, so a
 * sampling loop holds it once per frame rather than for its whole duration. count rather than a
 * read/write gap distinguishes a full ring from an empty one without wasting a slot.
 * @note A full ring simply drops the frame; Xcp_TriggerEventChannel is the caller, and it is what
 * counts the drop across the whole trigger and raises EV_DAQ_OVERLOAD, at most once, once the
 * sampling loop that calls this is done.
 */
static Std_ReturnType Xcp_DaqQueuePush(const Xcp_DtoFrameType *pFrame)
{
    Xcp_DtoQueueType *p_queue = Xcp_Rt[Xcp_Ptr->xcpRtRef].dtoQueue;
    Std_ReturnType result;

    SchM_Enter_Xcp_DtoQueue();

    if (p_queue->count >= p_queue->depth)
    {
        result = E_NOT_OK;
    }
    else
    {
        p_queue->frame[p_queue->write] = *pFrame;
        p_queue->write = (uint8)((uint8)(p_queue->write + 0x01u) % p_queue->depth);
        p_queue->count++;
        result = E_OK;
    }

    SchM_Exit_Xcp_DtoQueue();

    return result;
}

/*------------------------------------------------------------------------------------------------*/
/* global function definitions.                                                                   */
/*------------------------------------------------------------------------------------------------*/

Std_ReturnType Xcp_DaqQueuePeek(PduIdType *pTxPduId, PduInfoType **ppPduInfo)
{
    Xcp_DtoQueueType *p_queue = Xcp_Rt[Xcp_Ptr->xcpRtRef].dtoQueue;
    Std_ReturnType result = E_NOT_OK;

    /* Called with the exclusive area already held, from Xcp_TransmitOneFrame's selection
     * (Xcp.c). */
    if (p_queue->count != 0x00u)
    {
        Xcp_DaqTxPduInfo.SduDataPtr = &p_queue->frame[p_queue->read].data[0x00u];
        Xcp_DaqTxPduInfo.SduLength = p_queue->frame[p_queue->read].length;
        Xcp_DaqTxPduInfo.MetaDataPtr = NULL_PTR;

        *pTxPduId = p_queue->frame[p_queue->read].txPduId;
        *ppPduInfo = &Xcp_DaqTxPduInfo;

        result = E_OK;
    }

    return result;
}

void Xcp_DaqQueuePop(void)
{
    Xcp_DtoQueueType *p_queue = Xcp_Rt[Xcp_Ptr->xcpRtRef].dtoQueue;

    /* Called with the exclusive area already held, from Xcp_CanIfTxConfirmation (Xcp.c). */
    if (p_queue->count != 0x00u)
    {
        p_queue->read = (uint8)((uint8)(p_queue->read + 0x01u) % p_queue->depth);
        p_queue->count--;
    }
}

void Xcp_TriggerEventChannel(uint16 eventChannelNumber)
{
    if (Xcp_State != XCP_INITIALIZED)
    {
        Xcp_ReportError(0x00u, XCP_TRIGGER_EVENT_CHANNEL_API_ID, XCP_E_UNINIT);
    }
    else if (eventChannelNumber >= Xcp_Ptr->general->maxEventChannel)
    {
        Xcp_ReportError(0x00u, XCP_TRIGGER_EVENT_CHANNEL_API_ID, XCP_E_INVALID_EVENT_CHANNEL);
    }
    else
    {
        uint16 daq_idx;

        /* Accumulates across every DAQ list and every ODT this one trigger samples, not reset
         * per list or per ODT: 1.1/1.8.6 requires the slave to "take care not to overload
         * another cycle with this additional packet", so at most one EV_DAQ_OVERLOAD is raised
         * for the whole trigger, however many individual pushes failed within it. */
        boolean overloaded = FALSE;

        /* DD11: the authoritative binding of a DAQ list to an event channel is the one
         * SET_DAQ_LIST_MODE wrote at runtime (Xcp_Rt[...].daqList[...].eventChannelNumber), not
         * the configured triggeredDaqListRef, so the lists are scanned rather than the channel's
         * reference list walked. */
        for (daq_idx = 0x0000u; daq_idx < Xcp_Ptr->general->daqCount; daq_idx++)
        {
            Xcp_DaqListRtType *p_rt = &Xcp_Rt[Xcp_Ptr->xcpRtRef].daqList[daq_idx];

            if (((p_rt->mode & XCP_DAQ_LIST_MODE_RUNNING) != 0x00u) &&
                (p_rt->eventChannelNumber == eventChannelNumber))
            {
                p_rt->prescalerCounter++;

                /* 1.1/1.6.4.1.1.3: "Without reduction, the prescaler value must equal 1." */
                if (p_rt->prescalerCounter >= p_rt->prescaler)
                {
                    uint8_least odt_idx;

                    p_rt->prescalerCounter = 0x00u;

                    for (odt_idx = 0x00u; odt_idx < Xcp_Ptr->config->daqList[daq_idx].maxOdt; odt_idx++)
                    {
                        Xcp_DtoFrameType frame;

                        if (Xcp_DaqSampleOdt(&frame, daq_idx, (uint8)odt_idx) == E_OK)
                        {
                            if (Xcp_DaqQueuePush(&frame) != E_OK)
                            {
                                overloaded = TRUE;
                            }
                        }
                    }
                }
            }
        }

        /* XCP part 2 - Protocol Layer Specification 1.1/1.8.6
         * One event covers the whole trigger however many frames were lost: the slave "must take
         * care not to overload another cycle with this additional packet". */
        if ((overloaded == TRUE) && (Xcp_Ptr->general->overloadEvent == TRUE))
        {
            if (Xcp_EventQueuePush(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue,
                                   XCP_PID_EVENT,
                                   XCP_EVENT_DAQ_OVERLOAD,
                                   NULL_PTR,
                                   0x00000000u) != E_OK)
            {
                Xcp_ReportError(0x00u, XCP_TRIGGER_EVENT_CHANNEL_API_ID, XCP_E_EVENT_QUEUE_FULL);
            }
        }

        Xcp_StartNextTransmission();
    }
}
