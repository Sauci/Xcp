/**
 * @file Xcp_Daq.c
 * @author
 * @date
 *
 * @defgroup XCP_DAQ_C DATA ACQUISITION AND STIMULATION command group implementation
 * @ingroup XCP
 */

#include "Xcp_Internal.h"

#include "Xcp_Rt.h"

/*------------------------------------------------------------------------------------------------*/
/* local function definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

static boolean Xcp_DaqListIsValid(uint16 daqListNumber)
{
    return (boolean)((daqListNumber < Xcp_Ptr->general->daqCount) ? TRUE : FALSE);
}

static Xcp_DaqListRtType *Xcp_DaqListRt(uint16 daqListNumber)
{
    return &Xcp_Rt[Xcp_Ptr->xcpRtRef].daqList[daqListNumber];
}

/**
 * @brief resets every ODT entry of one DAQ list to its power-up state.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.1.1: "For a configurable DAQ
 * list, all ODT entries will be reset to address=0, extension=0 and size=0 (if valid :
 * bit_offset = 0xFF)." Bounded by daqListNumber's own maxOdt/maxOdtEntries, not any other list's,
 * so clearing one list never touches another's entries.
 * @note Despite living beside this file's other file-local helpers, this one has external
 * linkage and a declaration in Xcp_Internal.h: Xcp_Init (source/Xcp.c) calls it too. The
 * generated ODT entry arrays are module-level mutable statics (script/source_cfg.c.jinja2 emits
 * them `static`), and nothing used to reset them on (re-)initialisation -- so a re-initialised
 * module, and, in the test harness, a test sharing a compiled configuration with an earlier one,
 * would silently inherit a previous session's DAQ configuration.
 * @note DD14: Xcp_DaqSampleOdt (source/Xcp_DaqRuntime.c) copies one ODT's entries out from under
 * this same exclusive area before reading memory through them, because CLEAR_DAQ_LIST may run in
 * CanIf's receive context while the sampler walks the same array from a task or an interrupt --
 * including the sampler's own interrupt preempting a clear already in progress at task level, the
 * direction a lock taken only on the read side cannot help with. The inner loop below is wrapped
 * per ODT, not once for the whole nest, so each critical section is bounded by maxOdtEntries field
 * writes rather than maxOdt * maxOdtEntries: neither Xcp_Init (source/Xcp.c) nor
 * Xcp_DTOCmdDaqClearDaqList, this function's only callers, hold the area themselves, so nesting
 * across ODTs is not a concern either way.
 */
void Xcp_DaqListClearEntries(uint16 daqListNumber)
{
    uint8_least odt_idx;
    uint8_least entry_idx;

    for (odt_idx = 0x00u; odt_idx < Xcp_Ptr->config->daqList[daqListNumber].maxOdt; odt_idx++)
    {
        SchM_Enter_Xcp_DtoQueue();

        for (entry_idx = 0x00u;
             entry_idx < Xcp_Ptr->config->daqList[daqListNumber].maxOdtEntries;
             entry_idx++)
        {
            Xcp_OdtEntryType *p_entry =
                    &Xcp_Ptr->config->daqList[daqListNumber].odt[odt_idx].odtEntry[entry_idx];

            p_entry->address = NULL_PTR;
            p_entry->addressExtension = 0x00u;
            p_entry->length = 0x00u;
            p_entry->bitOffset = XCP_ODT_ENTRY_BIT_OFFSET_NONE;
        }

        SchM_Exit_Xcp_DtoQueue();
    }
}

/**
 * @brief TRUE when no other DAQ list transmits through this list's TX PDU.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.1.2.1 makes the transport layer
 * responsible for identifying a DTO once PID_OFF removes the identification field, and gives the
 * CAN example: "separate CAN-Ids for each DAQ list". This module gives each DAQ list exactly one
 * TX PDU, which is not the same thing as giving each list a *distinct* one -- nothing forbids two
 * lists naming the same XcpDto2PduMapping, and config/xcp.json ships exactly that, mapping both of
 * its lists to XCP_PDU_ID_TRANSMIT. So the distinctness has to be checked, not assumed.
 *
 * It is checked here rather than at generation time because the mapping is a macro name in the
 * configuration (script/source_cfg.c.jinja2 emits `{{daq.pdu_mapping}}` verbatim); the numbers two
 * names resolve to are the preprocessor's answer, not the generator's, so only the built
 * configuration knows whether two lists collide.
 */
static boolean Xcp_DaqListTxPduIsExclusive(uint16 daqListNumber)
{
    const uint16 tx_pdu_id = Xcp_Ptr->config->daqList[daqListNumber].dto[0x00u].dto2PduMapping.txPdu.id;
    boolean exclusive = TRUE;
    uint16 idx;

    for (idx = 0x0000u; idx < Xcp_Ptr->general->daqCount; idx++)
    {
        if ((idx != daqListNumber) &&
            (Xcp_Ptr->config->daqList[idx].dto[0x00u].dto2PduMapping.txPdu.id == tx_pdu_id))
        {
            exclusive = FALSE;
        }
    }

    return exclusive;
}

/**
 * @brief bytes already claimed by the written entries of one ODT.
 * @details An ODT becomes one DTO frame, so the entries it holds have to fit in what the frame
 * leaves after the identification field. Entries not yet written have length 0 and contribute
 * nothing.
 * @note odtNumber must be below the list's maxOdt: the ODT array is generated with exactly maxOdt
 * elements, and a configuration may set max_odt to 0 (config/xcp.schema.json's "minimum"), which
 * makes that array zero-length -- a GCC extension it accepts silently. Every caller is responsible
 * for the bound; Xcp_DTOCmdDaqSetDaqListMode's ODT-0 capacity check is the one that used to pass
 * 0x00u unconditionally.
 */
static uint8 Xcp_OdtUsedBytes(uint16 daqListNumber, uint8 odtNumber, uint8 excludedEntry)
{
    const Xcp_OdtType *p_odt = &Xcp_Ptr->config->daqList[daqListNumber].odt[odtNumber];
    uint8 used = 0x00u;
    uint8_least idx;

    for (idx = 0x00u; idx < Xcp_Ptr->config->daqList[daqListNumber].maxOdtEntries; idx++)
    {
        if (idx != (uint8_least)excludedEntry)
        {
            used = (uint8)(used + p_odt->odtEntry[idx].length);
        }
    }

    return used;
}

