#ifndef UXPLAY_WINDOWS_DNS_SD_H
#define UXPLAY_WINDOWS_DNS_SD_H

#include <stdint.h>

typedef struct _DNSServiceRef_t *DNSServiceRef;
typedef union _TXTRecordRef_t {
    char PrivateData[16];
    char *ForceNaturalAlignment;
} TXTRecordRef;

typedef uint32_t DNSServiceFlags;
typedef int32_t DNSServiceErrorType;

#define kDNSServiceErr_NoError 0
#define kDNSServiceErr_Unknown -65537
#define kDNSServiceErr_NameConflict -65548

#endif
