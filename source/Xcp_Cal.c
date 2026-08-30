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

uint8 Xcp_DTOCmdStdDownloadMax(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    uint8 number_of_data_elements;
    uint8_least idx;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2
     * This command does not support block transfer and it mustn't be used within a block transfer
     * sequence. The specification prescribes no error code for the violation; ERR_SEQUENCE is the
     * accurate one and leaves the master able to recover. */
    if (Xcp_BlockTransferIsActive() == TRUE)
    {
        Xcp_BlockTransferAbort();

        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (pPduInfo->SduLength < (PduLengthType)Xcp_Ptr->general->maxCto)
    {
        /* The minimum request size of this command is MAX_CTO, which does not fit the four-bit
         * field of ctoInfo, so the check happens here. */
        Xcp_FillErrorPacket(XCP_E_ASAM_CMD_SYNTAX, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.2
         * The data block with the fixed length (size) of MAX_CTO/AG-1 elements contained in the
         * CMD will be copied into memory, starting at the MTA. The MTA will be post-incremented by
         * MAX_CTO/AG-1. */
        number_of_data_elements = (uint8)((Xcp_Ptr->general->maxCto / element_size) - 0x01u);

        for (idx = 0x00u; idx < number_of_data_elements; idx++)
        {
            Xcp_WriteSlaveMemoryTable[Xcp_Ptr->general->addressGranularity](
                Xcp_Internal.memory_transfer.address,
                &pPduInfo->SduDataPtr[element_size + (idx * element_size)]);

            Xcp_Internal.memory_transfer.address += element_size;
        }

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdShortDownload(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 element_size = Xcp_ElementSizeForAddressGranularity(Xcp_Ptr->general->addressGranularity);
    const uint8 number_of_data_elements = pPduInfo->SduDataPtr[0x01u];
    uint8 capacity = 0x00u;
    uint32 address;
    uint8_least idx;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3
     * Please note that this command will have no effect (no data bytes can be transferred) if
     * MAX_CTO = 8 (e.g. XCP on CAN). */
    if (Xcp_Ptr->general->maxCto >= 0x08u)
    {
        capacity = (uint8)((Xcp_Ptr->general->maxCto - 0x08u) / element_size);
    }

    if (Xcp_BlockTransferIsActive() == TRUE)
    {
        /* This command mustn't be used within a block transfer sequence. */
        Xcp_BlockTransferAbort();

        Xcp_FillErrorPacket(XCP_E_ASAM_SEQUENCE, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (number_of_data_elements > capacity)
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3
         * If the number of elements exceeds (MAX_CTO-8)/AG, the error code ERR_OUT_OF_RANGE will
         * be returned. */
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_CopyToU32WithOrder(&pPduInfo->SduDataPtr[0x04u], &address, Xcp_Ptr->general->byteOrder);

        Xcp_Internal.memory_transfer.extension = pPduInfo->SduDataPtr[0x03u];

        for (idx = 0x00u; idx < number_of_data_elements; idx++)
        {
            Xcp_WriteSlaveMemoryTable[Xcp_Ptr->general->addressGranularity](
                (void *)address,
                &pPduInfo->SduDataPtr[0x08u + (idx * element_size)]);

            address += element_size;
        }

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.3
         * The MTA pointer is set to the first data element behind the downloaded data block. */
        Xcp_Internal.memory_transfer.address = (void *)address;

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdModifyBits(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 shift_value = pPduInfo->SduDataPtr[0x01u];
    uint16 and_mask;
    uint16 xor_mask;
    uint32 value;
    uint8 buffer[0x04u];

    *responseExpected = TRUE;

    /* A shift of 32 or more is undefined behaviour on a 32 bit value. The specification puts no
     * bound on S, so the request is rejected rather than evaluated. */
    if (shift_value > 0x1Fu)
    {
        Xcp_FillErrorPacket(XCP_E_ASAM_OUT_OF_RANGE, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x02u], &and_mask, Xcp_Ptr->general->byteOrder);
        Xcp_CopyToU16WithOrder(&pPduInfo->SduDataPtr[0x04u], &xor_mask, Xcp_Ptr->general->byteOrder);

        Xcp_ReadSlaveMemoryU32(Xcp_Internal.memory_transfer.address,
                               Xcp_Internal.memory_transfer.extension,
                               &buffer[0x00u]);

        Xcp_CopyToU32WithOrder(&buffer[0x00u], &value, Xcp_Ptr->general->byteOrder);

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.4
         * A = ( (A) & ((~((dword)(((word)~MA)<<S))) )^((dword)(MX<<S)) )
         * Both masks are widened to 32 bits before shifting; evaluating the shift at 16 bit width
         * would discard the high bits for any S >= 1. */
        value = (value & (~(((uint32)((uint16)(~and_mask))) << shift_value))) ^
                (((uint32)xor_mask) << shift_value);

        Xcp_CopyFromU32WithOrder(value, &buffer[0x00u], Xcp_Ptr->general->byteOrder);

        Xcp_WriteSlaveMemoryU32(Xcp_Internal.memory_transfer.address, &buffer[0x00u]);

        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.2.2.4
         * The MTA will not be affected. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}
