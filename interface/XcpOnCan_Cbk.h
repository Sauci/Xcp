/**
 * @file XcpOnCan_Cbk.h
 * @author Guillaume Sottas
 * @date 15/01/2018
 *
 * @defgroup XCP_CBK notifications
 * @ingroup XCP
 *
 * @brief notifications provided by CAN transport layer.
 *
 * @defgroup XCP_CBK_GCFDECL global callback function declarations
 * @ingroup XCP_CBK
 */

#ifndef XCPONCAN_CBK_H
#define XCPONCAN_CBK_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

/*------------------------------------------------------------------------------------------------*/
/* included files (#include).                                                                     */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_CBK
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global callback function declarations.                                                         */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_CBK_GCFDECL
 * @{
 */

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/**
 * @brief indication of a received PDU from a lower layer communication interface module.
 * @param [in] rxPduId ID of the received PDU.
 * @param [in] pPduInfo contains the length (SduLength) of the received PDU, a pointer to a buffer
 * (SduDataPtr) containing the PDU, and the MetaData related to this PDU
 */
void Xcp_CanIfRxIndication(PduIdType rxPduId, const PduInfoType *pPduInfo);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/**
 * @brief the lower layer communication interface module confirms the transmission of a PDU, or the
 * failure to transmit a PDU.
 * @param [in] txPduId ID of the PDU that has been transmitted
 * @param [in] result E_OK: the PDU was transmitted, E_NOT_OK: transmission of the PDU failed
 */
void Xcp_CanIfTxConfirmation(PduIdType txPduId, Std_ReturnType result);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/**
 * @brief within this API, the upper layer module (called module) shall check whether the available
 * data fits into the buffer size reported by PduInfoPtr->SduLength. If it fits, it shall copy its
 * data into the buffer provided by PduInfoPtr->SduDataPtr and update the length of the actual
 * copied data in PduInfoPtr->SduLength. If not, it returns E_NOT_OK without changing PduInfoPtr.
 * @param [in] txPduId ID of the SDU that is requested to be transmitted
 * @param [in/out] pPduInfo contains a pointer to a buffer (SduDataPtr) to where the SDU data shall
 * be copied, and the available buffer size in SduLength. On return, the service will indicate the
 * length of the copied SDU data in SduLength
 * @retval E_OK: SDU has been copied and SduLength indicates the number of copied bytes
 * @retval E_NOT_OK: No SDU data has been copied. PduInfoPtr must not be used since it may contain a
 * NULL pointer or point to invalid data.
 */
Std_ReturnType Xcp_CanIfTriggerTransmit(PduIdType txPduId, PduInfoType* pPduInfo);


#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/** @} */

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCPONCAN_CBK_H */
