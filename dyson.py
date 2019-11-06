import requests
import json
import boto3
import os
import sys
import argparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_input():

    parser = argparse.ArgumentParser(description='Dyson Cleaner Tool')
    parser._action_groups.pop()
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')
    required.add_argument('-config', required=True, help='Config File')
    optional.add_argument('-compare', help='Return results of Compare', action='store_true')
    optional.add_argument('-delete', help='Delete results of Compare', action='store_true')
    optional.add_argument('-version', action='version', version='0.9')

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    config = parser.parse_args().config
    commands = parser.parse_args()

    with open(config) as f:
        data = json.load(f)

    return data, commands


def get_token(constants):
    the_url = '{}/portal/sharing/rest/generateToken'.format(constants['info']['port_url'])

    payload = {
        'username': constants['info']['username'],
        'password': constants['info']['password'],
        'client': 'referer',
        'referer': 'referer',
        'f': 'json'
    }
    print("Requesting Token...\n")
    res = requests.post(the_url, data=payload, verify=False)

    try:
        return res.json()['token']

    except KeyError:
        raise Exception('Could Not Fetch Token with Authentication Inputs')


def get_services(token, server_url):
    res = json.loads(requests.get("{}/arcgis/admin/services/Hosted?f=pjson".format(server_url), params={'token':'{}'.format(token)}, verify=False).text)
    print("Getting Hosted Services...")
    services = res['services']
    service_list = []

    for service in services:
        service_list.append("Hosted_{}".format(service['serviceName']))
        #print(service)
    print("\tFound {} Hosted Services in {}\n".format(len(service_list), server_url))

    return service_list


def get_cloud_raster_store(token, server_url):
    res = json.loads(requests.get("{}/arcgis/admin/data/items?f=pjson".format(server_url), params={'token':'{}'.format(token)}, verify=False).text)
    print("Checking for Cloud Raster Store...")
    for x in res['rootItems']:

        if x == '/cloudStores':
            print('\tFound Cloud Raster Store')
            res2 = json.loads(requests.get("{0}/arcgis/admin/data/findItems?parentPath={1}&f=pjson".format(server_url, x), params={'token': '{}'.format(token)}, verify=False).text)
            if res2['items'][0]['provider'] == 'amazon':
                crs_root_bucket = res2['items'][0]['info']['objectStore'].split("/")[0]
                crs_bucket_path = res2['items'][0]['info']['objectStore'].split("/")[1]
                return_list = [crs_root_bucket, crs_bucket_path]
                return return_list


def get_bucket_objects(bucket):
    print("\tFinding .crf files in {}...".format(bucket[0]))

    crf_list = []
    s3_resource = boto3.resource('s3')
    bucket = s3_resource.Bucket(bucket[0])

    for bucket_obj in bucket.objects.filter():
        object_list = bucket_obj.key.split("/")

        if object_list[1].endswith(".crf"):
            #print(bucket_obj.key)
            if os.path.splitext(object_list[1])[0] not in crf_list:
                crf_list.append(os.path.splitext(object_list[1])[0])
    print("\tFound {} .crf files\n".format(len(crf_list)))
    return crf_list


def compare_crfs_to_services(token, server_url):

    delete_candidates = []
    services = get_services(token, server_url)
    cloud_raster_store = get_cloud_raster_store(token, server_url)
    for crf in get_bucket_objects(cloud_raster_store):
        if crf not in services:
            delete_candidates.append(crf)

    print("Found {0} possible candidates to delete. These {0} exist in {1}, but do not have a corresponding Hosted Service\n".format(len(delete_candidates), cloud_raster_store[0]))
    print(delete_candidates)
    return delete_candidates

## To Do - write delete function
# def delete_items():
# 
#     s3_resource = boto3.resource('s3')
#     bucket = s3_resource.Bucket()
#
#     for deleter in compare_crfs_to_services():
#         print(deleter)
#         full_path = "" + r"/" + deleter + ".crf"
#
#         for bucket_obj in bucket.objects.filter(Prefix=full_path):
#             print(bucket_obj.key)


def main():
    constants = get_input()[0]
    commands = get_input()[1]

    if commands.compare:
        token = get_token(constants)
        compare_crfs_to_services(token, constants['info']['server_url'])
        delete_ = input('\nWould you like to delete these .crfs? y or n')

        if delete_ == 'y':
            print("ok, deleting .crfs.. implement this later")
            #delete_items()
        elif delete_== 'n':
            print("ok, exiting")


if __name__ == '__main__':
    main()
