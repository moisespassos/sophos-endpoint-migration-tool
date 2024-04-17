import json
from vendors.sophos_central.sophos_api_connector import CentralRequest

central = CentralRequest()

class Firewalls(object):
    
    def migrate_groups(self, headers):
        
        firewall_groups_url = "/firewall/v1/firewall-groups"
        source_url = "{DATA_REGION}/{SETTING_URI}".format(DATA_REGION=headers['source']['region'], SETTING_URI=firewall_groups_url)
        destination_url = "{DATA_REGION}/{SETTING_URI}".format(DATA_REGION=headers['destination']['region'], SETTING_URI=firewall_groups_url)
        
        status, fw_groups = central.get(source_url, headers['source']['headers'])
        print(json.dumps(fw_groups, indent=4))
       