/**
 * @brief bytes one ODT's entries may occupy, after setting aside the timestamp's share of ODT 0.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.1.2.2, Diagram 10: the timestamp rides
 * in the first ODT of a cycle only, so it costs ODT 0 of a timestamped list
 * Xcp_TimestampWireSize(timestampType) bytes and costs every other ODT nothing. Reducing the
 * budget for every ODT would be a silent capacity regression for ODT 1..n.
 * @note Xcp_TimestampWireSize(Xcp_Ptr->general->timestampType), not XCP_DAQ_TIMESTAMP_SIZE: the
 * macro is the maximum across every configuration, right for compile-time sizing and #if gating,
 * wrong as the byte cost of the configuration actually running. Xcp_DTOCmdDaqSetDaqListMode
 * (below) applies the same rule when TIMESTAMP is enabled, so the two checks stay visibly the
 * same rule.
 */
static uint8 Xcp_DaqOdtEntryBudget(uint16 daqListNumber, uint8 odtNumber)
{
    uint8 budget = Xcp_Ptr->general->odtEntrySizeDaq;

    if ((odtNumber == 0x00u) &&
        ((Xcp_DaqListRt(daqListNumber)->mode & XCP_DAQ_LIST_MODE_TIMESTAMP) != 0x00u))
    {
        budget = (uint8)(budget - Xcp_TimestampWireSize(Xcp_Ptr->general->timestampType));
    }

    return budget;
}

/**
 * @brief Auto post-increments the DAQ pointer to the next entry within the current ODT.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.2: "The DAQ list pointer is
 * auto post incremented to the next ODT entry within one and the same ODT. After writing to the
 * last ODT entry of an ODT, the value of the DAQ pointer is undefined." This module represents
 * that undefined state as invalid (Xcp_Internal.daq_pointer.valid = FALSE) rather than wrapping
 * into the next ODT, so the pointer never silently crosses an ODT border: the next
 * Xcp_DaqApplyOdtEntry call fails the pointer-validity check instead of writing into the wrong ODT.
 */
static void Xcp_DaqPointerAdvance(void)
{
    if ((uint16)(Xcp_Internal.daq_pointer.odtEntryNumber + 0x01u) <
        (uint16)Xcp_Ptr->config->daqList[Xcp_Internal.daq_pointer.daqListNumber].maxOdtEntries)
    {
        Xcp_Internal.daq_pointer.odtEntryNumber++;
    }
    else
    {
        Xcp_Internal.daq_pointer.valid = FALSE;
    }
}

/**
 * @brief Applies one ODT entry at the current DAQ pointer and advances it.
 *
 * @details Shared by WRITE_DAQ and WRITE_DAQ_MULTIPLE. XCP part 2 - Protocol Layer Specification
 * 1.1/1.6.4.1.2.1 says WRITE_DAQ_MULTIPLE has "the same restrictions as the WRITE_DAQ command";
 * restating them in a second handler would make that true only on the day it was written. Sharing
 * one implementation makes it true by construction.
 *
 * @return 0x00u on success, otherwise the ASAM error code to report.
 */
static uint8 Xcp_DaqApplyOdtEntry(uint8 bitOffset, uint8 size, uint8 addressExtension, uint32 address)
{
    const uint8 granularity = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    uint8 error = 0x00u;
    Xcp_OdtEntryType *p_entry = NULL_PTR;

    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.2
     * The DAQ list pointer is left undefined past the last ODT entry of an ODT and the master is
     * responsible for repositioning it. Answering ERR_OUT_OF_RANGE tells it to do exactly that:
     * the error's prescribed action in 1.7.3.2.4 is "retry other parameter". */
    if (Xcp_Internal.daq_pointer.valid == FALSE)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if ((Xcp_DaqListRt(Xcp_Internal.daq_pointer.daqListNumber)->mode & XCP_DAQ_LIST_MODE_RUNNING) != 0x00u)
    {
        error = XCP_E_ASAM_DAQ_ACTIVE;
    }
    /* 1.1/1.6.4.1.1.2: "WRITE_DAQ is only possible for elements in configurable DAQ lists",
     * which are the lists numbered from MIN_DAQ upwards. */
    else if (Xcp_Internal.daq_pointer.daqListNumber < Xcp_Ptr->general->minDaq)
    {
        error = XCP_E_ASAM_WRITE_PROTECTED;
    }
    else if ((size == 0x00u) ||
             (size > Xcp_Ptr->general->odtEntrySizeDaq) ||
             ((size % granularity) != 0x00u))
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    /* 1.1/1.6.4.1.1.2: BIT_OFFSET is either 0x00..0x1F, naming a bit, or 0xFF, meaning the field
     * is to be ignored. Nothing else is defined. When it names a bit, "the Size of DAQ element
     * always has to be equal to the GRANULARITY_ODT_ENTRY_SIZE_x". */
    else if ((bitOffset != XCP_ODT_ENTRY_BIT_OFFSET_NONE) &&
             ((bitOffset > XCP_ODT_ENTRY_BIT_OFFSET_MAX) || (size != granularity)))
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    /* Xcp_DaqOdtEntryBudget's Xcp_DaqListRt dereference is safe here: this else if is reached only
     * once Xcp_Internal.daq_pointer.valid == FALSE (the first branch above) has been checked and
     * found false, which SET_DAQ_PTR (Xcp_DTOCmdDaqSetDaqPtr) only ever leaves TRUE after
     * validating daqListNumber itself -- the same gate the XCP_DAQ_LIST_MODE_RUNNING check two
     * branches above already relies on for the identical dereference. */
    else if ((uint16)((uint16)Xcp_OdtUsedBytes(Xcp_Internal.daq_pointer.daqListNumber,
                                               Xcp_Internal.daq_pointer.odtNumber,
                                               Xcp_Internal.daq_pointer.odtEntryNumber) + size) >
             (uint16)Xcp_DaqOdtEntryBudget(Xcp_Internal.daq_pointer.daqListNumber,
                                           Xcp_Internal.daq_pointer.odtNumber))
    {
        /* DD8: the entry is individually legal but the ODT it joins can no longer be carried in
         * one DTO -- now measured against the timestamp-adjusted budget of ODT 0
         * (Xcp_DaqOdtEntryBudget), not the raw MAX_ODT_ENTRY_SIZE_DAQ. 1.7.3.2.4 lists
         * ERR_DAQ_CONFIG for WRITE_DAQ and this is the configuration it describes. */
        error = XCP_E_ASAM_DAQ_CONFIG;
    }
    else
    {
        p_entry = &Xcp_Ptr->config->daqList[Xcp_Internal.daq_pointer.daqListNumber]
                       .odt[Xcp_Internal.daq_pointer.odtNumber]
                       .odtEntry[Xcp_Internal.daq_pointer.odtEntryNumber];

        /* No exclusive area around these four writes, unlike Xcp_DaqListClearEntries's writes
         * to this same odtEntry array (DD5/DD14 in the design doc). That is safe, not an
         * oversight: the DAQ_ACTIVE check a few lines above already refused this request unless
         * the addressed list is stopped, and Xcp_DaqSampleOdt (source/Xcp_DaqRuntime.c) only
         * ever walks a list's entries while it is RUNNING. So a list this function is about to
         * write is never being sampled, and a list being sampled is never reachable from here --
         * the two are mutually exclusive by construction (the RUNNING flag), not by a lock. This
         * reasoning breaks if WRITE_DAQ is ever allowed to touch a RUNNING list; do not remove
         * the DAQ_ACTIVE check above without adding an exclusive area here. */
        p_entry->address = (uint32 *)address;
        p_entry->addressExtension = addressExtension;
        p_entry->bitOffset = bitOffset;
        p_entry->length = size;

        Xcp_DaqPointerAdvance();
    }

    return error;
}

