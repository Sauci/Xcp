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

/**
 * @brief Reads a single byte form slave memory.
 * @param [in] pAddress Pointer to address location from where data must be read
 * @param [in] extension Address extension from where data must be read
 * @param [out] pBuffer Pointer to the buffer where the memory content will be stored
 */
extern void Xcp_ReadSlaveMemoryU8(void *pAddress, uint8 extension, uint8 *pBuffer);

/**
 * @brief Reads two bytes form slave memory.
 * @param [in] pAddress Pointer to address location from where data must be read
 * @param [in] extension Address extension from where data must be read
 * @param [out] pBuffer Pointer to the buffer where the memory content will be stored
 */
extern void Xcp_ReadSlaveMemoryU16(void *address, uint8 extension, uint8 *pBuffer);

/**
 * @brief Reads four bytes form slave memory.
 * @param [in] pAddress Pointer to address location from where data must be read
 * @param [in] extension Address extension from where data must be read
 * @param [out] pBuffer Pointer to the buffer where the memory content will be stored
 */
extern void Xcp_ReadSlaveMemoryU32(void *address, uint8 extension, uint8 *pBuffer);

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_MEMORY_ACCESS_H */
