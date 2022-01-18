/**
 * @file Xcp_Cfg.h
 * @author Guillaume Sottas
 * @date 10/12/2021
 */

#ifndef XCP_CFG_H
#define XCP_CFG_H

/* SWS_BSW_00059 */
#ifndef XCP_AR_RELEASE_MAJOR_VERSION
#error unknown AUTOSAR release major version
#elif (XCP_AR_RELEASE_MAJOR_VERSION != 4)
#error incompatible AUTOSAR release major version
#endif

/* SWS_BSW_00059 */
#ifndef XCP_AR_RELEASE_MINOR_VERSION
#error unknown AUTOSAR release minor version
#elif (XCP_AR_RELEASE_MINOR_VERSION != 3)
#error incompatible AUTOSAR release minor version
#endif

#endif /* #ifndef XCP_CFG_H */
