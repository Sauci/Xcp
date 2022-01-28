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
* @brief Access denied, Seed & Key is required (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_ACCESS_LOCKED (0x25u)

/**
* @brief Sequence error (see ASAM protocol layer specification 1.7.3.1)
 */
#define XCP_E_ASAM_SEQUENCE (0x29u)

#endif /* #ifndef XCP_ERRORS_H */
