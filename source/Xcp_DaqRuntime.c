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

    /* 1.1/1.1.2.1: with PID_OFF the packet carries no Identification Field at all, so the payload
     * -- or the timestamp, when both are on -- starts at offset 0. SET_DAQ_LIST_MODE has already
     * refused the bit for anything but an ABSOLUTE single-ODT list, so this cannot produce a frame
     * the master is unable to identify. Xcp_DaqListRt (source/Xcp_Daq.c) has file-local linkage
     * there, so the stored mode is read directly off Xcp_Rt here instead, the same way
     * Xcp_DaqSampleOdt's own timestamp check further up this file already does. */
    if ((Xcp_Rt[Xcp_Ptr->xcpRtRef].daqList[daqListNumber].mode & XCP_DAQ_LIST_MODE_PID_OFF) != 0x00u)
    {
        return 0x00u;
    }

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
 * @brief Finds the allocated DAQ list that receives on rxPduId and has PID_OFF in its stored mode.
 * @retval TRUE *pDaqListNumber names that list; FALSE no allocated list satisfies both conditions,
 * and *pDaqListNumber is not written.
 * @details 1.1/1.1.2.1: once the Identification Field is turned off, "the unambiguous
 * identification has to be done on the level of the Transport Layer" -- and the only handle this
 * module's transport layer offers is the PDU the frame arrived on. So under PID_OFF the receiving
 * PduId names the DAQ list, in place of a field that is not on the wire at all.
 *
 * At most one list can match, which is why the scan stops at the first: Xcp_DTOCmdDaqSetDaqListMode
 * (source/Xcp_Daq.c) grants PID_OFF only to a list whose PDU no other list shares, and rejects it
 * otherwise -- that is the whole purpose of Xcp_DaqListTxPduIsExclusive there. Uniqueness is
 * therefore established when the bit is set, not re-derived here.
 *
 * dto[0x00u], the same element Xcp_DaqSampleOdt below and Xcp_DaqListTxPduIsExclusive both read:
 * the exclusivity PID_OFF was granted on was decided on that element, so identification has to be
 * read off the same one or the two could disagree. rxPdu rather than txPdu of that union -- the
 * same bytes either way, since Xcp_RxPduType and Xcp_TxPduType have identical layouts, but this is
 * the receive side and Xcp_CanIfRxIndication (Xcp.c) matches on the same member.
 * @note The bound is Xcp_Internal.allocated_daq_count, which is what Xcp_DaqListIsValid
 * (source/Xcp_Daq.c, file-local there) means by a list existing: equal to daqCount under a STATIC
 * configuration, and raised from zero by ALLOC_DAQ under a DYNAMIC one.
 */
static boolean Xcp_DaqPidOffListForRxPdu(PduIdType rxPduId, uint16 *pDaqListNumber)
{
    boolean found = FALSE;
    uint16 idx;

    for (idx = 0x0000u; (idx < Xcp_Internal.allocated_daq_count) && (found == FALSE); idx++)
    {
        if (((Xcp_Rt[Xcp_Ptr->xcpRtRef].daqList[idx].mode & XCP_DAQ_LIST_MODE_PID_OFF) != 0x00u) &&
            ((PduIdType)Xcp_Ptr->config->daqList[idx].dto[0x00u].dto2PduMapping.rxPdu.id == rxPduId))
        {
            *pDaqListNumber = idx;
            found = TRUE;
        }
    }

    return found;
}

