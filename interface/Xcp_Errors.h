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
* specification 1.7.3.1). Introduced in version 1.1; absent from 1.0. Emitted by
* Xcp_CTOCmdStdGetStatus (source/Xcp_Std.c) while design doc DD101's start-up read of the session
* configuration id is still outstanding (docs/superpowers/specs/2026-09-09-xcp-daq-nv-storage-
* design.md) -- a condition only an integrator's own Xcp_ReadStoredSessionConfigurationId callback
* can resolve, which is why the module can only report it, not shorten it.
 */
#define XCP_E_ASAM_RESOURCE_TEMPORARY_NOT_ACCESSIBLE (0x33u)

/*------------------------------------------------------------------------------------------------*/
/* Detail codes for ERR_GENERIC's extended payload.                                               */
/*                                                                                                */
/* NOT ASAM-DEFINED. Everything above this fence is a code the specification names and numbers.   */
/* These are not: XCP part 2 - Protocol Layer Specification 1.1/1.1.3.3 says only that an         */
/* ERR_GENERIC packet "contains an implementation specific slave device error code as WORD as     */
/* additional information", leaving the value to whoever writes the slave. This module is that    */
/* implementation, and these are its values. A master decodes them against THIS header, not       */
/* against the specification. Design doc DD121-DD124,                                             */
/* docs/superpowers/specs/2026-09-15-xcp-err-generic-detail-design.md.                            */
/*                                                                                                */
/* 0x0000 is reserved and never emitted, so a zeroed or stale buffer cannot decode as a valid     */
/* detail code (DD123, the same reasoning as protocol_layer.checksum_max_block_size's minimum     */
/* of 1).                                                                                         */
/*------------------------------------------------------------------------------------------------*/

/**
* @brief UNLOCK: the integrator's Xcp_CalcKey returned E_NOT_OK, so no key could be computed at
* all. Distinct from ERR_ACCESS_LOCKED, which asserts the key was WRONG.
 */
#define XCP_GENERIC_DETAIL_KEY_CALCULATION_FAILED (0x0001u)

/**
* @brief PROGRAM_START: a programming session is already active (pgm_state is not XCP_PGM_IDLE).
* Refused by this module's own state gate, not by the integrator.
 */
#define XCP_GENERIC_DETAIL_PROGRAMMING_ALREADY_ACTIVE (0x0002u)

/**
* @brief PROGRAM_START: the integrator's Xcp_ProgramStart reported a non-zero status code, i.e. a
* slave that cannot permit programming (XCP part 2 - Protocol Layer Specification 1.1/1.6.5.1.1).
 */
#define XCP_GENERIC_DETAIL_PROGRAM_START_FAILED (0x0003u)

/**
* @brief PROGRAM_RESET: the integrator's Xcp_ProgramReset reported a non-zero status code.
 */
#define XCP_GENERIC_DETAIL_PROGRAM_RESET_FAILED (0x0004u)

/**
* @brief PROGRAM_PREPARE: the integrator's Xcp_ProgramPrepare reported a non-zero status code, i.e.
* target memory that is not "in a operational state which permits the download of code" (XCP part 2
* - Protocol Layer Specification 1.1/1.6.5.2.3).
 */
#define XCP_GENERIC_DETAIL_PROGRAM_PREPARE_FAILED (0x0005u)

#endif /* #ifndef XCP_ERRORS_H */
