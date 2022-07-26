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
 * @param [in] pLowerAddress Pointer to lower address of the data range on which the checksum is calculated
 * @param [in] pUpperAddress Pointer to upper address of the data range on which the checksum is calculated
 * @param [out] pResult Pointer to the buffer where the calculated checksum will be stored
 * @returns The post-incremented MTA value.
 */
extern void *Xcp_UserDefinedChecksumFunction(void *pLowerAddress, const void *pUpperAddress, uint32 *pResult);

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_CHECKSUM_H */
