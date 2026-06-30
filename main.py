#!/usr/bin/python3

import os
import json
import random
import string
import argparse

from vendors.sophos_central.sophos_api_connector import Auth
from vendors.sophos_central.sophos_migrate_endpoints import Migration
from vendors.sophos_central.sophos_endpoints import Endpoint
from config import Config

auth = Auth()
config = Config()
endpoints = Endpoint()
migration = Migration()


def create_job_folder():
    print("""[*] - We'll ask you to define a customer name.
    - This name will be used to create a folder for this job with the name defined here.
    - If you leave it empty, we'll create a folder with the name job-{RANDOM-CHARS}.
    - If you set a customer name (eg.: XPTO) and this folder already exists, you can reuse it or create a new random folder.
    """)

    answer = input("[?] - Define a customer name: ")
    print("\n")

    folder_prefix = "job"
    if len(answer) != 0:
        folder_prefix = answer

    folder_created = False
    create_random = False

    while not folder_created:
        job_folder = folder_prefix

        if create_random or folder_prefix == "job":
            job_folder = job_folder + "-" + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )

        print("[*] - Checking if folder %s exists..." % job_folder)

        job_path = "jobs/%s" % job_folder

        if not os.path.exists(job_path):
            try:
                os.makedirs(job_path)
                folder_created = True
            except Exception as error:
                print("[*] - Error while creating Job folder.")
                print("[!] - Error: %s" % error)
                exit(1)
        else:
            print("[!] - Job folder {JOBFOLDER} already exists!".format(JOBFOLDER=job_folder))
            answer = input("[?] - Keep defined folder name? [Yes/No] (Default: Yes) ")

            if any(answer.lower() == f for f in ['no', 'n', '0']):
                create_random = True
            else:
                return job_folder

    print("[*] - Job folder created at: {JOBFOLDER}\n".format(JOBFOLDER=job_folder))
    return job_folder


def write_json(data, job_folder, type):
    path = os.getcwd()
    jobs_path = path + "/" + config.get("jobs_folder")
    target_path = jobs_path + "/" + job_folder

    filename = "%s.json" % type
    file_path = target_path + "/" + filename

    try:
        with open(file_path, 'w') as outfile:
            json.dump(data, outfile, indent=4)

    except IOError as error:
        print("[!] - Error while creating %s file." % filename)
        print("[!] - Error: %s" % error)
        return False

    return filename