/**
 * @brief Reverses absolute_ODT_NUMBER = FIRST_PID(list) + relative ODT_NUMBER.
 * @retval TRUE pid falls in some allocated list's range; *pDaqListNumber and *pOdtNumber name it.
 * @retval FALSE no allocated list covers pid; neither output is written.
 * @details 1.1/1.6.4.1.1.4. The ABSOLUTE identification field is the one form that does not carry
 * the DAQ list number, so it has to be recovered -- the ranges [firstPid, firstPid + maxOdt) are
 * disjoint and contiguous by construction (the generator assigns firstPid as a running sum of the
 * preceding lists' maxOdt), so at most one list matches and a linear scan finds it.
 *
 * A 256-entry reverse table would answer in constant time but would have to be rebuilt on every
 * ALLOC_ODT and every direction change; the scan is bounded by allocated_daq_count, itself capped
 * at 255, against a frame rate the bus already bounds.
 *
 * A list with maxOdt 0x00u -- which config/xcp.schema.json permits -- yields an empty range and
 * can never match, so it needs no case of its own.
 */
static boolean Xcp_DaqListForAbsolutePid(uint8 pid, uint16 *pDaqListNumber, uint8 *pOdtNumber)
{
    boolean found = FALSE;
    uint16 idx;

    for (idx = 0x0000u; (idx < Xcp_Internal.allocated_daq_count) && (found == FALSE); idx++)
    {
        const uint16 first_pid = (uint16)Xcp_Ptr->config->daqList[idx].firstPid;
        const uint16 end_pid = (uint16)(first_pid + (uint16)Xcp_Ptr->config->daqList[idx].maxOdt);

        if (((uint16)pid >= first_pid) && ((uint16)pid < end_pid))
        {
            *pDaqListNumber = idx;
            *pOdtNumber = (uint8)((uint16)pid - first_pid);
            found = TRUE;
        }
    }

    return found;
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
 * maxOdtEntries or which slots they occupy. The scan below therefore walks every slot the ODT
 * holds -- its entryCount, which is every configured slot under STATIC and exactly what
 * ALLOC_ODT_ENTRY handed out under DYNAMIC
 * (cheap: one length comparison, no per-slot storage) -- but copies only the non-empty ones,
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
 * @note `timestamp` is sampled once per cycle by the caller (Xcp_TriggerEventChannel), not read
 * here -- this function only places the already-sampled value into ODT 0, per 1.1/1.1.2.2.
 */
static Std_ReturnType Xcp_DaqSampleOdt(Xcp_DtoFrameType *pFrame, uint16 daqListNumber, uint8 odtNumber,
                                       uint32 timestamp)
{
    Xcp_OdtEntryType entry[XCP_MAX_DTO];
    uint8 copied = 0x00u;
    uint8_least idx;
    uint8 offset;
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    Std_ReturnType result = E_NOT_OK;

    SchM_Enter_Xcp_DtoQueue();

    for (idx = 0x00u; idx < Xcp_Ptr->config->daqList[daqListNumber].odt[odtNumber].entryCount; idx++)
    {
        const Xcp_OdtEntryType *p_live =
                &Xcp_Ptr->config->daqList[daqListNumber].odt[odtNumber].odtEntry[idx];

        if ((p_live->length != 0x00u) && (copied < XCP_MAX_DTO))
        {
            /* Field by field, not `entry[copied] = *p_live;`: .number is declared const, and
             * .number is never read back below -- ascending scan order already IS ascending ODT
             * entry order, which is the frame layout 1.1/1.1.4.1 wants. */
            entry[copied].address = p_live->address;
            entry[copied].addressExtension = p_live->addressExtension;
            entry[copied].length = p_live->length;
            copied++;
        }
    }

    SchM_Exit_Xcp_DtoQueue();

    offset = Xcp_DaqWriteIdentificationField(pFrame, daqListNumber, odtNumber);

#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)
    /* XCP part 2 - Protocol Layer Specification 1.1/1.1.2.2, Diagram 10: the Timestamp Field sits
     * directly after the Identification Field, in the first ODT of the cycle only. Xcp_DaqListRt
     * (source/Xcp_Daq.c) has file-local linkage there, so the stored mode is read directly off
     * Xcp_Rt here instead -- the same way Xcp_TriggerEventChannel's own p_rt already does further
     * down in this file. */
    if ((odtNumber == 0x00u) &&
        ((Xcp_Rt[Xcp_Ptr->xcpRtRef].daqList[daqListNumber].mode & XCP_DAQ_LIST_MODE_TIMESTAMP) != 0x00u))
    {
        /* Xcp_TimestampWireSize(timestampType), not XCP_DAQ_TIMESTAMP_SIZE: the macro is the
         * maximum across every configuration in the build, right for compile-time sizing and #if
         * gating, wrong as the byte count of the configuration actually running. Tasks 4 and 5
         * apply the same rule to their ODT-0 budget arithmetic (source/Xcp_Daq.c), so all three
         * read as the same rule.
         *
         * Computed once, into timestamp_size, and switched on directly below -- not
         * Xcp_Ptr->general->timestampType switched on a second, independent time -- because two
         * switches over the same enum, maintained in two files, can silently drift at whichever
         * arm nobody is looking at (an earlier version of this switch did exactly that: its
         * default wrote 4 bytes for FOUR_BYTE/default while Xcp_TimestampWireSize's own default
         * returns 0 for NO_TIME_STAMP/default). One switch producing the exact value the offset
         * advance also uses cannot disagree with itself. */
        const uint8 timestamp_size = Xcp_TimestampWireSize(Xcp_Ptr->general->timestampType);

        switch (timestamp_size)
        {
            case 0x01u:
                pFrame->data[offset] = (uint8)timestamp;
                break;
            case 0x02u:
                Xcp_CopyFromU16WithOrder((uint16)timestamp, &pFrame->data[offset],
                                         Xcp_Ptr->general->byteOrder);
                break;
            case 0x04u:
                Xcp_CopyFromU32WithOrder(timestamp, &pFrame->data[offset],
                                         Xcp_Ptr->general->byteOrder);
                break;
            default:
                /* timestamp_size 0x00u: NO_TIME_STAMP, or any future timestampType this helper
                 * does not map -- writes and advances nothing, matching Xcp_TimestampWireSize's
                 * own 0. Unreachable today because Xcp_DTOCmdDaqSetDaqListMode already refuses to
                 * enable TIMESTAMP without a clock (source/Xcp_Daq.c); kept so this switch, like
                 * the helper's own, is total rather than assuming its caller's guard. */
                break;
        }

        offset = (uint8)(offset + timestamp_size);
    }
#else
    (void)timestamp;
#endif /* #if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON) */

    for (idx = 0x00u; idx < copied; idx++)
    {
        uint8_least element;

        /* 1.1/1.6.4.1.1.2, DD8: BIT_OFFSET is validated and stored by WRITE_DAQ but does not
         * change what is sampled here. For DIRECTION = DAQ the master applies BIT_MASK to what it
         * receives; the slave transmits the element unmodified, so entry[] above does not copy
         * bitOffset -- there is nothing here that would ever read it. */
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

Std_ReturnType Xcp_DaqReadIdentificationField(const PduInfoType *pPduInfo,
                                              PduIdType rxPduId,
                                              uint16 *pDaqListNumber,
                                              uint8 *pOdtNumber,
                                              uint8 *pOffset)
{
    Std_ReturnType result = E_NOT_OK;
    uint16 daq_list_number = 0x0000u;
    uint8 odt_number = 0x00u;
    uint8 offset = 0x00u;
    boolean decoded;

    /* PID_OFF first, and not as an arm of the switch below: it is a property of one DAQ list, not
     * of the build's identificationFieldType, and it removes the very field the switch would read.
     * There is no ordering hazard in asking about it before the field is decoded -- a list holding
     * the bit owns its PDU exclusively (Xcp_DaqPidOffListForRxPdu above), so a frame arriving on
     * some other list's PDU matches nothing here and falls through to the field. */
    decoded = Xcp_DaqPidOffListForRxPdu(rxPduId, &daq_list_number);

    if (decoded == TRUE)
    {
        /* 1.1/1.1.2.1: no Identification Field on the wire, so the payload -- or the timestamp,
         * when both are on -- starts at byte 0. SET_DAQ_LIST_MODE grants PID_OFF only to a
         * single-ODT list, so the ODT is 0 and there is nothing to read. Exactly what
         * Xcp_DaqWriteIdentificationField returns 0x00u for on the transmit side. */
        odt_number = 0x00u;
        offset = 0x00u;
    }
    else
    {
        /* The arms below are Xcp_DaqWriteIdentificationField's, in its order and reading back
         * precisely what each of them writes. That function is the authority on these layouts; a
         * disagreement between the two is a defect here, not there. Each arm checks SduLength
         * before indexing: the field it is about to read is as long as the configuration says, not
         * as long as the master actually sent. */
        switch (Xcp_Ptr->general->identificationFieldType)
        {
            case RELATIVE_BYTE:
            {
                if (pPduInfo->SduLength >= 0x02u)
                {
                    odt_number = pPduInfo->SduDataPtr[0x00u];
                    daq_list_number = (uint16)pPduInfo->SduDataPtr[0x01u];
                    offset = 0x02u;
                    decoded = TRUE;
                }

                break;
            }
            case RELATIVE_WORD:
            {
                if (pPduInfo->SduLength >= 0x03u)
                {
                    odt_number = pPduInfo->SduDataPtr[0x00u];
                    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x01u], &daq_list_number,
                                           Xcp_Ptr->general->byteOrder);
                    offset = 0x03u;
                    decoded = TRUE;
                }

                break;
            }
            case RELATIVE_WORD_ALIGNED:
            {
                if (pPduInfo->SduLength >= 0x04u)
                {
                    odt_number = pPduInfo->SduDataPtr[0x00u];
                    /* Byte 1 is the FILL byte, skipped: 1.1/1.1.2.1 gives it no defined value, so
                     * nothing about it can be checked. */
                    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &daq_list_number,
                                           Xcp_Ptr->general->byteOrder);
                    offset = 0x04u;
                    decoded = TRUE;
                }

                break;
            }
            default:
            {
                /* ABSOLUTE. The one form carrying no DAQ list number, so the list is recovered
                 * from the PID's own range rather than read. */
                if (pPduInfo->SduLength >= 0x01u)
                {
                    decoded = Xcp_DaqListForAbsolutePid(pPduInfo->SduDataPtr[0x00u],
                                                        &daq_list_number, &odt_number);
                    offset = 0x01u;
                }

                break;
            }
        }
    }

    /* Both bounds, for every form: the ABSOLUTE scan establishes them on the way in, but the four
     * other forms take the master's word for the list number, the ODT number, or both, and the
     * caller indexes daqList[] and its odt[] with exactly these. */
    if ((decoded == TRUE) &&
        (daq_list_number < Xcp_Internal.allocated_daq_count) &&
        (odt_number < Xcp_Ptr->config->daqList[daq_list_number].maxOdt))
    {
#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)
        /* DD44. 1.1/1.1.2.2: "The TIMESTAMP flag can be used as well for DIRECTION = DAQ as for
         * DIRECTION = STIM", and for stimulation the master "first receives a time stamped
         * DTO(DAQ) from the slave and then echoes this current value of the slave device's clock
         * in the DTO Packet for the first ODT of the DAQ cycle". So the field sits directly after
         * the Identification Field, on ODT 0 alone -- Diagram 10's shape, in the other direction
         * -- and this mirrors Xcp_DaqSampleOdt's own block above condition for condition.
         *
         * Skipped, not read into anything: the value is the slave's own clock coming back, and
         * 1.1.2.2 offers the correlation it enables ("gives the slave the possibility to check
         * whether DTO(DAQ) and CTO(STIM) belong functionally together") as a possibility, not a
         * requirement. Acting on it needs a record of which clock value went out with which DAQ
         * cycle, which is its own mechanism; the design document records it as a follow-up. This
         * interface has nowhere to put the value, so reading it would only be a discarded load.
         *
         * Xcp_TimestampWireSize(timestampType), not XCP_DAQ_TIMESTAMP_SIZE, for the reason
         * Xcp_DaqSampleOdt states at length: the macro is the maximum across every configuration
         * in the build, right for compile-time sizing and #if gating, wrong as the byte count of
         * the configuration actually running. It is also the size the specification obliges the
         * master to use -- "The master has to use the same Type of Timestamp Field when
         * transferring STIM Packets to the slave" as the slave published through
         * GET_DAQ_RESOLUTION_INFO -- so there is nothing here to negotiate or infer from the
         * frame. */
        if ((odt_number == 0x00u) &&
            ((Xcp_Rt[Xcp_Ptr->xcpRtRef].daqList[daq_list_number].mode &
              XCP_DAQ_LIST_MODE_TIMESTAMP) != 0x00u))
        {
            offset = (uint8)(offset + Xcp_TimestampWireSize(Xcp_Ptr->general->timestampType));
        }
#endif /* #if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON) */

        /* The frame has to be at least as long as the fields that precede its payload, timestamp
         * included -- the per-arm checks above cover only the identification field, which is all
         * they had decoded at that point. Equality is accepted: a frame that is exactly its own
         * header carries an empty payload, which is a well-formed frame that DD39's payload-length
         * check (the caller's) is what rejects. This also keeps SduLength - *pOffset defined for
         * that caller, which is unsigned and would otherwise wrap. */
        if ((uint32)pPduInfo->SduLength >= (uint32)offset)
        {
            *pDaqListNumber = daq_list_number;
            *pOdtNumber = odt_number;
            *pOffset = offset;

            result = E_OK;
        }
    }

    return result;
}

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
                    uint32 timestamp = 0x00000000u;

                    p_rt->prescalerCounter = 0x00u;