/**
 * @brief TRUE when at least one ODT entry of the list has been written.
 * @details A list with no entry has nothing to sample, so starting or selecting it would put the
 * slave into data transfer mode with no data to transfer.
 */
static boolean Xcp_DaqListIsConfigured(uint16 daqListNumber)
{
    boolean result = FALSE;
    uint8_least odt_idx;
    uint8_least entry_idx;

    for (odt_idx = 0x00u; odt_idx < Xcp_Ptr->config->daqList[daqListNumber].maxOdt; odt_idx++)
    {
        for (entry_idx = 0x00u;
             entry_idx < Xcp_Ptr->config->daqList[daqListNumber].maxOdtEntries;
             entry_idx++)
        {
            if (Xcp_Ptr->config->daqList[daqListNumber].odt[odt_idx].odtEntry[entry_idx].length != 0x00u)
            {
                result = TRUE;
            }
        }
    }

    return result;
}

/**
 * @brief Recomputes the DAQ_RUNNING bit of the session status.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.1.1.3: the bit means "at least one
 * DAQ list has been started and is in data transfer mode", so it is a property of every list
 * together and is recomputed whenever one of them starts or stops.
 */
static void Xcp_DaqSessionStatusUpdate(void)
{
    uint16 idx;
    boolean running = FALSE;

    for (idx = 0x0000u; idx < Xcp_Ptr->general->daqCount; idx++)
    {
        if ((Xcp_Rt[Xcp_Ptr->xcpRtRef].daqList[idx].mode & XCP_DAQ_LIST_MODE_RUNNING) != 0x00u)
        {
            running = TRUE;
        }
    }

    if (running == TRUE)
    {
        Xcp_Internal.session_status |= XCP_SESSION_STATUS_MASK_DAQ_RUNNING;
    }
    else
    {
        Xcp_Internal.session_status &= (uint8)(~XCP_SESSION_STATUS_MASK_DAQ_RUNNING);
    }
}

/*------------------------------------------------------------------------------------------------*/
/* command handler definitions.                                                                  */
/*------------------------------------------------------------------------------------------------*/

