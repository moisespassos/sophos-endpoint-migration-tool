import os
import json
import requests
from vendors.sophos_central.sophos_api_connector import CentralRequest

central = CentralRequest()


class Endpoint(object):

    def _init_(self):
        self.headers = ""
        self._request_page = 1
        self._endpoints_list = []
        self._endpoints_ids = []

    def setHeaders(self, headers):
        self.headers = headers

    def generate_ep_file(self, headers, job_folder):
        endpoints_url = "{DATA_REGION}/{ENDPOINTS_URI}".format(
            DATA_REGION=headers['source']['region'],
            ENDPOINTS_URI='/endpoint/v1/endpoints'
        )

        print("[*] - Generating a list of endpoints from Central...")

        endpoints_list, endpoints_ids = self._fetch_all_endpoints(
            headers['source']['headers'],
            endpoints_url
        )

        endpoints_file = "./jobs/%s/origin_endpoints_%s.json" % (
            job_folder,
            headers['source']['headers']['X-Tenant-ID']
        )

        try:
            with open(endpoints_file, 'w') as outfile:
                json.dump(endpoints_list, outfile, indent=4)
        except IOError:
            print("[*] - Error while creating endpoints file.")
            return False

        print("[*] - List of endpoints generated to file: {EP_FILE}".format(EP_FILE=endpoints_file))
        return True

    def _generate_dump_file(self, tenant_headers, type, data, job_folder):
        print("[*] - Generating a list of {TYPE} from Central...".format(TYPE=type))

        dump_file = "./jobs/{FOLDERNAME}/{TENANT_ID}_{TYPE}.json".format(
            FOLDERNAME=job_folder,
            TENANT_ID=tenant_headers['X-Tenant-ID'],
            TYPE=type
        )

        print("[*] - Dumping data in the {FILE} file".format(FILE=dump_file))

        try:
            with open(dump_file, 'w') as outfile:
                json.dump(data, outfile, indent=4)
        except IOError:
            print("[*] - Error while creating {TYPE} file.".format(TYPE=type))
            return False

        print("[*] - List of {TYPE}s generated in the file: {DUMP_FILE}".format(
            DUMP_FILE=dump_file,
            TYPE=type
        ))
        return True

    def get_all_endpoints(self, headers, job_folder, use_generated_file=True):
        endpoints_file = "./jobs/%s/origin_endpoints_%s.json" % (
            job_folder,
            headers['headers']['X-Tenant-ID']
        )

        if os.path.exists(endpoints_file) and use_generated_file:
            print("[*] - Using previously generated file: %s" % endpoints_file)

            with open(endpoints_file) as json_file:
                endpoints_json = json.load(json_file)

            endpoints_ids = []
            for endpoint in endpoints_json:
                endpoints_ids.append(endpoint['id'])

            return endpoints_json, endpoints_ids, "from_file"

        endpoints_url = "{DATA_REGION}/{ENDPOINTS_URI}".format(
            DATA_REGION=headers['region'],
            ENDPOINTS_URI='/endpoint/v1/endpoints'
        )

        print("[*] - Fetching endpoints from Sophos Central")
        endpoints_list, endpoints_ids = self._fetch_all_endpoints(
            headers['headers'],
            endpoints_url
        )

        return endpoints_list, endpoints_ids, "from_central"

    def get_all_groups(self, headers, central_dataregion, job_folder):
        groups_list = list()
        endpoints_groups_url = "{DATA_REGION}/{GROUPS_URI}".format(
            DATA_REGION=central_dataregion,
            GROUPS_URI="endpoint/v1/endpoint-groups"
        )

        groups_status, groups_data = central.get(endpoints_groups_url, headers)

        if groups_status:
            for x in groups_data['items']:
                if "description" in x.keys():
                    groups_list.append(x)

            self._generate_dump_file(headers, "groups", groups_data, job_folder)
            return groups_list

    def _fetch_all_endpoints(self, headers, endpoints_url):
        self._request_page = 1
        self._endpoints_list = []
        self._endpoints_ids = []

        params_data = {
            "pageTotal": True,
            "view": "basic"
        }

        def append_endpoints(page_key=""):
            if page_key:
                params_data["pageFromKey"] = page_key
            elif "pageFromKey" in params_data:
                del params_data["pageFromKey"]

            try:
                res_endpoints = requests.get(
                    endpoints_url,
                    headers=headers,
                    params=params_data
                )

                res_endpoints_code = res_endpoints.status_code

                try:
                    endpoints_data = res_endpoints.json()
                except ValueError:
                    print("[!] - Sophos Central returned a non-JSON response.")
                    print("[!] - HTTP Return code: %d" % res_endpoints_code)
                    return [], []

            except requests.exceptions.RequestException as error:
                print("[!] - Error while fetching endpoints from Sophos Central.")
                print("[!] - Error: %s" % error)
                return [], []

            if res_endpoints_code not in [200, 201]:
                print("[!] - Failed to fetch endpoints from Sophos Central.")
                print("[!] - HTTP Return code: %d" % res_endpoints_code)
                print(json.dumps(endpoints_data, indent=4))
                return [], []

            for objEndpoint in endpoints_data.get('items', []):
                endpoint_dict = {
                    'id': objEndpoint.get('id'),
                    'TYPE': objEndpoint.get('type'),
                    'hostname': objEndpoint.get('hostname')
                }

                self._endpoints_list.append(endpoint_dict)
                self._endpoints_ids.append(endpoint_dict['id'])

            next_key = endpoints_data.get('pages', {}).get('nextKey')
            if next_key:
                self._request_page += 1
                return append_endpoints(next_key)

            return self._endpoints_list, self._endpoints_ids

        return append_endpoints()