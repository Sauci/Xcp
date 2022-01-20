/**
 * @file Xcp.h
 * @author Guillaume Sottas
 * @date 15/01/2018
 *
 * @defgroup XCP CAN transport layer
 *
 * @defgroup XCP_H_GDEF identification informations
 * @ingroup XCP_H
 * @defgroup XCP_H_E errors classification
 * @ingroup XCP_H
 * @defgroup XCP_H_E_D development errors
 * @ingroup XCP_H_E
 * @defgroup XCP_H_E_R runtime errors
 * @ingroup XCP_H_E
 * @defgroup XCP_H_E_T transient faults
 * @ingroup XCP_H_E
 * @defgroup XCP_H_GTDEF global data type definitions
 * @ingroup XCP_H
 * @defgroup XCP_H_EFDECL external function declarations
 * @ingroup XCP_H
 * @defgroup XCP_H_GCDECL global constant declarations
 * @ingroup XCP_H
 * @defgroup XCP_H_GVDECL global variable declarations
 * @ingroup XCP_H
 * @defgroup XCP_H_GFDECL global function declarations
 * @ingroup XCP_H
 * @defgroup XCP_H_GSFDECL global scheduled function declarations
 * @ingroup XCP_H
 */

#ifndef XCP_H
#define XCP_H

#ifdef __cplusplus

extern "C" {

#endif /* #ifdef __cplusplus */

/*------------------------------------------------------------------------------------------------*/
/* included files (#include).                                                                     */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H
 * @{
 */

#include "Xcp_Types.h"

#if defined(CFFI_ENABLE)

/**
 * @brief if CFFI_ENABLE is defined, expose the Xcp callback function to CFFI module as well as
 * the external functions.
 */
#include "XcpOnCan_Cbk.h"

#ifndef CANIF_H

#include "CanIf.h"

#endif /* #ifndef CANIF_H */

#if (XCP_DEV_ERROR_DETECT == STD_ON)

#include "Det.h"

#endif /* #if (XCP_DEV_ERROR_DETECT == STD_ON) */

#endif /* #if defined(CFFI_ENABLE) */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global data type definitions (typedef, struct).                                                */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GTDEF
 * @{
 */

typedef enum {
    XCP_UNINITIALIZED = 0x00u,
    XCP_INITIALIZED,
} Xcp_StateType;

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global definitions (#define).                                                                  */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GDEF
 * @{
 */

/**
 * @brief unique identifier of the XCP driver.
 * @note this value corresponds to document ID of corresponding Autosar software specification.
 */
#define XCP_MODULE_ID (0xFFu)

#ifndef XCP_SW_MAJOR_VERSION

/**
 * @brief XCP driver major version number.
 */
#define XCP_SW_MAJOR_VERSION (0x00u)

#endif /* #ifndef XCP_SW_MAJOR_VERSION */

#ifndef XCP_SW_MINOR_VERSION

/**
 * @brief XCP driver minor version number.
 */
#define XCP_SW_MINOR_VERSION (0x01u)

#endif /* #ifndef XCP_SW_MINOR_VERSION */

#ifndef XCP_SW_PATCH_VERSION

/**
 * @brief XCP driver patch version number.
 */
#define XCP_SW_PATCH_VERSION (0x00u)

#endif /* #ifndef XCP_SW_PATCH_VERSION */

/**
 * @brief @ref Xcp_Init API ID.
 */
#define XCP_INIT_API_ID (0x00u)

/**
 * @brief @ref Xcp_GetVersionInfo API ID.
 */
#define XCP_GET_VERSION_INFO_API_ID (0x01u)

/**
 * @brief @ref Xcp_SetTransmissionMode API ID.
 */
#define XCP_SET_TRANSMISSION_MODE_API_ID (0x05u)

/**
 * @brief @ref Xcp_MainFunction API ID.
 */
#define XCP_MAIN_FUNCTION_API_ID (0x04u)

/**
 * @brief @ref Xcp_MainFunction API ID.
 */
#define XCP_CAN_IF_RX_INDICATION_API_ID (0x42u)

/** @} */

/**
 * @addtogroup XCP_H_E_D
 * @{
 */

/**
 * @brief Module not initialized.
 */
#define XCP_E_UNINIT (0x02u)

/**
 * @brief Initialization of XCP failed.
 */
#define XCP_E_INIT_FAILED (0x04u)

/**
 * @brief Null pointer has been passed as an argument.
 */
#define XCP_E_PARAM_POINTER (0x12u)

/**
 * @brief API call with wrong PDU ID.
 */
#define XCP_E_INVALID_PDUID (0x03u)

/** @} */

/**
 * @addtogroup XCP_H_E_R
 * @{
 */

/** @} */

/**
 * @addtogroup XCP_H_E_T
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* external function declarations (extern).                                                       */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_EFDECL
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global constant declarations (extern const).                                                   */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GCDECL
 * @{
 */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global variable declarations (extern).                                                         */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GVDECL
 * @{
 */

#ifdef CFFI_ENABLE

extern Xcp_StateType Xcp_State;

extern const Xcp_Type *Xcp_Ptr;

#endif /* #ifndef CFFI_ENABLE */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global function declarations.                                                                  */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GFDECL
 * @{
 */

#define Xcp_START_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

/**
 * @brief this service initializes interfaces and variables of the AUTOSAR XCP layer.
 * @param [in] pConfig pointer to a selected configuration structure
 */
void Xcp_Init(const Xcp_Type *pConfig);

#define Xcp_STOP_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

#if (XCP_GET_VERSION_INFO_API == STD_ON)

#define Xcp_START_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

/**
 * @brief returns the version information of this module.
 * @param [out] pVersionInfo pointer to where to store the version information of this module
 */
void Xcp_GetVersionInfo(Std_VersionInfoType *pVersionInfo);

#define Xcp_STOP_SEC_CODE_SLOW
#include "Xcp_MemMap.h"

#endif /* #if (XCP_GET_VERSION_INFO_API == STD_ON) */

#if (XCP_SUPPRESS_TX_SUPPORT == STD_ON)

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/**
 * @brief this API is used to turn on and off of the TX capabilities of used communication bus
 * channel in XCP module.
 * @param [in] channel the Network channel for the used bus communication
 * @param [in] mode enabled or disabled Transmission mode Parameters
 */
void Xcp_SetTransmissionMode(NetworkHandleType channel, Xcp_TransmissionModeType mode);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

#endif /* #if (XCP_SUPPRESS_TX_SUPPORT == STD_ON) */

/** @} */

/*------------------------------------------------------------------------------------------------*/
/* global scheduled function declarations.                                                        */
/*------------------------------------------------------------------------------------------------*/

/**
 * @addtogroup XCP_H_GSFDECL
 * @{
 */

#define Xcp_START_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/**
 * @brief the main function for scheduling the CAN TP.
 */
void Xcp_MainFunction(void);

#define Xcp_STOP_SEC_CODE_FAST
#include "Xcp_MemMap.h"

/** @} */

#ifdef __cplusplus
};

#endif /* #ifdef __cplusplus */

#endif /* #ifndef XCP_H */
