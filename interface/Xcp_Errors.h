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
* @brief Command syntax invalid (see ASAM protocol layer specification 1.7.3.1)
*/
#define XCP_E_ASAM_CMD_SYNTAX (0x21u)

/**
* @brief Command syntax valid but command parameter(s) out of range (see ASAM protocol layer
 * specification 1.7.3.1)
 */
#define XCP_E_ASAM_OUT_OF_RANGE (0x22u)

#endif /* #ifndef XCP_ERRORS_H */
