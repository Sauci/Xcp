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

