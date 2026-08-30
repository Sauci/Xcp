/**
 * @file Xcp_Pag.c
 * @author
 * @date
 *
 * @defgroup XCP_PAG_C PAGE SWITCHING command group implementation
 * @ingroup XCP
 */

#ifndef XCP_INTERNAL_H
#include "Xcp_Internal.h"
#endif /* #ifndef XCP_INTERNAL_H */

#ifndef XCP_RT_H
#include "Xcp_Rt.h"
#endif /* #ifndef XCP_RT_H */

#if (XCP_PAGING_SUPPORTED == STD_ON)

/*------------------------------------------------------------------------------------------------*/
/* local function definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

static boolean Xcp_SegmentIsValid(uint8 segment)
{
    return (boolean)((segment < Xcp_Ptr->general->maxSegment) ? TRUE : FALSE);
}

static boolean Xcp_PageIsValid(uint8 segment, uint8 page)
{
    boolean result = FALSE;

    if (Xcp_SegmentIsValid(segment) == TRUE)
    {
        if (page < Xcp_Ptr->config->segment[segment].maxPages)
        {
            result = TRUE;
        }
    }

    return result;
}

uint8 Xcp_DTOCmdStdSetCalPage(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    const uint8 page = pPduInfo->SduDataPtr[0x03u];
    uint8 error = 0x00u;
    uint8_least first;
    uint8_least last;
    uint8_least idx;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1
     * Both flags ECU and XCP may be set simultaneously or separately. A request selecting neither
     * asks for nothing and is rejected. */
    if ((mode & (XCP_CAL_PAGE_MODE_ECU | XCP_CAL_PAGE_MODE_XCP)) == 0x00u)
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else if (((mode & XCP_CAL_PAGE_MODE_ALL) == 0x00u) && (Xcp_SegmentIsValid(segment) == FALSE))
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1
         * The ALL flag makes the logical segment number irrelevant; the command applies to all
         * segments. */
        if ((mode & XCP_CAL_PAGE_MODE_ALL) != 0x00u)
        {
            first = 0x00u;
            last = Xcp_Ptr->general->maxSegment;
        }
        else
        {
            first = segment;
            last = (uint8_least)(segment + 0x01u);
        }

        /* Validate every affected segment before switching any of them, so a bad page number
         * cannot leave the slave half-switched. */
        for (idx = first; idx < last; idx++)
        {
            if (Xcp_PageIsValid((uint8)idx, page) == FALSE)
            {
                error = XCP_E_ASAM_PAGE_NOT_VALID;

                break;
            }
        }

        if (error == 0x00u)
        {
            for (idx = first; idx < last; idx++)
            {
                /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.1
                 * If the calibration data page cannot be set to the given mode, an
                 * ERR_MODE_NOT_VALID will be returned. The specification defines no rollback, so
                 * segments already switched stay switched. */
                if (Xcp_SetCalPage((uint8)idx, page, mode) != E_OK)
                {
                    error = XCP_E_ASAM_MODE_NOT_VALID;

                    break;
                }
            }
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

uint8 Xcp_DTOCmdStdGetCalPage(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    uint8 page = 0x00u;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.1.2
     * Mode may be 0x01 (ECU access) or 0x02 (XCP access). All other values are invalid. */
    if ((mode != XCP_CAL_PAGE_MODE_ECU) && (mode != XCP_CAL_PAGE_MODE_XCP))
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else if (Xcp_GetCalPage(segment, mode, &page) != E_OK)
    {
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = page;

        Xcp_FinalizeResPacket(0x04u, &Xcp_Internal.cto_response.pdu_info);
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdGetPagProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.1
     * MAX_SEGMENT is the total number of segments in the slave device. PAG_PROPERTIES bit 0 is
     * FREEZE_SUPPORTED, indicating that all SEGMENTS can be put in FREEZE mode. */
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = Xcp_Ptr->general->maxSegment;
    Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = Xcp_Ptr->general->pagProperties;

    Xcp_FinalizeResPacket(0x03u, &Xcp_Internal.cto_response.pdu_info);

    return E_OK;
}

boolean Xcp_GetSegmentFreezeState(uint8 segment)
{
    boolean result = FALSE;

    if (Xcp_SegmentIsValid(segment) == TRUE)
    {
        result = Xcp_Rt[Xcp_Ptr->xcpRtRef].segment[segment].freeze;
    }

    return result;
}

uint8 Xcp_DTOCmdStdSetSegmentMode(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else if (((mode & XCP_SEGMENT_MODE_FREEZE) != 0x00u) && ((Xcp_Ptr->general->pagProperties & 0x01u) == 0x00u))
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.1
         * PAG_PROPERTIES bit 0 is FREEZE_SUPPORTED, indicating that all SEGMENTS can be put in
         * FREEZE mode; a request to enable FREEZE on a slave that does not support it is
         * rejected. */
        error = XCP_E_ASAM_MODE_NOT_VALID;
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.4
         * The FREEZE flag selects the SEGMENT for freezing through STORE_CAL_REQ. */
        Xcp_Rt[Xcp_Ptr->xcpRtRef].segment[segment].freeze =
            (boolean)(((mode & XCP_SEGMENT_MODE_FREEZE) != 0x00u) ? TRUE : FALSE);

        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdGetSegmentMode(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.5
         * GET_SEGMENT_MODE reports the SEGMENT's current mode; bit 0 reflects whether FREEZE,
         * as set by SET_SEGMENT_MODE, is enabled. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] =
            (uint8)((Xcp_Rt[Xcp_Ptr->xcpRtRef].segment[segment].freeze == TRUE) ? XCP_SEGMENT_MODE_FREEZE : 0x00u);

        Xcp_FinalizeResPacket(0x03u, &Xcp_Internal.cto_response.pdu_info);
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdGetSegmentInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 mode = pPduInfo->SduDataPtr[0x01u];
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    const uint8 segment_info = pPduInfo->SduDataPtr[0x03u];
    const uint8 mapping_index = pPduInfo->SduDataPtr[0x04u];
    const Xcp_SegmentType *p_segment;
    uint32 value = 0x00000000u;
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else
    {
        p_segment = &Xcp_Ptr->config->segment[segment];

        if (mode == 0x00u)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2
             * Mode 0: SEGMENT_INFO selects 0 = address, 1 = length of this SEGMENT. */
            if (segment_info == 0x00u)
            {
                value = p_segment->address;
            }
            else if (segment_info == 0x01u)
            {
                value = p_segment->length;
            }
            else
            {
                error = XCP_E_ASAM_OUT_OF_RANGE;
            }
        }
        else if (mode == 0x01u)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2
             * Mode 1: SEGMENT_INFO and MAPPING_INDEX are don't care. */
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = p_segment->maxPages;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = p_segment->addressExtension;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = p_segment->maxMapping;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u] = p_segment->compressionMethod;
            Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x05u] = p_segment->encryptionMethod;

            Xcp_FinalizeResPacket(0x06u, &Xcp_Internal.cto_response.pdu_info);
        }
        else if (mode == 0x02u)
        {
            /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.2
             * Mode 2: SEGMENT_INFO selects 0 = source address, 1 = destination address,
             * 2 = length, for the range referenced by MAPPING_INDEX. */
            if (mapping_index >= p_segment->maxMapping)
            {
                error = XCP_E_ASAM_OUT_OF_RANGE;
            }
            else if (segment_info == 0x00u)
            {
                value = p_segment->addressMapping[mapping_index].sourceAddress;
            }
            else if (segment_info == 0x01u)
            {
                value = p_segment->addressMapping[mapping_index].destinationAddress;
            }
            else if (segment_info == 0x02u)
            {
                value = p_segment->addressMapping[mapping_index].length;
            }
            else
            {
                error = XCP_E_ASAM_OUT_OF_RANGE;
            }
        }
        else
        {
            error = XCP_E_ASAM_OUT_OF_RANGE;
        }
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }
    else if (mode != 0x01u)
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] = 0x00u; /* reserved */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x03u] = 0x00u; /* reserved */

        Xcp_CopyFromU32WithOrder(value,
                                 &Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x04u],
                                 Xcp_Ptr->general->byteOrder);

        Xcp_FinalizeResPacket(0x08u, &Xcp_Internal.cto_response.pdu_info);
    }
    else
    {
        /* Mode 1 has already assembled its response. */
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdGetPageInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 segment = pPduInfo->SduDataPtr[0x02u];
    const uint8 page = pPduInfo->SduDataPtr[0x03u];
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    if (Xcp_SegmentIsValid(segment) == FALSE)
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else if (Xcp_PageIsValid(segment, page) == FALSE)
    {
        error = XCP_E_ASAM_PAGE_NOT_VALID;
    }
    else
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.3
         * PAGE 0 of the INIT_SEGMENT of a PAGE contains the initial data for this PAGE. */
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x01u] =
            Xcp_Ptr->config->segment[segment].page[page].pageProperties;
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x02u] =
            Xcp_Ptr->config->segment[segment].page[page].initSegment;

        Xcp_FinalizeResPacket(0x03u, &Xcp_Internal.cto_response.pdu_info);
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

