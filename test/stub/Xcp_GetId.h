/**
* @file Xcp_GetId.h
* @author Guillaume Sottas
* @date 11/09/2026
*/

#ifndef XCP_GET_ID_H
#define XCP_GET_ID_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

#include "Std_Types.h"

/**
 * @brief supplies GET_ID identification data for any identification type.
 * @param identificationType the Requested Identification Type from the GET_ID request: 0..4 or
 * 128..255 (XCP part 2 - Protocol Layer Specification 1.1/1.6.1.2.2). 5..127 are refused before
 * this is called.
 * @param pIdentification set to the address the master will UPLOAD the identification from.
 * @param pExtension set to the MTA address extension that address is reached through.
 * @param pLength set to the identification's length in bytes.
 * @retval E_OK : all three out-parameters are set; the requested type is served.
 * @retval E_NOT_OK : this slave does not serve the requested type. Not an error: it answers
 * Length = 0.
 */
extern Std_ReturnType Xcp_GetIdentificationFunction(uint8 identificationType,
                                                    const void **pIdentification,
                                                    uint8 *pExtension,
                                                    uint32 *pLength);

#ifdef __cplusplus
}

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_GET_ID_H */
