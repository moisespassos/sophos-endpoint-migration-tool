
import configparser as cp

ignore_policy_settings = {
    "threat-protection": [
        "endpoint.threat-protection.malware-protection.email-protection.attachment-file-types-blocking.enabled",
        "endpoint.threat-protection.malware-protection.skip-trusted-installers",
        "endpoint.threat-protection.malware-protection.deep-learning.detection-level",
        "endpoint.threat-protection.network-protection.connection-tracking.enabled",
        "endpoint.threat-protection.exploit-mitigation.all-mitigations.enabled"
    ],
    "server-threat-protection": [
        "endpoint.threat-protection.malware-protection.email-protection.attachment-file-types-blocking.enabled",
        "endpoint.threat-protection.malware-protection.skip-trusted-installers",
        "endpoint.threat-protection.malware-protection.deep-learning.detection-level",
        "endpoint.threat-protection.network-protection.connection-tracking.enabled",
        "endpoint.threat-protection.exploit-mitigation.all-mitigations.enabled"
    ]
}

class Config():

    config_file = "config/config.ini"

    def __init__(self) -> None:
        pass

    def get(self, param, section = "default"):

        config_file = cp.ConfigParser(allow_no_value=True)
        config_file.read(self.config_file)

        value = config_file.get(section, param)
        if any(value.lower() == f for f in ['no', 'n']): return False
        if any(value.lower() == f for f in ['yes', 'y']): return True
        
        return value
