/**
* @file Xcp_SeedKey.h
* @author Guillaume Sottas
* @date 27/01/2022
*/

#ifndef XCP_SEED_KEY_H
#define XCP_SEED_KEY_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

#ifndef STD_TYPES_H
#include "Std_Types.h"
#endif /* #ifndef STD_TYPES_H */

/**
 * @brief Generates a random seed.
 * @param [out] pSeedBuffer Pointer to the buffer where the generated seed will be stored
* @param [in] maxSeedLength Maximum length of the seed the caller can handle. This value depends of
*     the size of the buffer in the XCP stack
 * @param [out] pSeedLength Pointer to the seed length of the generated seed. This value should
 *     never be greater than the maxSeedLength parameter
 * @retval E_OK : The seed has been successfully generated
 * @retval E_NOT_OK : The seed has not been successfully generated, or the seed length is greater
 *     than the specified maximum seed length
 */
extern Std_ReturnType Xcp_GetSeed(uint8 *pSeedBuffer,
                                  const uint16 maxSeedLength,
                                  uint16 *pSeedLength);

/**
 * @brief Calculates the key for the provided seed.
* @param [in] pSeedBuffer Pointer to the buffer containing the input seed
* @param [in] seedLength Length of the provided input seed
* @param [out] pKeyBuffer Pointer to the buffer where the calculated key will be stored
 * @param [in] maxKeyLength Maximum length of the key the caller can handle. This value depends of
 *     the size of the buffer in the XCP stack
 * @param [out] pKeyLength Pointer to the key length of the calculated key. This value should never
 *     be greater than the maxKeyLength parameter
 * @retval E_OK : The key has been successfully calculated
 * @retval E_NOT_OK : The key has not been successfully generated, or the key length is greater
 *     than the specified maximum key length
 *
 * @link https://support.vector.com/kb?id=kb_article_view&sysparm_article=KB0011313&sys_kb_id=35e40ea41b2614148e9a535c2e4bcb28&spa=1
 */
extern Std_ReturnType Xcp_CalcKey(const uint8 *pSeedBuffer,
                                  const uint16 seedLength,
                                  uint8* pKeyBuffer,
                                  const uint16 maxKeyLength,
                                  uint16 *pKeyLength);

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_SEED_KEY_H */