uint8 Xcp_DTODaqStimPacket(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqSetDaqPtr(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 odt_number = pPduInfo->SduDataPtr[0x04u];
    const uint8 odt_entry_number = pPduInfo->SduDataPtr[0x05u];
    uint16 daq_list_number;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &daq_list_number, Xcp_Ptr->general->byteOrder);

    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.1
     * "If the specified list is not available, ERR_OUT_OF_RANGE will be returned." ODT_NUMBER and
     * ODT_ENTRY_NUMBER are relative to that list, so both are bounded by its own configuration. */
    if (Xcp_DaqListIsValid(daq_list_number) == FALSE)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if ((Xcp_DaqListRt(daq_list_number)->mode & XCP_DAQ_LIST_MODE_RUNNING) != 0x00u)
    {
        error = XCP_E_ASAM_DAQ_ACTIVE;
    }
    else if (odt_number >= Xcp_Ptr->config->daqList[daq_list_number].maxOdt)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if (odt_entry_number >= Xcp_Ptr->config->daqList[daq_list_number].maxOdtEntries)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else
    {
        Xcp_Internal.daq_pointer.daqListNumber = daq_list_number;
        Xcp_Internal.daq_pointer.odtNumber = odt_number;
        Xcp_Internal.daq_pointer.odtEntryNumber = odt_entry_number;
        Xcp_Internal.daq_pointer.valid = TRUE;
    }

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdDaqWriteDaq(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 bit_offset = pPduInfo->SduDataPtr[0x01u];
    const uint8 size = pPduInfo->SduDataPtr[0x02u];
    const uint8 extension = pPduInfo->SduDataPtr[0x03u];
    uint32 address;
    uint8 error;

    *responseExpected = TRUE;

    Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &address, Xcp_Ptr->general->byteOrder);

    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.2. Xcp_DaqApplyOdtEntry carries the
     * full set of restrictions this command imposes -- pointer validity, DAQ_ACTIVE, write
     * protection, size/granularity, bit offset, ODT capacity, in that order -- and the pointer
     * advance that follows a successful write. See its own doc comment for why it is shared with
     * WRITE_DAQ_MULTIPLE rather than reimplemented there. */
    error = Xcp_DaqApplyOdtEntry(bit_offset, size, extension, address);

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

/**
 * @brief writes NoDAQ consecutive ODT entries starting at the current DAQ list pointer.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.1. Each element is 8 bytes:
 * BIT_OFFSET, size, a DWORD address, an address extension and a mandatory alignment dummy --
 * "The dummy byte at the end of each DAQ element must be used for alignment issues, even for the
 * last element." Confirmed against the PDF page images (pages 96-97: the Position column runs
 * 2, 3, 4, 8, 9 for element 1 and 10, 11, 12, 16, 17 for element 2, i.e. stride 8, and the n-th
 * element's dummy sits at n*8+1), not the OCR text dump, which garbles this table.
 *
 * Xcp_DaqApplyOdtEntry is applied once per element as the loop walks them, in request order, with
 * no rollback on failure: 1.6.4.1.2.1 says "it is not possible to detect which entry caused the
 * error. In that case the whole configuration is invalid", so a master that gets an error must
 * reconfigure the list regardless of how many elements this call already wrote.
 *
 * The "must not write over ODT borders" restriction needs no separate check here: the DAQ pointer
 * stops at an ODT border rather than wrapping into the next ODT (Xcp_DaqPointerAdvance), so an
 * element sequence that runs past the end of one ODT fails Xcp_DaqApplyOdtEntry's pointer-validity
 * check on its own, the same way a second WRITE_DAQ past the border does today.
 */
uint8 Xcp_DTOCmdDaqWriteDaqMultiple(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 count = pPduInfo->SduDataPtr[0x01u];
    uint8 error = 0x00u;
    uint8_least idx;

    *responseExpected = TRUE;

    /* count comes straight off the wire and nothing else bounds it, so it is bounded here first,
     * against a limit derived from MAX_CTO rather than by reconstructing the request length.
     * That ordering is the point: PduLengthType is integrator-supplied and AUTOSAR permits uint8
     * for a CAN-only stack, where the (PduLengthType)(0x02u + count * 0x08u) below wraps --
     * count = 32 gives 258, truncating to 2, which any 8-byte SDU satisfies, and the loop would
     * then read SduDataPtr[2..257] and feed 31 fabricated entries to Xcp_DaqApplyOdtEntry. The
     * comparison below is reached only for a count this build's MAX_CTO could actually carry, so
     * its arithmetic cannot overflow whatever PduLengthType is. MAX_CTO >= 10 whenever this
     * command is enabled -- script/source_cfg.c.jinja2 refuses to generate otherwise, per XCP
     * part 2 1.1/1.6.4.1.2.1 -- so this bound is never zero. ERR_OUT_OF_RANGE, whose prescribed
     * master action in 1.7.3.2.4 is "retry other parameter": fewer elements. */
    if ((uint16)count > (uint16)((Xcp_Ptr->general->maxCto - 0x02u) / 0x08u))
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if (pPduInfo->SduLength < (PduLengthType)(0x02u + ((PduLengthType)count * 0x08u)))
    {
        error = XCP_E_ASAM_CMD_SYNTAX;
    }
    else
    {
        for (idx = 0x00u; (idx < (uint8_least)count) && (error == 0x00u); idx++)
        {
            const uint8 *p_element = &pPduInfo->SduDataPtr[0x02u + (idx * 0x08u)];
            uint32 address;

            Xcp_CopyToU32WithOrder(&p_element[0x02u], &address, Xcp_Ptr->general->byteOrder);

            error = Xcp_DaqApplyOdtEntry(p_element[0x00u], p_element[0x01u], p_element[0x06u], address);
        }
    }

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

/**
 * @brief reads back the ODT entry currently named by the DAQ pointer, then advances it.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.2. Takes no request
 * parameters beyond the command byte itself -- the entry is selected entirely through
 * Xcp_Internal.daq_pointer, the same state WRITE_DAQ, WRITE_DAQ_MULTIPLE and SET_DAQ_PTR share.
 */
uint8 Xcp_DTOCmdDaqReadDaq(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8 error = 0x00u;

    (void)pPduInfo;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.2: the DAQ list pointer is left
     * undefined past the last ODT entry of an ODT and the master is responsible for
     * repositioning it. ERR_OUT_OF_RANGE's prescribed action in 1.7.3.2.4 is "retry other
     * parameter" (SP2a DD10) -- reposition with SET_DAQ_PTR. There is no
     * Xcp_DaqPointerIsValid()-style predicate in this file (Task 9); every call site, this one
     * included, reads Xcp_Internal.daq_pointer.valid directly, e.g. Xcp_DaqApplyOdtEntry above. */
    if (Xcp_Internal.daq_pointer.valid == FALSE)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }

    if (error == 0x00u)
    {
        const Xcp_OdtEntryType *p_entry =
                &Xcp_Ptr->config->daqList[Xcp_Internal.daq_pointer.daqListNumber]
                         .odt[Xcp_Internal.daq_pointer.odtNumber]
                         .odtEntry[Xcp_Internal.daq_pointer.odtEntryNumber];

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = p_entry->bitOffset;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = p_entry->length;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = p_entry->addressExtension;
        Xcp_CopyFromU32WithOrder((uint32)p_entry->address,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                 Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);

        /* 1.1/1.6.4.1.2.2: "The DAQ list pointer is auto post incremented within one and the
         * same ODT (See WRITE_DAQ)." Same helper, same advance, same stop (not wrap) at the ODT
         * border as WRITE_DAQ and WRITE_DAQ_MULTIPLE -- see Xcp_DaqPointerAdvance's own doc
         * comment above. */
        Xcp_DaqPointerAdvance();
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdDaqClearDaqList(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint16 daq_list_number;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &daq_list_number, Xcp_Ptr->general->byteOrder);

    if (Xcp_DaqListIsValid(daq_list_number) == FALSE)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.1.1
         * "For a configurable DAQ list, all ODT entries will be reset to address=0, extension=0
         * and size=0 (if valid : bit_offset = 0xFF)." */
        Xcp_DaqListClearEntries(daq_list_number);

        /* "For PREDEFINED and configurable DAQ lists, the running Data Transmission on this list
         * will be stopped and all DAQ list states are reset." The command is therefore legal
         * while the list runs -- see defect D10 against the error matrix. */
        Xcp_DaqListRt(daq_list_number)->mode = 0x00u;
        Xcp_DaqListRt(daq_list_number)->eventChannelNumber = 0x0000u;
        Xcp_DaqListRt(daq_list_number)->prescaler = 0x01u;
        Xcp_DaqListRt(daq_list_number)->prescalerCounter = 0x00u;
        Xcp_DaqListRt(daq_list_number)->priority = 0x00u;

        /* The mode reset above may have just stopped the only list that was running, so
         * DAQ_RUNNING (1.1/1.6.1.1.3) needs recomputing across every list, not just this one. */
        Xcp_DaqSessionStatusUpdate();

        /* The pointer names an entry this command has just reset, so it no longer names
         * anything meaningful. */
        if ((Xcp_Internal.daq_pointer.valid == TRUE) &&
            (Xcp_Internal.daq_pointer.daqListNumber == daq_list_number))
        {
            Xcp_Internal.daq_pointer.valid = FALSE;
        }
    }

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdDaqSetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 prescaler = pPduInfo->SduDataPtr[0x06u];
    const uint8 priority = pPduInfo->SduDataPtr[0x07u];
    uint16 daq_list_number;
    uint16 event_channel_number;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &daq_list_number, Xcp_Ptr->general->byteOrder);
    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x04u], &event_channel_number, Xcp_Ptr->general->byteOrder);

    if (Xcp_DaqListIsValid(daq_list_number) == FALSE)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if ((Xcp_DaqListRt(daq_list_number)->mode & XCP_DAQ_LIST_MODE_RUNNING) != 0x00u)
    {
        error = XCP_E_ASAM_DAQ_ACTIVE;
    }
    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.3
     * DIRECTION selects stimulation and PID_OFF a DTO without an identification field; 1.1 adds
     * ALTERNATING somewhere in bits 6..7. None of these three is implemented, and 1.7.3.2.4 lists
     * ERR_MODE_NOT_VALID for this command, which is precisely what an unsupported mode is.
     * TIMESTAMP is handled separately below: whether it is honoured depends on this build's
     * configuration, not on a blanket refusal. */
    else if ((mode & XCP_DAQ_LIST_MODE_REQ_UNSUPPORTED) != 0x00u)
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.3
     * TIMESTAMP asks for a mode this build may not have a clock for. DD9: an unsupported mode is
     * what ERR_MODE_NOT_VALID means. */
    else if (((mode & XCP_DAQ_LIST_MODE_REQ_TIMESTAMP) != 0x00u) &&
             (Xcp_Ptr->general->timestampType == NO_TIME_STAMP))
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    /* The timestamp occupies Xcp_TimestampWireSize(timestampType) bytes of ODT 0 only (1.1/1.1.2.2,
     * Diagram 10), so enabling it shrinks that ODT's budget below the MAX_ODT_ENTRY_SIZE_DAQ that
     * GET_DAQ_RESOLUTION_INFO reports and WRITE_DAQ enforced when the entries were written. An ODT
     * 0 already filled past the reduced budget cannot carry one. 0xFFu as excludedEntry excludes
     * nothing -- every configured slot is counted; no real index can equal it because the loop in
     * Xcp_OdtUsedBytes bounds idx strictly below maxOdtEntries, itself a uint8.
     *
     * maxOdt first, and short-circuited: a list configured with max_odt 0 has no ODT 0 at all, and
     * its generated Xcp_OdtType array is zero-length, so passing 0x00u to Xcp_OdtUsedBytes reads
     * off the end of it. This is the module's only odt[ index bounded by neither maxOdt nor
     * SET_DAQ_PTR's validation. A list with nowhere to put the timestamp answers the same
     * ERR_OUT_OF_RANGE the capacity check does: it is the capacity question with the answer
     * "none", and the master's recovery -- retry other parameter -- is the same one. */
    else if (((mode & XCP_DAQ_LIST_MODE_REQ_TIMESTAMP) != 0x00u) &&
             ((Xcp_Ptr->config->daqList[daq_list_number].maxOdt == 0x00u) ||
              ((uint16)Xcp_OdtUsedBytes(daq_list_number, 0x00u, 0xFFu) >
               (uint16)(Xcp_Ptr->general->odtEntrySizeDaq -
                        Xcp_TimestampWireSize(Xcp_Ptr->general->timestampType)))))
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if (event_channel_number >= Xcp_Ptr->general->maxEventChannel)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if ((prescaler == 0x00u) ||
             ((prescaler > 0x01u) && (Xcp_Ptr->general->prescalerSupported == FALSE)))
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    /* 1.1/1.6.4.1.1.3 names the code for this one outright: "If the ECU doesn't support the
     * prioritization of DAQ lists, a DAQ list priority > 0 is not allowed and will be indicated
     * by returning ERR_OUT_OF_RANGE." */
    else if (priority != 0x00u)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    /* 1.1/1.1.2.1: PID_OFF is 'only allowed if the Identification Field Type is absolute ODT
     * number', and identification then falls to the transport layer, which 1.1.2.1 says needs
     * 'separate CAN-Ids for each DAQ list and only one ODT for each DAQ list'.
     *
     * All three conditions are checked, because the transport-layer half is not satisfied by
     * construction: this module gives a DAQ list exactly one TX PDU, which is not the same as
     * giving each list a distinct one (Xcp_DaqListTxPduIsExclusive, this file). Two single-ODT
     * lists sharing a TX PDU -- the arrangement config/xcp.json ships -- would otherwise both be
     * granted PID_OFF and put two DTOs on one CAN-Id with nothing to tell them apart. */
    else if (((mode & XCP_DAQ_LIST_MODE_REQ_PID_OFF) != 0x00u) &&
             ((Xcp_Ptr->general->identificationFieldType != ABSOLUTE) ||
              (Xcp_Ptr->config->daqList[daq_list_number].maxOdt != 0x01u) ||
              (Xcp_DaqListTxPduIsExclusive(daq_list_number) == FALSE)))
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else
    {
        Xcp_DaqListRt(daq_list_number)->eventChannelNumber = event_channel_number;
        Xcp_DaqListRt(daq_list_number)->prescaler = prescaler;
        Xcp_DaqListRt(daq_list_number)->prescalerCounter = 0x00u;
        Xcp_DaqListRt(daq_list_number)->priority = priority;

        /* The stored mode uses the GET_DAQ_LIST_MODE layout of 1.1/1.6.4.1.2.6, which is not the
         * layout this request arrives in -- TIMESTAMP and PID_OFF happen to sit at the same bit in
         * both, but that is a coincidence, not a shortcut: do not be tempted to assign `mode`
         * wholesale here when DIRECTION becomes supported too, as it sits at a different bit in
         * each byte (request bit 0, stored bit 1). Xcp_DTOCmdDaqGetDaqListMode (below) reads these
         * same bits back. */
        if ((mode & XCP_DAQ_LIST_MODE_REQ_TIMESTAMP) != 0x00u)
        {
            Xcp_DaqListRt(daq_list_number)->mode |= XCP_DAQ_LIST_MODE_TIMESTAMP;
        }
        else
        {
            Xcp_DaqListRt(daq_list_number)->mode &= (uint8)(~XCP_DAQ_LIST_MODE_TIMESTAMP);
        }

        /* Re-specified in full on every request, not only ever settable: a master that turns
         * PID_OFF back off in a later SET_DAQ_LIST_MODE must see it actually cleared here, exactly
         * as TIMESTAMP is above. */
        if ((mode & XCP_DAQ_LIST_MODE_REQ_PID_OFF) != 0x00u)
        {
            Xcp_DaqListRt(daq_list_number)->mode |= XCP_DAQ_LIST_MODE_PID_OFF;
        }
        else
        {
            Xcp_DaqListRt(daq_list_number)->mode &= (uint8)(~XCP_DAQ_LIST_MODE_PID_OFF);
        }
    }

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdDaqGetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint16 daq_list_number;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &daq_list_number, Xcp_Ptr->general->byteOrder);

    if (Xcp_DaqListIsValid(daq_list_number) == FALSE)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.6
         * Xcp_DaqListRtType stores the mode in exactly this layout, so it needs no translation
         * on the way out. The request of 1.6.4.1.1.3 uses a different one. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_DaqListRt(daq_list_number)->mode;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u; /* reserved */

        Xcp_CopyFromU16WithOrder(Xcp_DaqListRt(daq_list_number)->eventChannelNumber,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                 Xcp_Ptr->general->byteOrder);

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u] = Xcp_DaqListRt(daq_list_number)->prescaler;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x07u] = Xcp_DaqListRt(daq_list_number)->priority;

        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

