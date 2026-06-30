import os
import json
from os import listdir
from os.path import isfile, join
from config import Config
from config import ignore_policy_settings
from vendors.sophos_central.sophos_api_connector import CentralRequest

config = Config()
central = CentralRequest()


class Migration(object):

    def __init__(self) -> None:
        self.DEFAULT_JOBS_FOLDER = './jobs/'

    def create_job(self, endpoints_ids, endpoints_list, headers):
        print("[*] - Creating migration job from tenant: %s" % headers['source']['headers']['X-Tenant-ID'])

        migrate_json = {
            "fromTenant": headers['source']['headers']['X-Tenant-ID'],
            "endpoints": endpoints_ids
        }

        migration_url = "{DATA_REGION}/{MIGRATION_URI}".format(
            DATA_REGION=headers['destination']['region'],
            MIGRATION_URI="endpoint/v1/migrations"
        )

        job_status, res_data = central.insert(
            migration_url,
            headers['destination']['headers'],
            migrate_json
        )

        if job_status:
            print("[*] - Job created. ID: %s" % res_data['id'])

            migrate_json["endpoints"] = endpoints_list
            migrate_json["job_id"] = res_data['id']
            migrate_json["token"] = res_data['token']
            migrate_json["createdAt"] = res_data['createdAt']
            migrate_json["expiresAt"] = res_data['expiresAt']

            return migrate_json

        print("[!] - Error while creating migration job.")
        if config.get("debug"):
            print(json.dumps(res_data, indent=4))
        return False

    def start_job(self, headers, migration_id, endpoints_ids, token):
        print("[*] - Starting last created job: %s" % migration_id)

        params_data = {
            "id": migration_id,
            "token": token,
            "endpoints": endpoints_ids
        }

        migration_url = "{DATA_REGION}/{MIGRATION_URI}/{MIGRATION_ID}".format(
            DATA_REGION=headers['source']['region'],
            MIGRATION_URI="endpoint/v1/migrations",
            MIGRATION_ID=migration_id
        )

        job_status, job_data = central.put(
            migration_url,
            headers['source']['headers'],
            params_data
        )

        if job_status:
            return job_data

        print("[!] - Error while starting migration job.")
        if config.get("debug"):
            print(json.dumps(job_data, indent=4))
        return False

    def list_jobs(self):
        if not os.path.exists(self.DEFAULT_JOBS_FOLDER):
            print("[!] - Jobs folder does not exist.")
            return False

        job_files = [
            f for f in listdir(self.DEFAULT_JOBS_FOLDER)
            if isfile(join(self.DEFAULT_JOBS_FOLDER, f))
        ]

        if not job_files:
            print("[!] - No job files found.")
            return False

        for job_id in job_files:
            print("[%d] - %s" % (job_files.index(job_id), job_id.split(".")[0]))

        return True

    def status(self, headers, central_dataregion, src_tenant=None, migration_id=""):
        print("[*] - Function: Get job status")

        if migration_id:
            migration_url = "{DATA_REGION}/{MIGRATION_URI}/{MIGRATION_ID}/endpoints".format(
                DATA_REGION=central_dataregion,
                MIGRATION_URI="endpoint/v1/migrations",
                MIGRATION_ID=migration_id
            )
        else:
            migration_url = "{DATA_REGION}/{MIGRATION_URI}".format(
                DATA_REGION=central_dataregion,
                MIGRATION_URI="endpoint/v1/migrations"
            )

        status, migration_data = central.get(migration_url, headers)

        if not status:
            print("[!] - Could not get migration status.")
            if config.get("debug"):
                print(json.dumps(migration_data, indent=4))
            return False

        endpoints_file = None

        if src_tenant:
            for folder, subs, files in os.walk(self.DEFAULT_JOBS_FOLDER):
                for filename in files:
                    if src_tenant in filename:
                        endpoints_file = f'{folder}/{filename}'
                        break

        if migration_id:
            job_endpoints = None

            if endpoints_file:
                try:
                    print('[*] - Job file exists... Getting data...')
                    with open(endpoints_file, 'r') as json_file:
                        job_endpoints = json.load(json_file)
                except Exception:
                    job_endpoints = None

            print("[*] - Getting job status of Job ID: %s" % migration_id)
            print("\n========================================================================")

            for migration_status in migration_data.get('items', []):
                try:
                    if job_endpoints:
                        endpoint = next(
                            (item for item in job_endpoints if item['id'] == migration_status['id']),
                            None
                        )
                        if endpoint:
                            print("Endpoint:\t %s" % endpoint['hostname'].title())
                except Exception:
                    pass

                print("Endpoint ID:\t %s" % migration_status.get('id'))
                print("Status:\t\t %s" % migration_status.get('status'))

                if migration_status.get('status') == "failed":
                    print("Reason:\t\t %s" % migration_status.get('reason'))
                    print("Failed at:\t %s" % migration_status.get('failedAt'))

                print("\n")

            return True

        print(json.dumps(migration_data, indent=4))
        return True

    def migrate_exclusions(self, headers, migration_type=None):
        print("[*] - Function: Migrating exclusions")

        if not migration_type:
            migration_type = [
                "exclusions/scanning",
                "exclusions/isolation",
                "exclusions/intrusion-prevention",
                "web-control/local-sites"
            ]

        for type_url in migration_type:
            type_url = "endpoint/v1/settings/" + type_url

            src_setting_url = "{DATA_REGION}/{SETTING_URI}".format(
                DATA_REGION=headers['source']['region'],
                SETTING_URI=type_url
            )

            dst_setting_url = "{DATA_REGION}/{SETTING_URI}".format(
                DATA_REGION=headers['destination']['region'],
                SETTING_URI=type_url
            )

            if config.get("debug"):
                print("\n\n[*] - Getting settings for " + type_url)

            status, data = central.get(src_setting_url, headers['source']['headers'])

            if not status:
                print("[-] - Could not get exclusions for {migration_type}".format(migration_type=type_url))
                if config.get("debug"):
                    print(json.dumps(data, indent=4))
                continue

            for exclusion in data.get('items', []):
                exclusion_dict = {}

                for key in exclusion.keys():
                    if key == "id":
                        continue
                    exclusion_dict[key] = exclusion[key]

                send_status, send_data = central.insert(
                    dst_setting_url,
                    headers['destination']['headers'],
                    exclusion_dict
                )

                if send_status:
                    print("[+] - Creating exclusion for {migration_type} success!".format(migration_type=type_url))
                else:
                    print("[-] - Could not create exclusions for {migration_type}".format(migration_type=type_url))
                    if config.get("debug"):
                        print(json.dumps(send_data, indent=4))

    def get_policies(self, headers):
        print("[*] - Getting All Policies")

        params_data = {
            "pageTotal": True
        }

        policies_url = "{DATA_REGION}/{URI}".format(
            DATA_REGION=headers['region'],
            URI="endpoint/v1/policies"
        )

        res_status, res_data = central.get(
            policies_url,
            headers['headers'],
            params_data
        )

        if res_status:
            return res_data

        print("[!] - Could not get policies.")
        if config.get("debug"):
            print(json.dumps(res_data, indent=4))
        return False

    def _clean_policy_settings(self, policy):
        policy_settings = json.loads(json.dumps(policy.get('settings', {})))
        policy_type = policy.get('type')

        if policy_type in ignore_policy_settings:
            print("[*] - Cleaning unsupported/read-only settings for policy type: %s" % policy_type)

            for remove_setting in ignore_policy_settings[policy_type]:
                if remove_setting in policy_settings:
                    print("[-] - Removing read-only setting: " + remove_setting)
                    policy_settings.pop(remove_setting, None)

        for setting_name, setting_value in policy_settings.items():
            if isinstance(setting_value, dict):
                setting_value.pop("recommendedValue", None)

        scanning_key = "endpoint.threat-protection.exclusions.scanning"
        if scanning_key in policy_settings:
            current_exclusions = policy_settings[scanning_key].get('value', [])
            scanning_exclusions = [
                x for x in current_exclusions
                if x.get('type') != "detectedExploit"
            ]
            policy_settings[scanning_key]['value'] = scanning_exclusions

        return policy_settings

    def migrate_policies(self, headers):
        src_policies = self.get_policies(headers['source'])

        if not src_policies or 'items' not in src_policies:
            print("[!] - No source policies found.")
            return False

        policies_url = "{DATA_REGION}/{URI}".format(
            DATA_REGION=headers['destination']['region'],
            URI="endpoint/v1/policies"
        )

        success_count = 0
        error_count = 0

        for policy in src_policies['items']:
            policy_name = policy.get('name')
            policy_type = policy.get('type')

            print("\n[*] - Processing policy: {POLICYNAME} ({POLICYTYPE})".format(
                POLICYNAME=policy_name,
                POLICYTYPE=policy_type
            ))

            policy_settings = self._clean_policy_settings(policy)

            if policy_name == "Base Policy":
                print("[*] - Updating Base Policy for {POLICYTYPE}".format(
                    POLICYTYPE=policy_type
                ))

                policy_content = {
                    'settings': policy_settings
                }

                base_policy_url = "/{POLICYTYPE}/base".format(
                    POLICYTYPE=policy_type
                )

                url = policies_url + base_policy_url

                status, data = central.update(
                    url,
                    headers['destination']['headers'],
                    policy_content
                )

            else:
                print("[*] - Creating a new {POLICYTYPE} policy: {POLICYNAME}".format(
                    POLICYTYPE=policy_type,
                    POLICYNAME=policy_name
                ))

                policy_content = {
                    'name': policy_name.replace("-", " ").replace("_", " "),
                    'type': policy_type,
                    'appliesTo': {},
                    'priority': policy.get('priority', 0),
                    'settings': policy_settings
                }

                status, data = central.insert(
                    policies_url,
                    headers['destination']['headers'],
                    policy_content
                )

            if status:
                success_count += 1
                print("[+] - Policy migrated successfully: {POLICYNAME}".format(
                    POLICYNAME=policy_name
                ))
            else:
                error_count += 1
                print("[!] - Error while migrating policy {POLICYNAME}".format(
                    POLICYNAME=policy_name
                ))
                if config.get("debug"):
                    print(json.dumps(data, indent=4))

        print("\n[*] - Policy migration finished.")
        print("[*] - Success: %d" % success_count)
        print("[*] - Errors: %d" % error_count)

        return error_count == 0

    def migrate_computer_groups(self, headers):
        print("[*] - Function: Migrate computer groups")

        src_endpoints_groups_url = "{DATA_REGION}/{GROUPS_URI}".format(
            DATA_REGION=headers['source']['region'],
            GROUPS_URI="endpoint/v1/endpoint-groups"
        )

        groups_status, source_computers_groups = central.get(
            src_endpoints_groups_url,
            headers['source']['headers']
        )

        if not groups_status:
            print("\n[!] - Could not get groups from source instance.")
            if config.get("debug"):
                print(json.dumps(source_computers_groups, indent=4))
            return False

        endpoints_groups_url = "{DATA_REGION}/{GROUPS_URI}".format(
            DATA_REGION=headers['destination']['region'],
            GROUPS_URI="endpoint/v1/endpoint-groups"
        )

        created_groups = []

        for group in source_computers_groups.get('items', []):
            if "description" not in group.keys():
                if config.get("debug"):
                    print("[~] - DEBUG: Ignoring AD Group: " + group['name'])
                continue

            group_dict = {
                "name": group['name'],
                "type": group['type']
            }

            if len(group.get('description', '')) != 0:
                group_dict['description'] = group['description']

            print("[*] - Creating computer group: " + group['name'])

            groups_status, groups_data = central.insert(
                endpoints_groups_url,
                headers['destination']['headers'],
                group_dict
            )

            if groups_status:
                if config.get("debug"):
                    print(json.dumps(groups_data, indent=4))
                created_groups.append(groups_data)
            else:
                print("\n[!] - Error while creating group %s\n" % group['name'])
                if config.get("debug"):
                    print(json.dumps(groups_data, indent=4))

        return created_groups