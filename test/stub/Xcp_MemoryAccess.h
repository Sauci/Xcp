/**
* @file Xcp_SeedKey.h
* @author Guillaume Sottas
* @date 27/01/2022
*/

#ifndef XCP_MEMORY_ACCESS_H
#define XCP_MEMORY_ACCESS_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

#ifndef STD_TYPES_H
#include "Std_Types.h"
#endif /* #ifndef STD_TYPES_H */

extern void Xcp_ReadSlaveMemoryU8(uint32 address, uint8 extension, uint8 *pBuffer);

extern void Xcp_ReadSlaveMemoryU16(uint32 address, uint8 extension, uint8 *pBuffer);

extern void Xcp_ReadSlaveMemoryU32(uint32 address, uint8 extension, uint8 *pBuffer);

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_MEMORY_ACCESS_H */