/**
 * @brief maps the configured consistency level onto DAQ_EVENT_PROPERTIES' CONSISTENCY_DAQ and
 * CONSISTENCY_EVENT bits.
 * @details XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.7: 00 is consistency on ODT
 * level (the default -- neither bit set), 01 is CONSISTENCY_DAQ (DAQ list level) and 10 is
 * CONSISTENCY_EVENT (event channel level). All three are configurable -- config/xcp.schema.json
 * has always permitted "DAQ", and DAQ_LIST is the enumerator it maps to (see the note above
 * Xcp_EventChannelConsistencyType in interface/Xcp_Types.h).
 */
static uint8 Xcp_EventConsistencyBits(Xcp_EventChannelConsistencyType consistency)
{
    uint8 bits;

    switch (consistency)
    {
        case EVENT:
            bits = XCP_DAQ_EVENT_PROPERTIES_CONSISTENCY_EVENT;
            break;
        case DAQ_LIST:
            bits = XCP_DAQ_EVENT_PROPERTIES_CONSISTENCY_DAQ;
            break;
        case ODT:
        default:
            bits = 0x00u;
            break;
    }

    return bits;
}

/**
 * @brief GET_DAQ_EVENT_INFO, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.7.
 * @details Defined immediately before Xcp_DTOCmdDaqGetDaqListInfo, its neighbour in the PID
 * table (0xD7 before 0xD8) and its closest sibling in shape: both take a channel/list number,
 * answer ERR_OUT_OF_RANGE for one that does not exist, and build a PROPERTIES byte the same way.
 * @note MAX_DAQ_LIST reports the *configured* length of triggeredDaqListRef -- "the maximum number
 * of DAQ lists in this event channel". That is a different question from the *runtime* binding
 * SET_DAQ_LIST_MODE writes to Xcp_Rt[...].daqList[...].eventChannelNumber (DD23, see
 * Xcp_DTOCmdDaqGetDaqListInfo's own EVENT_FIXED comment below), which is which list is bound
 * right now, and until this task triggeredDaqListRef had no runtime role at all.
 */
