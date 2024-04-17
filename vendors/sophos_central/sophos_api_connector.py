import sys
import json
import requests
from os import path
import configparser as cp
from time import sleep, time
from datetime import datetime

from config import Config

config = Config()

sys.path.append('../../')

class CentralRequest(object):
    def __init__(self) -> None:
        self.requests_count = 0
        self.request_time   = datetime.now()

    def rate_limit_control(self):
        # For future implementations
        # backoff = random_between(0, min(cap, base * (2 ** attempt)))
        
        adjust_time = False
        cur_request_time = datetime.now()        
        time_lapsed = (cur_request_time - self.request_time)
        self.requests_count += 1

        # print("\n[*] - Rate control. Count: %d" % (self.requests_count))
        # print("[*] - Time control: %d  - %s\n" % (time_lapsed.seconds, str(datetime.now())))

        if (self.requests_count % 1000 == 0 ) and (time_lapsed.seconds <= 3600):
            # print(" ------ Waiting 60 seconds for the next request")
            wait_seconds = 60
        elif (self.requests_count % 100 == 0) and (time_lapsed.seconds <= 60):
            # print(" ------ Waiting 20 seconds for the next request")
            wait_seconds = 20
        elif (self.requests_count >= 9 ) and (time_lapsed.seconds <= 10):
            # print(" ------ Waiting 2 seconds for the next request")
            wait_seconds = 2

        if adjust_time:
            print("[*] - Script has reached Sophos Central rate limits.")
            print("[*] - Waiting {SECONDS} to continue.".format(SECONDS=str(wait_seconds)))

            sleep(wait_seconds)
            self.request_time = datetime.now()
            return True


        return False

    def get(self, url, headers, params = None):
        # print("HEADERS - GET")
        # print(headers)
        # print(url)
        # print(params)
        return self._exec("GET", url, headers, params)

    def insert(self, url, headers, params = None):
        return self._exec("POST", url, headers, params)
   
    def put(self, url, headers, params = None):
        return self._exec("PUT", url, headers, params)

    def update(self, url, headers, params = None):
        return self._exec("PATCH", url, headers, params)

    def _exec(self, method, url, headers, params = None):
        force_run_again = True

        while force_run_again:
            # print("\n\n\n\n")
            # print("HEadersss")
            # print(headers)
            # sleep(10)
            
            # Requesting rate limit control
            self.rate_limit_control()

            if config.get("debug"):
                print("[*] - Starting {METHOD} request on Sophos Central...".format(METHOD=method))
                print("[*] - Sophos Central Tenant: {TENANT}".format(TENANT=headers['X-Tenant-ID']))

            # print(json.dumps(headers, indent=4))
            # print(json.dumps(params, indent=4))

            try:
                res = None
                if method == "GET":
                    params_data = {}
                    params_data["pageTotal"] = True
                    params_data["pageSize"]  = 2
                    # params_data["view"]      = 'basic'
                    res = requests.get(url, headers=headers, params=params)
                elif method == "POST":
                    res = requests.post(url, headers=headers, json=params)
                elif method == "PATCH":
                    res = requests.patch(url, headers=headers, json=params)
                elif method == "PUT":
                    res = requests.put(url, headers=headers, json=params)
                else:
                    print("[!] - Method not found")
                    print("[!] - Aborting execution.")
                    exit()

                res_code = res.status_code
                res_data = res.json()
                # print("[*] - HTTP Return code: %d" % (res_code))
            
            except requests.exceptions.HTTPError :
                pass

            if res_code == 429:
                print("\n[!] - Failed to perform this task")
                print("    - Rate limit reached.")
                print("    - Please check KB: https://developer.sophos.com/intro#rate-limits")
                print("[-] - Waiting 30 seconds after trying again...")
                if config.get("debug"):
                    print("    - HTTP Code: %d"     % (res_code))
                    print("    - Error message: %s" % (res_data['message']))
                sleep(30)
            elif res_code > 201:
                # print(res_data)
                res_users_error_code = res_data['error']
                res_data['status_code'] = res_code
                print("\n[!] - Failed to perform this task")
                print("    - HTTP Code: %d"     % (res_code))
                print("    - Error message: %s" % (res_data['message']))
                
                if config.get("debug"):
                    # print("\n*******************************************************\n")
                    print("    - Error Code: %s"    % (res_users_error_code))
                    print("    - URL: {URL}".format(URL=url))
                    print(json.dumps(res_data, indent=4))
                    print("\n*******************************************************\n")
                # exit(1)
                return False, res_data
            elif res_code == 200 or res_code == 201:
                return True, res_data

class Auth(object):
    auth_url = 'https://id.sophos.com/api/v2/oauth2/token'
    whoami_url = 'https://api.central.sophos.com/whoami/v1'
    # auth_url = api_conf.auth_uri
    # whoami_url = api_conf.whoami_uri

    def get_file_location(self, process_path):
        dir_name = path.dirname(path.abspath(__file__))
        final_path = "{0}{1}".format(dir_name, process_path)
        return final_path

        
    def load_credentials(self, sophos_final_path, section, parameter):
        sophos_conf = cp.ConfigParser(allow_no_value=True)
        sophos_conf.read(sophos_final_path)
        return sophos_conf.get(section, parameter)


    def get_token(self, client_id, client_secret, self_url):
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data_tok = "grant_type=client_credentials&client_id={0}&client_secret={1}&scope=token".format(client_id,
                                                                                                          client_secret)
            res = requests.post(self_url, headers=headers, data=data_tok)
            res_code = res.status_code
            res_data = res.json()
            if res_code == 200:
                sophos_access_token = res_data['access_token']
                return sophos_access_token
            else:
                res_error_code = res_data['errorCode']
                res_message = "Response Code: {0} Message: {1}".format(res_code, res_data['message'])
                return None, res_message, res_error_code
        

    def valid_headers(self, sophos_access_token):
            if sophos_access_token[0] is not None:
                headers = {"Authorization": "Bearer {0}".format(sophos_access_token), "Accept": "application/json"}
                return headers
            else:
                exit(1)

    def get_tentant(self, headers, whoami_url):
            try:
                res_tenant = requests.get(whoami_url, headers=headers)
                res_tenant_code = res_tenant.status_code
                tenant_data = res_tenant.json()
            except requests.exceptions.RequestException as res_exception:
                print("Failed to obtain the tenant ID")
                res_tenant_error_code = tenant_data['error']
                print(res_exception)
                print("Err Code: {0}, Err Detail: {1}".format(res_tenant_code, res_tenant_error_code))
                exit(1)
            if res_tenant_code == 200:
                return tenant_data

    # @mwt(timeout=60*60)
    def get_headers(self, tenant_credentials):
        credentials_path = config.get("credentials_path")
        credentials_path = ("%s%s") % ("/../..", credentials_path)
        credentails_real_path = self.get_file_location(credentials_path)
        sophos_client_id = self.load_credentials(credentails_real_path, tenant_credentials, "client_id")
        sophos_client_secret = self.load_credentials(credentails_real_path, tenant_credentials, "client_secret")
        
        sophos_access_token = self.get_token(sophos_client_id, sophos_client_secret, self.auth_url)
        tenant_headers = self.valid_headers(sophos_access_token)
        tenant_data = self.get_tentant(tenant_headers, self.whoami_url)
        central_dataregion = tenant_data["apiHosts"]["dataRegion"]
        tenant_headers["X-Tenant-ID"] = tenant_data['id']
        
        return tenant_headers, central_dataregion