#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)
                    /* 1.1/1.1.2.2 Diagram 10: one clock reading per DAQ cycle, transmitted in the
                     * first ODT. Reading per ODT would give one cycle's ODTs differing timestamps
                     * and would call integrator code once per ODT instead of once per cycle. */
                    if ((p_rt->mode & XCP_DAQ_LIST_MODE_TIMESTAMP) != 0x00u)
                    {
                        timestamp = Xcp_GetDaqTimestamp();
                    }
#endif /* #if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON) */

                    for (odt_idx = 0x00u; odt_idx < Xcp_Ptr->config->daqList[daq_idx].maxOdt; odt_idx++)
                    {
                        Xcp_DtoFrameType frame;

                        if (Xcp_DaqSampleOdt(&frame, daq_idx, (uint8)odt_idx, timestamp) == E_OK)
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
            Std_ReturnType push_result;

            /* The event queue now has two producers that can each run in a different context --
             * Xcp_MainFunction (EV_STORE_CAL) and this trigger (EV_DAQ_OVERLOAD, documented to be
             * callable from an interrupt) -- while Xcp_TransmitOneFrame, the one consumer, reads
             * read/write under this same area. Without it, a trigger preempting a push already in
             * progress could compute the same pre-update write index, and both writers would then
             * target the same slot: one event silently lost, the surviving entry a mixture of
             * both writers' fields. Xcp_DaqQueuePush, three lines above, takes the same area for
             * the identical reason. Xcp_ReportError (which calls Det_ReportError) stays outside: it is
             * an external call, and the area must stay short. */
            SchM_Enter_Xcp_DtoQueue();
            push_result = Xcp_EventQueuePush(Xcp_Rt[Xcp_Ptr->xcpRtRef].eventQueue,
                                             XCP_PID_EVENT,
                                             XCP_EVENT_DAQ_OVERLOAD,
                                             NULL_PTR,
                                             0x00000000u);
            SchM_Exit_Xcp_DtoQueue();

            if (push_result != E_OK)
            {
                Xcp_ReportError(0x00u, XCP_TRIGGER_EVENT_CHANNEL_API_ID, XCP_E_EVENT_QUEUE_FULL);
            }
        }

        Xcp_StartNextTransmission();
    }
}
