import os
import json
import requests
from vendors.sophos_central.sophos_api_connector import CentralRequest

central = CentralRequest()

class Endpoint(object):

    headers = ""
    _request_page  = 1
    _endpoints_list = []
    _endpoints_ids  = []

    def setHeaders(self, headers):
        self.headers = headers

    # def _exec(self, method, url, headers, params = None):
    #     print("[*] - Starting {METHOD} on Sophos Central...".format(METHOD=method))

    #     try:
    #         res = None
    #         if method == "GET":
    #             res = requests.get(url, headers=headers, params=params)
    #         elif method == "POST":
    #             res = requests.post(url, headers=headers, json=params)

    #         res_code = res.status_code
    #         res_data = res.json()
    #         # print("[*] - HTTP Return code: %d" % (res_code))
        
    #     except requests.exceptions.HTTPError :
    #       pass

    #     if res_code > 201:
    #         res_users_error_code = res_data['error']
    #         print("\n[*] - Failed to perform this task")
    #         print("    - ERROR_CODE: %d" % (res_code))
    #         print("    - Error message: %s" % (res_users_error_code))
    #         print("    - URL: {URL}".format(URL=url))
    #         print("\n*******************************************************\n")
    #         exit()

    #     elif res_code == 200 or res_code == 201:
    #         return res_data
   
    def generate_ep_file(self, headers, job_folder):
        
        endpoints_url = "{DATA_REGION}/{ENDPOINTS_URI}".format(DATA_REGION=headers['source']['region'], ENDPOINTS_URI='/endpoint/v1/endpoints')    
        print("[*] - Generating a list of endpoints from Central...")
        endpoints_list, endpoints_ids = self._fetch_all_endpoints(headers, endpoints_url)

        endpoints_file = "./jobs/%s/origin_endpoints_%s.json" % (job_folder, headers['source']['headers']['X-Tenant-ID'])

        try:
            with open(endpoints_file, 'w') as outfile:
                json.dump(endpoints_list, outfile, indent=4)

        except IOError:
            print("[*] - Error while creating endpoints file.")

        print("[*] - List of endpoints generated to file: {EP_FILE}".format(EP_FILE=endpoints_file))

    def _generate_dump_file(self, tenant_headers, type, data, job_folder):

        # tenantFolder = tenant.TenantFolder(tenant_headers)

        print("[*] - Generating a list of {TYPE} from Central...".format(TYPE=type))

        dump_file = "./jobs/{FOLDERNAME}/{TENANT_ID}_{TYPE}.json".format(FOLDERNAME=job_folder, TENANT_ID=tenant_headers['X-Tenant-ID'], TYPE=type)

        print("[*] - Dumping data in the {FILE} file".format(FILE=dump_file))

        try:
            with open(dump_file, 'w') as outfile:
                json.dump(data, outfile, indent=4)
        except IOError:
            print("[*] - Error while creating {TYPE} file.".format(TYPE=type))
            return False

        print("[*] - List of {TYPE}s generated in the  file: {DUMP_FILE}".format(DUMP_FILE=dump_file, TYPE=type))
        return True

    def get_all_endpoints(self, headers, job_folder, use_generated_file = True):
        # def get_all_endpoints(self, tenant_headers, src_central_dataregion, use_generated_file = True):
        
        endpoints_file = "./jobs/%s/origin_endpoints_%s.json" % (job_folder, headers['headers']['X-Tenant-ID'])
        
        if os.path.exists(endpoints_file) and use_generated_file:
            print("[*] - Using previously generated file: %s" % (endpoints_file))
            with open(endpoints_file) as json_file:
                endpoints_json = json.load(json_file)
                endpoints_ids  = []
                for endpoint in endpoints_json:
                    endpoints_ids.append(endpoint['id'])
            return endpoints_json, endpoints_ids, "from_file"
        else:

            endpoints_url = "{DATA_REGION}/{ENDPOINTS_URI}".format(DATA_REGION=headers['region'], ENDPOINTS_URI='/endpoint/v1/endpoints')    
            
            print("[*] - Fetching endpoints from Sophos Central")
            endpoints_list, endpoints_ids = self._fetch_all_endpoints(headers['headers'], endpoints_url)
            return  endpoints_list, endpoints_ids, "from_central"
    
    def get_all_groups(self, headers, central_dataregion, job_folder):
        groups_list = list()
        endpoints_groups_url = "{DATA_REGION}/{GROUPS_URI}".format(DATA_REGION=central_dataregion, GROUPS_URI="endpoint/v1/endpoint-groups")
        groups_status, groups_data = central.get(endpoints_groups_url, headers)
        if groups_status:
            for x in groups_data['items']:
                if "description" in x.keys():
                    groups_list.append(x)
            self._generate_dump_file(headers, "groups", groups_data, job_folder)
            return groups_list


    def _fetch_all_endpoints(self, headers, endpoints_url):
        params_data = {}
        params_data["pageTotal"] = True
        # params_data["pageSize"]  = 2
        params_data["view"]      = 'basic'

        def append_endpoints(endpoints_url, headers, pageKey = ""):
            params_data["pageFromKey"] = pageKey

            try:
                res_endpoints = requests.get(endpoints_url, headers=headers['source']['headers'], params=params_data)
                res_endpoints_code = res_endpoints.status_code
                endpoints_data = res_endpoints.json()

            except requests.exceptions.RequestException as res_exception:
                res_endpoints_error_code = endpoints_data['error']
                return res_endpoints_error_code

            if res_endpoints_code == 200 or res_endpoints_code == 201 :
                for objEndpoint in endpoints_data['items']:
                    Endpoints_Dict = {}
                    Endpoints_Dict['id'] = objEndpoint['id']
                    Endpoints_Dict['TYPE'] = objEndpoint['type']
                    Endpoints_Dict['hostname'] = objEndpoint['hostname']

                    self._endpoints_list.append(Endpoints_Dict)
                    self._endpoints_ids.append(Endpoints_Dict['id'])
                
                try:
                    if endpoints_data['pages']['nextKey']:
                        self._request_page += 1
                        append_endpoints(endpoints_url, headers, endpoints_data['pages']['nextKey'])

                except:
                    pass

                return self._endpoints_list, self._endpoints_ids          

        return append_endpoints(endpoints_url, headers)