uint8 Xcp_DTOCmdDaqGetDaqEventInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint16 event_channel_number;

    *responseExpected = TRUE;

    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &event_channel_number, Xcp_Ptr->general->byteOrder);

    if (event_channel_number >= Xcp_Ptr->general->maxEventChannel)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        const Xcp_EventChannelType *p_channel = &Xcp_Ptr->config->eventChannel[event_channel_number];
        uint8 properties = 0x00u;

        /* DAQ_EVENT_PROPERTIES: DAQ set for DAQ and DAQ_STIM, the same condition
         * Xcp_DTOCmdDaqGetDaqListInfo's own DAQ_LIST_PROPERTIES uses below for its DAQ bit. STIM
         * stays clear even for a DAQ_STIM channel for the same reason that comment gives: data
         * stimulation arrives in SP3. */
        if ((p_channel->type == DAQ) || (p_channel->type == DAQ_STIM))
        {
            properties |= XCP_DAQ_EVENT_PROPERTIES_DAQ;
        }

        properties |= Xcp_EventConsistencyBits(p_channel->consistency);

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = properties;
        /* maxDaqList, not (uint8)triggeredDaqListRefCount: the two are generated from the same
         * expression, but maxDaqList is the uint8 field whose doxygen quotes 1.6.4.1.2.7's own
         * definition of MAX_DAQ_LIST, while triggeredDaqListRefCount is a uint32 that a cast here
         * would silently truncate -- 256 references would report 0, telling the master the
         * channel handles no lists at all. The count that cannot be represented now fails
         * generation instead (script/source_cfg.c.jinja2), so the two agree by construction. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = p_channel->maxDaqList;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = p_channel->nameLength;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = p_channel->timeCycle;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = (uint8)p_channel->timeUnit;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u] = p_channel->priority;

        /* 1.1/1.6.4.1.2.7: the command "automatically sets the Memory Transfer Address (MTA) to
         * the location from which the master device may upload the event channel name". No
         * Xcp_SetMta exists to call: Xcp_DTOCmdStdSetMta (source/Xcp_Std.c, SET_MTA's own
         * handler) writes these same two fields directly rather than through a wrapper, so this
         * does the same. Only when there is somewhere real to point, though -- with nothing to
         * publish, moving the MTA to NULL_PTR would silently invalidate whatever the master had
         * already set with SET_MTA, so it is left alone instead. */
        if (p_channel->nameLength != 0x00u)
        {
            Xcp_Internal.memory_transfer.address = (void *)p_channel->namePtr;
            Xcp_Internal.memory_transfer.extension = 0x00u;
        }

        Xcp_FinalizeResPacket(0x07u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

/**
 * @brief GET_DAQ_LIST_INFO, XCP part 2 - Protocol Layer Specification 1.1/1.6.4.2.2.1.
 * @details Unlike its neighbours in the PID table (0xD9 GET_DAQ_RESOLUTION_INFO, 0xDA
 * GET_DAQ_PROCESSOR_INFO, 0xDB READ_DAQ, all 1.6.4.1.2.x), this command's own section sits in a
 * different subtree -- 1.6.4 is renumbered wholesale between 1.0 and 1.1, so nothing here carries
 * a 1.0-era citation forward.
 */
uint8 Xcp_DTOCmdDaqGetDaqListInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint16 daq_list_number;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &daq_list_number, Xcp_Ptr->general->byteOrder);

    /* 1.1/1.6.4.2.2.1: "If the specified list is not available, ERR_OUT_OF_RANGE will be
     * returned." Unlike the DAQ pointer (Task 9, no predicate of its own), the DAQ list has a
     * real one -- Xcp_DaqListIsValid, used the same way GET_DAQ_LIST_MODE and CLEAR_DAQ_LIST use
     * it above. */
    if (Xcp_DaqListIsValid(daq_list_number) == FALSE)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }

    if (error == 0x00u)
    {
        uint8 properties = 0x00u;

        /* DAQ_LIST_PROPERTIES:
         * PREDEFINED stays clear -- the master configures this list's ODT entries through
         * WRITE_DAQ rather than them being fixed at build time.
         * EVENT_FIXED stays clear (DD23): Xcp_TriggerEventChannel (Xcp_DaqRuntime.c) samples a
         * list by the event-channel binding SET_DAQ_LIST_MODE wrote at runtime
         * (Xcp_Rt[...].daqList[...].eventChannelNumber), not by this list's configured
         * triggeredDaqListRef -- so the master can genuinely move a list between event channels,
         * which is exactly what EVENT_FIXED = 0 means. FIXED_EVENT below is therefore don't-care
         * and zero-filled.
         * STIM stays clear even for a DAQ_STIM list: data stimulation arrives in SP3, matching
         * the STIM granularity of 0 that Xcp_DTOCmdDaqGetDaqResolutionInfo (this file) already
         * reports for the same reason. */
        if ((Xcp_Ptr->config->daqList[daq_list_number].type == DAQ) ||
            (Xcp_Ptr->config->daqList[daq_list_number].type == DAQ_STIM))
        {
            properties |= XCP_DAQ_LIST_PROPERTIES_DAQ;
        }

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = properties;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = Xcp_Ptr->config->daqList[daq_list_number].maxOdt;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] =
                Xcp_Ptr->config->daqList[daq_list_number].maxOdtEntries;

        /* FIXED_EVENT: don't-care per EVENT_FIXED above. Zero-filled through the same
         * byte-order-aware helper every other multi-byte field in this file uses, for
         * consistency, even though the all-zero result is order-independent. */
        Xcp_CopyFromU16WithOrder(0x0000u,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                 Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x06u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdDaqStartStopDaqList(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    uint16 daq_list_number;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &daq_list_number, Xcp_Ptr->general->byteOrder);

    if (Xcp_DaqListIsValid(daq_list_number) == FALSE)
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if (mode > XCP_DAQ_START_STOP_MODE_SELECT)
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else if ((mode != XCP_DAQ_START_STOP_MODE_STOP) &&
             (Xcp_DaqListIsConfigured(daq_list_number) == FALSE))
    {
        error = XCP_E_ASAM_DAQ_CONFIG;
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.4 */
        if (mode == XCP_DAQ_START_STOP_MODE_START)
        {
            /* Reset the counter before setting RUNNING: once RUNNING is visible, a trigger
             * preempting between the two writes must never sample against a stale counter
             * left over from a previous run. */
            Xcp_DaqListRt(daq_list_number)->prescalerCounter = 0x00u;
            Xcp_DaqListRt(daq_list_number)->mode |= XCP_DAQ_LIST_MODE_RUNNING;
        }
        else if (mode == XCP_DAQ_START_STOP_MODE_SELECT)
        {
            Xcp_DaqListRt(daq_list_number)->mode |= XCP_DAQ_LIST_MODE_SELECTED;
        }
        else
        {
            Xcp_DaqListRt(daq_list_number)->mode &= (uint8)(~XCP_DAQ_LIST_MODE_RUNNING);
        }

        Xcp_DaqSessionStatusUpdate();
    }

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        /* 1.1/1.6.4.1.1.4: FIRST_PID may be ignored by a master using a relative identification
         * field type, but the response format does not change, so it is always sent. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] =
                Xcp_Ptr->config->daqList[daq_list_number].firstPid;

        Xcp_FinalizeResPacket(0x02u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdDaqStartStopSynch(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    uint8 error = 0x00u;
    uint16 idx;
    boolean any_selected = FALSE;

    *responseExpected = TRUE;

    for (idx = 0x0000u; idx < Xcp_Ptr->general->daqCount; idx++)
    {
        if ((Xcp_DaqListRt(idx)->mode & XCP_DAQ_LIST_MODE_SELECTED) != 0x00u)
        {
            any_selected = TRUE;
        }
    }

    if (mode > XCP_DAQ_SYNCH_MODE_STOP_SELECTED)
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else if ((mode == XCP_DAQ_SYNCH_MODE_START_SELECTED) && (any_selected == FALSE))
    {
        /* Starting the selected lists when none is selected starts nothing, which is a DAQ
         * configuration the master did not intend. 1.7.3.2.4 lists ERR_DAQ_CONFIG here. */
        error = XCP_E_ASAM_DAQ_CONFIG;
    }
    else
    {
        for (idx = 0x0000u; idx < Xcp_Ptr->general->daqCount; idx++)
        {
            const boolean selected =
                    (boolean)(((Xcp_DaqListRt(idx)->mode & XCP_DAQ_LIST_MODE_SELECTED) != 0x00u)
                              ? TRUE : FALSE);

            /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.1.5 */
            if (mode == XCP_DAQ_SYNCH_MODE_STOP_ALL)
            {
                Xcp_DaqListRt(idx)->mode &= (uint8)(~XCP_DAQ_LIST_MODE_RUNNING);
            }
            else if (selected == TRUE)
            {
                if (mode == XCP_DAQ_SYNCH_MODE_START_SELECTED)
                {
                    /* Reset the counter before setting RUNNING -- see the identical ordering
                     * argument in Xcp_DTOCmdDaqStartStopDaqList above. */
                    Xcp_DaqListRt(idx)->prescalerCounter = 0x00u;
                    Xcp_DaqListRt(idx)->mode |= XCP_DAQ_LIST_MODE_RUNNING;
                }
                else
                {
                    Xcp_DaqListRt(idx)->mode &= (uint8)(~XCP_DAQ_LIST_MODE_RUNNING);
                }
            }
            else
            {
                /* Not selected, and the mode applies only to selected lists. */
            }

            /* "The slave device software has to reset the mode SELECTED of a DAQ list after
             * successful execution of a START_STOP_SYNCH." All three modes are an execution. */
            Xcp_DaqListRt(idx)->mode &= (uint8)(~XCP_DAQ_LIST_MODE_SELECTED);
        }

        Xcp_DaqSessionStatusUpdate();
    }

    if (error == 0x00u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdDaqGetDaqProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    uint8 properties = 0x00u;
    uint8 key_byte;

    (void)pPduInfo;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.4
     * DAQ_CONFIG_TYPE stays clear: this phase configures DAQ lists statically. RESUME and
     * BIT_STIM are unimplemented and so are reported unsupported, which is what lets
     * SET_DAQ_LIST_MODE refuse the matching mode bits. TIMESTAMP_SUPPORTED and PID_OFF_SUPPORTED
     * are not in that group: TIMESTAMP_SUPPORTED follows whether the configuration declares a
     * clock, set just below; PID_OFF_SUPPORTED follows the identification field type, set here. */
    if (Xcp_Ptr->general->prescalerSupported == TRUE)
    {
        properties |= XCP_DAQ_PROPERTIES_PRESCALER_SUPPORTED;
    }

    /* TIMESTAMP_SUPPORTED (bit 4): NO_TIME_STAMP means protocol_layer.timestamp was absent from
     * the configuration (Task 1), the same condition GET_DAQ_RESOLUTION_INFO's TIMESTAMP_MODE /
     * TIMESTAMP_TICKS branch below tests. */
    if (Xcp_Ptr->general->timestampType != NO_TIME_STAMP)
    {
        properties |= XCP_DAQ_PROPERTIES_TIMESTAMP_SUPPORTED;
    }

    /* PID_OFF_SUPPORTED (bit 5): 1.1/1.1.2.1 permits turning off the Identification Field "only
     * ... if the Identification Field Type is absolute ODT number" -- with any other type no DAQ
     * list could ever accept the bit (Xcp_DTOCmdDaqSetDaqListMode also requires a single-ODT list,
     * a per-list condition GET_DAQ_PROCESSOR_INFO's one build-wide byte cannot express here). */
    if (Xcp_Ptr->general->identificationFieldType == ABSOLUTE)
    {
        properties |= XCP_DAQ_PROPERTIES_PID_OFF_SUPPORTED;
    }

    /* OVERLOAD_MSB stays clear: indicating an overload in the MSB of the PID would cap every
     * ODT number below 0x7C whether or not an overload ever happened. */
    if (Xcp_Ptr->general->overloadEvent == TRUE)
    {
        properties |= XCP_DAQ_PROPERTIES_OVERLOAD_EVENT;
    }

    /* DAQ_KEY_BYTE: identification field type in bits 7:6, address extension type in bits 5:4,
     * optimisation type in bits 3:0. The address extension may differ within one ODT (0b00) and
     * the optimisation type is OM_DEFAULT (0b0000), so only the field type contributes.
     * This shift is only correct because Xcp_IdentificationFieldTypeType enumerates ABSOLUTE=0,
     * RELATIVE_BYTE=1, RELATIVE_WORD=2, RELATIVE_WORD_ALIGNED=3 (interface/Xcp_Types.h), which
     * matches the bit pattern this section of the specification assigns. Do not renumber that
     * enum without updating this shift. */
    key_byte = (uint8)((uint8)Xcp_Ptr->general->identificationFieldType << 0x06u);

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = properties;

    Xcp_CopyFromU16WithOrder(Xcp_Ptr->general->daqCount,
                             &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u],
                             Xcp_Ptr->general->byteOrder);
    Xcp_CopyFromU16WithOrder(Xcp_Ptr->general->maxEventChannel,
                             &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                             Xcp_Ptr->general->byteOrder);

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u] = Xcp_Ptr->general->minDaq;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x07u] = key_byte;

    Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

