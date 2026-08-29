/**
 * @file Xcp_Cal.c
 * @author
 * @date
 *
 * @defgroup XCP_CAL_C CALIBRATION command group implementation
 * @ingroup XCP
 */

#ifndef XCP_INTERNAL_H
#include "Xcp_Internal.h"
#endif /* #ifndef XCP_INTERNAL_H */

/*------------------------------------------------------------------------------------------------*/
/* local function definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

uint8 Xcp_DTOCmdStdDownloadNext(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    Std_ReturnType result = E_OK;
    return result;
}

uint8 Xcp_DTOCmdStdDownload(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    Std_ReturnType result = E_OK;
    const uint8_least element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8_least alignment = Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1
     * If the slave device does not support block transfer mode, all downloaded data are transferred in a single command packet. Therefore, the
     * number of data elements parameter in the request has to be in the range [1..MAX_CTO-2]. An ERR_OUT_OF_RANGE will be returned, if the number
     * of data elements is more than MAX_CTO-2. */
    if (((Xcp_Ptr->general->slaveBlockModeSupported == FALSE) &&
         ((number_of_data_elements * element_size) <= (Xcp_Ptr->general->maxCto - 0x02u))) ||
        (Xcp_Ptr->general->slaveBlockModeSupported == TRUE))
    {
        
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }

    return result;
}
