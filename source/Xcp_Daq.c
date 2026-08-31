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

uint8 Xcp_DTODaqStimPacket(boolean *responseExpected, const PduInfoType *pPduInfo)
{
    (void)pPduInfo;

    *responseExpected = TRUE;

    return E_OK;
}

