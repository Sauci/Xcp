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

#ifndef STD_TYPES_H
#include "Std_Types.h"
#endif /* #ifndef STD_TYPES_H */

#ifndef COMSTACK_TYPES_H
#include "ComStack_Types.h"
#endif /* #ifndef COMSTACK_TYPES_H */

/**
 * @brief Calculates the checksum on the provided address range.
 * @param [in] pCtoPduInfo Lower address of the data range on which the checksum is calculated
 * @param [out] pResErrPduInfo Upper address of the data range on which the checksum is calculated
 * @retval E_OK : Command executed successfully
 * @retval XCP_E_* : Command failed. If the DET module is enabled, this error will be reported to the DET
 */
extern uint8 Xcp_UserCmdFunction(const PduInfoType *pCtoPduInfo, PduInfoType *pResErrPduInfo);

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_USER_CMD_H */
