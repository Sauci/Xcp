/**
 * @file Xcp_Daq.c
 * @author
 * @date
 *
 * @defgroup XCP_DAQ_C DATA ACQUISITION AND STIMULATION command group implementation
 * @ingroup XCP
 */

#include "Xcp_Internal.h"

/*------------------------------------------------------------------------------------------------*/
/* local function definitions (static).                                                           */
/*------------------------------------------------------------------------------------------------*/

uint8 Xcp_DTOCmdDaqAllocOdtEntry(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqAllocOdt(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqAllocDaq(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqFreeDaq(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqGetDaqEventInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqGetDaqListInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqGetDaqResolutionInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqGetDaqProcessorInfo(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqReadDaq(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqGetDaqClock(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqStartStopSynch(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqStartStopDaqList(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqGetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqSetDaqListMode(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqWriteDaq(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqSetDaqPtr(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTOCmdDaqClearDaqList(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTODaqStimPacket(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

uint8 Xcp_DTODaqPacket(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}