/* Declared in Xcp_Internal.h, external linkage -- see the declaration there for why. */
uint8 Xcp_TimestampWireSize(Xcp_TimestampTypeType type)
{
    uint8 size;

    switch (type)
    {
        case ONE_BYTE:
            size = 0x01u;
            break;
        case TWO_BYTE:
            size = 0x02u;
            break;
        case FOUR_BYTE:
            size = 0x04u;
            break;
        case NO_TIME_STAMP:
        default:
            size = 0x00u;
            break;
    }

    return size;
}

uint8 Xcp_DTOCmdDaqGetDaqResolutionInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

    /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.5
     * The granularity is what an ODT entry's size must be a multiple of and what its address
     * must be aligned to, which is exactly the address granularity's element size (1, 2 or 4) --
     * one of the {1,2,4,8} this section allows. WRITE_DAQ (Task 7) checks a new entry's size
     * against this same Xcp_ElementSizeForAddressGranularity() result, so the two commands agree
     * on what counts as a legal entry size by construction. */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] =
            Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);

    /* MAX_ODT_ENTRY_SIZE_DAQ is the same derived value (MAX_DTO minus the identification field
     * size, Task 1) that WRITE_DAQ refuses entries larger than
     * (source/Xcp_Daq.c:Xcp_DTOCmdDaqWriteDaq, "size > Xcp_Ptr->general->odtEntrySizeDaq"). A
     * master that trusts what this command reports can never have WRITE_DAQ refuse it. */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = Xcp_Ptr->general->odtEntrySizeDaq;

    /* Data stimulation arrives in SP3; until then a STIM granularity of 0 says so, and there is
     * no WRITE_DAQ-equivalent for STIM yet to disagree with it. */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = Xcp_Ptr->general->odtEntrySizeStim;

    if (Xcp_Ptr->general->timestampType == NO_TIME_STAMP)
    {
        /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.5
         * "If the slave doesn't support a time stamped mode, the parameters TIMESTAMP_MODE and
         * TIMESTAMP_TICKS are invalid" -- permitted explicitly because TIMESTAMP_SUPPORTED
         * (DAQ_PROPERTIES bit 4, GET_DAQ_PROCESSOR_INFO) is clear. These two bytes are not a
         * stand-in for "unimplemented"; they are the specification's own way of saying the
         * fields carry no meaning, and must not be read as e.g. "timestamp mode 0" or "zero
         * ticks of delay". */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = 0x00u;

        Xcp_CopyFromU16WithOrder(0x0000u,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u],
                                 Xcp_Ptr->general->byteOrder);
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.5
         * TIMESTAMP_MODE: bits 2:0 size, bit 3 TIMESTAMP_FIXED, bits 7:4 unit. TIMESTAMP_FIXED
         * stays clear because the master switches the timestamp per DAQ list through
         * SET_DAQ_LIST_MODE. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] =
                (uint8)(Xcp_TimestampWireSize(Xcp_Ptr->general->timestampType) |
                        (uint8)((uint8)Xcp_Ptr->general->timestampUnit << 0x04u));

        Xcp_CopyFromU16WithOrder(Xcp_Ptr->general->timestampTicks,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x06u],
                                 Xcp_Ptr->general->byteOrder);
    }

    Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

