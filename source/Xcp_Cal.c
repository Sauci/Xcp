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
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8 alignment = (uint8)Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];
    uint8 expected = 0x00u;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.1
     * It contains the remaining number of data elements to transmit. The slave device will use
     * this information to detect lost packets. If a sequence error has been detected, the error
     * code ERR_SEQUENCE will be returned. The negative response will contain the expected number
     * of data elements. */
    if (Xcp_BlockTransferIsActive() == TRUE)
    {
        expected = Xcp_Internal.block_transfer.requested_elements;

        if (number_of_data_elements == expected)
        {
            if (Xcp_BlockTransferWriteSlaveMemory(&pPduInfo->SduDataPtr[0x02u + alignment],
                                                  element_size) == E_NOT_OK)
            {
                Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

                Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
            }
            else
            {
                *responseExpected = FALSE;
            }
        }
        else
        {
            Xcp_FillErrorPacketWithData(XCP_E_ASAM_SEQUENCE,
                                        &expected,
                                        0x01u,
                                        &Xcp_Internal.cto_response.pdu_info);

            Xcp_BlockTransferAbort();
        }
    }
    else
    {
        Xcp_FillErrorPacketWithData(XCP_E_ASAM_SEQUENCE,
                                    &expected,
                                    0x01u,
                                    &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdDownload(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8 alignment = (uint8)Xcp_GetNumberOfAlignmentBytes(0x02u, element_size, Xcp_Ptr->general->maxCto);
    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1
     * The data block of the specified length (size) contained in the CMD will be copied into
     * memory, starting at the MTA. The MTA will be post-incremented by the number of data bytes.
     *
     * XCP part 2 - Protocol Layer Specification 1.0/1.6.1.2.1
     * MAX_BS applies to master block mode, whose packets are DOWNLOAD_NEXT. Slave block mode
     * governs multi-response commands such as UPLOAD and is not consulted here. */
    if (Xcp_DataTransferInitialize(number_of_data_elements,
                                   element_size,
                                   alignment,
                                   (uint8)(Xcp_Ptr->general->maxCto - 0x02u),
                                   Xcp_Ptr->general->masterBlockModeSupported,
                                   Xcp_Ptr->general->maxBS) == E_OK)
    {
        if (Xcp_BlockTransferWriteSlaveMemory(&pPduInfo->SduDataPtr[0x02u + alignment],
                                              element_size) == E_NOT_OK)
        {
            /* The whole payload has been written, so the command is acknowledged now. */
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

            Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
        }
        else
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.1.1
             * The slave device will acknowledge only the last DOWNLOAD_NEXT command packet. */
            *responseExpected = FALSE;
        }
    }
    else
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
