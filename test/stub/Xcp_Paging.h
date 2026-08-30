/**
 * @file Xcp_Paging.h
 *
 * @brief calibration page switching callbacks, to be implemented by the integrator.
 */

#ifndef XCP_PAGING_H
#define XCP_PAGING_H

#ifdef __cplusplus
extern "C" {
#endif /* #ifdef __cplusplus */

#ifndef STD_TYPES_H
#include "Std_Types.h"
#endif /* #ifndef STD_TYPES_H */

/**
 * @brief activates a calibration page for the given access mode.
 * @param [in] segment logical data segment number
 * @param [in] page logical data page number
 * @param [in] mode 0x01 = ECU access, 0x02 = XCP access
 * @retval E_OK the page has been activated
 * @retval E_NOT_OK the page cannot be set to the given mode; ERR_MODE_NOT_VALID is returned
 */
extern Std_ReturnType Xcp_SetCalPage(uint8 segment, uint8 page, uint8 mode);

/**
 * @brief reports the calibration page currently active for the given access mode.
 * @param [in] segment logical data segment number
 * @param [in] mode 0x01 = ECU access, 0x02 = XCP access
 * @param [out] pPage receives the logical data page number; untouched when E_NOT_OK is returned
 * @retval E_OK pPage has been written
 * @retval E_NOT_OK no page is active for that mode; ERR_MODE_NOT_VALID is returned
 */
extern Std_ReturnType Xcp_GetCalPage(uint8 segment, uint8 mode, uint8 *pPage);

/**
 * @brief copies one calibration page onto another.
 * @retval E_OK the page has been copied
 * @retval E_NOT_OK the destination cannot be written; ERR_WRITE_PROTECTED is returned
 */
extern Std_ReturnType Xcp_CopyCalPage(uint8 srcSegment, uint8 srcPage, uint8 dstSegment, uint8 dstPage);

#ifdef __cplusplus
}
#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_PAGING_H */