#if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON)

uint8 Xcp_DTOCmdDaqGetDaqClock(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    /* XCP_DAQ_TIMESTAMP_SUPPORTED is ANY across the configurations compiled into this module
     * (script/header_cfg.h.jinja2 folds it with `any`), so compiling this handler in says only
     * that SOME configuration declares a clock. Whether the *active* one does is a separate
     * question, and the answer is Xcp_Ptr->general->timestampType, exactly as it is for
     * GET_DAQ_PROCESSOR_INFO's TIMESTAMP_SUPPORTED bit, GET_DAQ_RESOLUTION_INFO's
     * TIMESTAMP_MODE / TIMESTAMP_TICKS pair and SET_DAQ_LIST_MODE's TIMESTAMP arm. Without this
     * gate a two-configuration build would have the other three tell the master there is no
     * clock while this one answered with a value -- and would call Xcp_GetDaqTimestamp() on
     * behalf of a configuration that never contracted for it. ERR_CMD_UNKNOWN is what
     * Xcp_CmdNotImplemented answers for a command this build does not have, which is what this
     * command is for a configuration with no clock. */
    if (Xcp_Ptr->general->timestampType == NO_TIME_STAMP)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_CMD_UNKNOWN, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        /* XCP part 2 - Protocol Layer Specification 1.1/1.6.4.1.2.3 reserves byte 1 and the WORD
         * at 2..3. Zero-filled, so their byte order is immaterial. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u;

        /* 1.1/1.6.4.1.2.3 wants the value "when the GET_DAQ_CLOCK command packet has been
         * received". Xcp_CanIfRxIndication dispatches to this handler synchronously, in the same
         * call that received the command, so reading the clock here already is that moment --
         * there is no later, differently-scheduled point (Xcp_MainFunction never assembles CTO
         * responses; see the Task 8 report) for this read to be deferred from. */
        Xcp_CopyFromU32WithOrder(Xcp_GetDaqTimestamp(),
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                 Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

#endif /* #if (XCP_DAQ_TIMESTAMP_SUPPORTED == STD_ON) */

