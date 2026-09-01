/**
* @file Xcp_errors.h
* @author Guillaume Sottas
* @date 20/01/2022
*/

#ifndef XCP_ERRORS_H
#define XCP_ERRORS_H

/*------------------------------------------------------------------------------------------------*/
/* global definitions (#define).                                                                  */
/*------------------------------------------------------------------------------------------------*/

/**
* @brief Command processor synchronization (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_CMD_SYNCH (0x00u)

/**
* @brief Command was not executed (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_CMD_BUSY (0x10u)

/**
* @brief Command rejected because DAQ is running (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_DAQ_ACTIVE (0x11u)

/**
* @brief Command rejected because PGM is running (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_PGM_ACTIVE (0x12u)

/**
* @brief Unknown command or not implemented optional command (see ASAM protocol layer specification
* 1.7.3.1)
*/
#define XCP_E_ASAM_CMD_UNKNOWN (0x20u)

/**
* @brief Command syntax invalid (see ASAM protocol layer specification 1.7.3.1)
*/
#define XCP_E_ASAM_CMD_SYNTAX (0x21u)

/**
* @brief Command syntax valid but command parameter(s) out of range (see ASAM protocol layer
 * specification 1.7.3.1)
 */
#define XCP_E_ASAM_OUT_OF_RANGE (0x22u)

/**
* @brief Memory write protected (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_WRITE_PROTECTED (0x23u)

/**
* @brief Access denied (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_ACCESS_DENIED (0x24u)

/**
* @brief Access denied, Seed & Key is required (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_ACCESS_LOCKED (0x25u)

/**
* @brief Page not valid (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_PAGE_NOT_VALID (0x26u)

/**
* @brief Mode not valid (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_MODE_NOT_VALID (0x27u)

/**
* @brief Segment not valid (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_SEGMENT_NOT_VALID (0x28u)

/**
* @brief Sequence error (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_SEQUENCE (0x29u)

/**
* @brief DAQ configuration not valid (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_DAQ_CONFIG (0x2Au)

/**
* @brief Memory overflow (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_MEMORY_OVERFLOW (0x30u)

/**
* @brief Generic error (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_GENERIC (0x31u)

/**
* @brief Verify error (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_VERIFY (0x32u)

/**
* @brief Access to the requested resource is temporary not possible (see ASAM protocol layer
* specification 1.7.3.1). Introduced in version 1.1; absent from 1.0. Nothing in this module
* emits it, since it describes a condition only an integrator's callbacks can detect.
 */
#define XCP_E_ASAM_RESOURCE_TEMPORARY_NOT_ACCESSIBLE (0x33u)

#endif /* #ifndef XCP_ERRORS_H */
