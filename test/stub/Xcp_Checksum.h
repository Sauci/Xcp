/**
* @file Xcp_Checksum.h
* @author Guillaume Sottas
* @date 18/07/2022
*/

#ifndef XCP_CHECKSUM_H
#define XCP_CHECKSUM_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

#ifndef STD_TYPES_H
#include "Std_Types.h"
#endif /* #ifndef STD_TYPES_H */

/**
 * @brief Calculates the checksum on the provided address range.
 * @param [in] lowerAddress Lower address of the data range on which the checksum is calculated
 * @param [in] upperAddress Upper address of the data range on which the checksum is calculated
 * @param [out] pResult Pointer to the buffer where the calculated checksum will be stored
 * @returns The post-incremented MTA value.
 */
extern uint32 Xcp_UserDefinedChecksumFunction(uint32 lowerAddress, const uint32 upperAddress, uint32 *pResult);

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_CHECKSUM_H */
