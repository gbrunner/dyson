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
    optional.add_argument('-fixbundles', help='get', action='store_true')
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
    folder_name = res['services'][0]['folderName']

    services = res['services']
    service_list = []

    for service in services:
        service_list.append(("{}_{}".format(folder_name, service['serviceName']), "{}".format(service['serviceName'])))

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
            if os.path.splitext(object_list[1])[0] not in crf_list:
                crf_list.append(os.path.splitext(object_list[1])[0])
    print("\tFound {} .crf files\n".format(len(crf_list)))
    return crf_list


def compare_crfs_to_services(token, server_url):

    delete_candidates = []
    services = get_services(token, server_url)
    services_short_name = [service[0] for service in services]

    cloud_raster_store = get_cloud_raster_store(token, server_url)
    for crf in get_bucket_objects(cloud_raster_store):
        if crf not in services_short_name:
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


def verify_bucket_object(bucket, key):

    s3_resource = boto3.resource('s3')
    bucket = s3_resource.Bucket(bucket)
    objs = list(bucket.objects.filter(Prefix=key))

    if len(objs) > 0:
        return True
    else:
        return False


def fix_broken_paths(token, server_url, bucket):
    client = boto3.client('s3')
    res = json.loads(requests.get("{}/arcgis/admin/services/Hosted?f=pjson".format(server_url), params={'token': '{}'.format(token)}, verify=False).text)
    folder_name = res['services'][0]['folderName']

    for service in get_services(token, server_url):

        individual_res = json.loads(requests.get("{}/arcgis/admin/services/Hosted/{}.ImageServer?f=pjson".format(server_url, service[1]), params={'token': '{}'.format(token)}, verify=False).text)

        s3_bundle_path = individual_res['properties']['path']
        if s3_bundle_path == "@":

            print("\n{0} has a path value of {1}".format(service[1], s3_bundle_path))

            full_crf_name = bucket[1] + "/" + "{}_".format(folder_name) + service[1] + ".crf"

            if verify_bucket_object(bucket[0], full_crf_name):
                # dont hardcode region name here

                web_url = "https://{}.s3-us-west-2.amazonaws.com/{}".format(bucket[0], full_crf_name)
                # below returns the url with wrong region, if you try to browse to it redirects to west region?
                #web_url = "https://{}.s3-{}.amazonaws.com/{}".format(bucket[0],client.meta.region_name, full_crf_name)
                print("Found a corresponding web url in s3!! Setting path property for {} from @ to {}".format(
                    full_crf_name, web_url))

                individual_res['properties']['path'] = web_url

                payload = {
                    'service': json.dumps(individual_res),
                    'token': token,
                    'f': 'json'
                }
                # uncomment below to actually post the update
                # requests.post("{}/arcgis/admin/services/Hosted/{}.ImageServer/edit".format(server_url, service['serviceName']),  data=payload, verify=False)

            else:
                print("Sorry, found no crf in s3 that matches")


def main():
    constants = get_input()[0]
    commands = get_input()[1]

    if commands.fixbundles:
        token = get_token(constants)
        bucket = get_cloud_raster_store(token, constants['info']['server_url'])
        fix_broken_paths(token,  constants['info']['server_url'], bucket)

    if commands.compare:
        token = get_token(constants)
        compare_crfs_to_services(token, constants['info']['server_url'])
        delete_ = input('\nWould you like to delete these .crfs? y or n')

        if delete_ == 'y':
            print("ok, deleting .crfs.. implement this later")
            #delete_items()
        elif delete_ == 'n':
            print("ok, exiting")


if __name__ == '__main__':
    main()