uint8 Xcp_DTOCmdStdCopyCalPage(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    const uint8 src_segment = pPduInfo->SduDataPtr[0x01u];
    const uint8 src_page = pPduInfo->SduDataPtr[0x02u];
    const uint8 dst_segment = pPduInfo->SduDataPtr[0x03u];
    const uint8 dst_page = pPduInfo->SduDataPtr[0x04u];
    uint8 error = 0x00u;

    *responseExpected = TRUE;

    if ((Xcp_SegmentIsValid(src_segment) == FALSE) || (Xcp_SegmentIsValid(dst_segment) == FALSE))
    {
        error = XCP_E_ASAM_SEGMENT_NOT_VALID;
    }
    else if ((Xcp_PageIsValid(src_segment, src_page) == FALSE) ||
             (Xcp_PageIsValid(dst_segment, dst_page) == FALSE))
    {
        error = XCP_E_ASAM_PAGE_NOT_VALID;
    }
    else if (Xcp_CopyCalPage(src_segment, src_page, dst_segment, dst_page) != E_OK)
    {
        /* XCP part 2 - Protocol Layer Specification 1.0/1.6.3.2.6
         * If calibration data page cannot be copied to the given destination, e.g. because the
         * location of destination is a flash segment, an ERR_WRITE_PROTECTED will be returned. */
        error = XCP_E_ASAM_WRITE_PROTECTED;
    }
    else
    {
        Xcp_Internal.cto_response.pdu_info.SduDataPtr[0x00u] = XCP_PID_RESPONSE;

        Xcp_FinalizeResPacket(0x01u, &Xcp_Internal.cto_response.pdu_info);
    }

    if (error != 0x00u)
    {
        Xcp_FillErrorPacket(error, &Xcp_Internal.cto_response.pdu_info);
    }

    return E_OK;
}

#endif /* #if (XCP_PAGING_SUPPORTED == STD_ON) */
