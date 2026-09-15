/**
* @file Xcp_UserCmd.h
* @author Guillaume Sottas
* @date 21/07/2022
*/

#ifndef XCP_USER_CMD_H
#define XCP_USER_CMD_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

#include "Std_Types.h"

#include "ComStack_Types.h"

/**
 * @brief Handles a USER_CMD request (XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.12).
 * @param [in] pCtoPduInfo The request as received, including the USER_CMD PID in byte 0.
 * @param [out] pResErrPduInfo The response to transmit. Write the payload into SduDataPtr and set
 * SduLength to the number of bytes written, MAX_CTO included but never exceeded: 1.1/1.1.3.3 ends a
 * packet at MAX_CTO-1, and a longer response is discarded and answered ERR_GENERIC carrying
 * XCP_GENERIC_DETAIL_USER_CMD_RESPONSE_TOO_LONG regardless of this function's own return value --
 * a failure return does not exempt the buffer already written from the bound. Det then gets
 * XCP_E_USER_CMD_RESPONSE_TOO_LONG when the call itself succeeded, or this function's own error
 * otherwise.
 * @retval E_OK : Command executed successfully
 * @retval XCP_E_* : Command failed. If the DET module is enabled, this error will be reported to the DET
 */
extern uint8 Xcp_UserCmdFunction(const PduInfoType *pCtoPduInfo, PduInfoType *pResErrPduInfo);

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_USER_CMD_H */