def main(args=None):
    print("[*] - Checking config.ini settings...")

    print("[#] - Migrate Endpoints:\t\t {CONFIG_ENDPOINTS}".format(
        CONFIG_ENDPOINTS=config.get("migrate_endpoints")
    ))
    print("[#] - Migrate computer groups:\t\t {CONFIG_EP_GROUPS}".format(
        CONFIG_EP_GROUPS=config.get("migrate_endpoints_groups")
    ))
    print("[#] - Migrate Exclusions:\t\t {CONFIG_EXCLUSIONS}".format(
        CONFIG_EXCLUSIONS=config.get("migrate_exclusions")
    ))
    print("[#] - Migrate Endpoint/Server Policies:  {CONFIG_POLICIES}".format(
        CONFIG_POLICIES=config.get("migrate_policies")
    ))

    answer = input("\n[?] - You really want to continue? [Yes / No] (Default: Yes): ")
    if any(answer.lower() == f for f in ['no', 'n', '0']):
        print('\n\n[!] - Aborting execution!')
        exit(0)

    print("\n[*] - User confirmed. Continuing to create a new Migration Job.")

    job_folder = create_job_folder()
    print("\n")

    source_headers, source_central_dataregion = auth.get_headers("source_sophos_central")
    dst_header, dst_central_dataregion = auth.get_headers("destination_sophos_central")

    headers = {
        "source": {
            "headers": source_headers,
            "region": source_central_dataregion
        },
        "destination": {
            "headers": dst_header,
            "region": dst_central_dataregion
        }
    }

    if config.get("migrate_exclusions"):
        print("[*] - Migrating Exclusions as it has been set on config.ini. \n")
        migration.migrate_exclusions(headers)

    if config.get("migrate_endpoints_groups"):
        print("[*] - Migrating computer groups.")
        print("[!] - Note that groups from Active Directory and Azure will not be migrated! You should run Azure/AD Sync for this.")
        migration.migrate_computer_groups(headers)

    if config.get("migrate_policies"):
        print("[*] - Migrating Policies... \n")
        migration.migrate_policies(headers)

    if config.get("migrate_endpoints"):
        print("[*] - Migrating Endpoints... \n")
        print("[*] - Getting list of endpoints from Source tenant")

        endpoints_list, endpoints_ids, source_data = endpoints.get_all_endpoints(
            headers['source'],
            job_folder
        )

        if source_data == "from_file":
            print("\n[*] - {COUNT} endpoint(s) in the list will be migrated.\n".format(
                COUNT=len(endpoints_list)
            ))
            print("\t[0] - Yes, continue with this list.")
            print("\t[1] - Migrate ALL endpoints from Central (ignore this list).")
            print("\t[2] - Abort execution.")

            answer = input("\n[?] - Choose an option: ")

            try:
                answer = int(answer)
            except ValueError:
                print("[!] - Invalid option. Aborting execution.")
                exit(1)

            if answer == 2:
                print('\n\n[!] - Aborting execution!')
                exit(0)

            elif answer == 1:
                print("\n[*] - Migrating all endpoints from Central.")
                endpoints_list, endpoints_ids, source_data = endpoints.get_all_endpoints(
                    headers['source'],
                    job_folder,
                    False
                )

        if not endpoints_list or not endpoints_ids:
            print("[!] - No endpoints found to migrate. Aborting execution.")
            exit(1)

        migration_job = migration.create_job(endpoints_ids, endpoints_list, headers)

        if config.get("debug"):
            print(json.dumps(migration_job, indent=4))

        if migration_job:
            start_migration_job = migration.start_job(
                headers,
                migration_job['job_id'],
                endpoints_ids,
                migration_job['token']
            )

            if start_migration_job:
                migration_data = dict()
                migration_data['Source_Tenant'] = start_migration_job
                migration_data['Destination_Tenant'] = migration_job

                job_file = write_json(migration_data, job_folder, "migration_job")

                if job_file:
                    print("[*] - File with Job information created at: %s" % job_file)
                    exit(0)
            else:
                print("\n[*] - Some error occurred while starting migration job on Source tenant.")
                exit(1)
        else:
            print("\n[*] - Some error occurred while creating migration job on Destination Tenant.")
            exit(1)


if __name__ == "__main__":
    print("[*] - Starting Sophos Central Migration Tool!\n")

    parser = argparse.ArgumentParser(
        description='Script for migrating Sophos Central endpoints between sub-estates.'
    )

    parser.add_argument(
        '--list-jobs',
        '-l',
        help='List all the job IDs created by this tool.',
        action="store_true"
    )

    parser.add_argument(
        '--status',
        '-s',
        help='Status of a specific migration ID.',
        type=str
    )

    parser.add_argument(
        '--endpoint-file',
        '-e',
        action="store_true",
        help='Generate a list of Endpoints existing on the source tenant.'
    )

    args = parser.parse_args()

    if args.status:
        dst_headers, dst_centralregion = auth.get_headers("destination_sophos_central")
        migration.status(
            dst_headers,
            dst_centralregion,
            migration_id=args.status
        )

    elif args.endpoint_file:
        src_headers, src_centralregion = auth.get_headers("source_sophos_central")

        headers = {
            'source': {
                'headers': src_headers,
                'region': src_centralregion
            }
        }

        job_folder = create_job_folder()
        endpoints.generate_ep_file(headers, job_folder)

    elif args.list_jobs:
        migration.list_jobs()

    else:
        print("[*] - No arguments passed. Starting main function.")
        main(args)