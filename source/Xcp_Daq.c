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
 */
void Xcp_DaqListClearEntries(uint16 daqListNumber)
{
    uint8_least odt_idx;
    uint8_least entry_idx;

    for (odt_idx = 0x00u; odt_idx < Xcp_Ptr->config->daqList[daqListNumber].maxOdt; odt_idx++)
    {
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
    }
}

/**
 * @brief bytes already claimed by the written entries of one ODT.
 * @details An ODT becomes one DTO frame, so the entries it holds have to fit in what the frame
 * leaves after the identification field. Entries not yet written have length 0 and contribute
 * nothing.
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
    const uint8 granularity = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    uint32 address;
    uint8 error = 0x00u;
    Xcp_OdtEntryType *p_entry = NULL_PTR;

    *responseExpected = TRUE;

    Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &address, Xcp_Ptr->general->byteOrder);

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
    else if ((bit_offset != XCP_ODT_ENTRY_BIT_OFFSET_NONE) &&
             ((bit_offset > XCP_ODT_ENTRY_BIT_OFFSET_MAX) || (size != granularity)))
    {
        error = XCP_E_ASAM_OUT_OF_RANGE;
    }
    else if ((uint16)((uint16)Xcp_OdtUsedBytes(Xcp_Internal.daq_pointer.daqListNumber,
                                               Xcp_Internal.daq_pointer.odtNumber,
                                               Xcp_Internal.daq_pointer.odtEntryNumber) + size) >
             (uint16)Xcp_Ptr->general->odtEntrySizeDaq)
    {
        /* DD8: the entry is individually legal but the ODT it joins can no longer be carried in
         * one DTO. 1.7.3.2.4 lists ERR_DAQ_CONFIG for WRITE_DAQ and this is the configuration it
         * describes. */
        error = XCP_E_ASAM_DAQ_CONFIG;
    }
    else
    {
        p_entry = &Xcp_Ptr->config->daqList[Xcp_Internal.daq_pointer.daqListNumber]
                       .odt[Xcp_Internal.daq_pointer.odtNumber]
                       .odtEntry[Xcp_Internal.daq_pointer.odtEntryNumber];

        p_entry->address = (uint32 *)address;
        p_entry->addressExtension = extension;
        p_entry->bitOffset = bit_offset;
        p_entry->length = size;

        /* 1.1/1.6.4.1.1.2: "The DAQ list pointer is auto post incremented to the next ODT entry
         * within one and the same ODT. After writing to the last ODT entry of an ODT, the value
         * of the DAQ pointer is undefined." */
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

