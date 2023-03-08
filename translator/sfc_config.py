import json
import logging
import os.path
import sys

import yaml

# TODO: make it functional
gInput = ""


def get_service_nodes_uri():
    return "/restconf/config/service-node:service-nodes"


def get_service_nodes_data():
    global gInput
    sns = {
        "service-nodes": {
            "service-node": [
                {"name": node["name"], "ip-mgmt-address": node["ip-address"]}
                for node in gInput["service-nodes"]
            ]
        }
    }

    return sns


def get_service_functions_uri():
    return "/restconf/config/service-function:service-functions"


def get_service_functions_data():
    global gInput

    sfs = {
        "service-functions": {
            "service-function": [
                {
                    "name": node["name"],
                    "ip-mgmt-address": node["ip-address"],
                    "rest-uri": "http://" + node["ip-address"] + ":5000",
                    "type": node["type"],
                    "nsh-aware": "true",
                    "sf-data-plane-locator": {
                        "name": node["name"] + "-dpl",
                        "port": 6633,
                        "ip": node["ip-address"],
                        "transport": "service-locator:vxlan-gpe",
                        "service-function-forwarder": node["sff_name"],
                    },
                }
                for node in gInput["service-functions"]
            ]
        }
    }
    return sfs


def get_service_function_forwarders_uri():
    return "/restconf/config/service-function-forwarder:service-function-forwarders"


def get_service_function_forwarders_data():
    global gInput
    sffs = {}
    sffs["service-function-forwarders"] = {}
    sffs["service-function-forwarders"]["service-function-forwarder"] = list()

    for node in gInput["service-function-forwarders"]:
        counter = 1
        sff_dp_locator = list()
        sf_dictionary = list()
        if len(node["service_function"]) > 0:
            for ele in node["service_function"]:
                sff_dp_locator.append(
                    {
                        "name": node["name"] + "-" + str(counter) + "-dpl",
                        "data-plane-locator": {
                            "transport": "service-locator:vxlan-gpe",
                            "port": 6633,
                            "ip": node["ip-address"],
                        },
                        "service-function-forwarder-ovs:ovs-options": {
                            "remote-ip": "flow",
                            "dst-port": "6633",
                            "key": "flow",
                            "nsp": "flow",
                            "nsi": "flow",
                            "nshc1": "flow",
                            "nshc2": "flow",
                            "nshc3": "flow",
                            "nshc4": "flow",
                            "exts": "gpe",
                        },
                    }
                )
                sf_dictionary.append(
                    {
                        "name": ele,
                        "sff-sf-data-plane-locator": {
                            "sf-dpl-name": ele + "-dpl",
                            "sff-dpl-name": node["name"] + "-" + str(counter) + "-dpl",
                        },
                    }
                )
                counter += 1
        else:
            sff_dp_locator.append(
                {
                    "name": node["name"] + "-" + str(counter) + "-dpl",
                    "data-plane-locator": {
                        "transport": "service-locator:vxlan-gpe",
                        "port": 6633,
                        "ip": node["ip-address"],
                    },
                    "service-function-forwarder-ovs:ovs-options": {
                        "remote-ip": "flow",
                        "dst-port": "6633",
                        "key": "flow",
                        "nsp": "flow",
                        "nsi": "flow",
                        "nshc1": "flow",
                        "nshc2": "flow",
                        "nshc3": "flow",
                        "nshc4": "flow",
                        "exts": "gpe",
                    },
                }
            )

        if counter > 1:
            sffs["service-function-forwarders"]["service-function-forwarder"].append(
                {
                    "name": node["name"],
                    "service-node": node["service_node"],
                    "service-function-forwarder-ovs:ovs-bridge": {
                        "bridge-name": "br-sfc"
                    },
                    "sff-data-plane-locator": sff_dp_locator,
                    "service-function-dictionary": sf_dictionary,
                }
            )
        else:
            sffs["service-function-forwarders"]["service-function-forwarder"].append(
                {
                    "name": node["name"],
                    "service-node": node["service_node"],
                    "service-function-forwarder-ovs:ovs-bridge": {
                        "bridge-name": "br-sfc"
                    },
                    "sff-data-plane-locator": sff_dp_locator,
                }
            )

    return sffs


def get_service_function_chains_uri():
    return "/restconf/config/service-function-chain:service-function-chains/"


def get_service_function_chains_data():
    global gInput
    sfcs = {}
    sfcs["service-function-chains"] = {}
    sfcs["service-function-chains"]["service-function-chain"] = list()

    for node in gInput["service-function-chains"]:
        sfc_sf = list()
        for ele in node["service_function"]:
            for sf in gInput["service-functions"]:
                if sf["name"] == ele:
                    sf_type = sf["type"]
            sfc_sf.append({"name": ele, "type": sf_type})

        sfcs["service-function-chains"]["service-function-chain"].append(
            {
                "name": node["name"],
                "symmetric": node["symmetric"],
                "sfc-service-function": sfc_sf,
            }
        )

    return sfcs


def get_service_function_paths_uri():
    return "/restconf/config/service-function-path:service-function-paths/"


def get_service_function_paths_data():
    global gInput
    sfps = {}
    sfps["service-function-paths"] = {}
    sfps["service-function-paths"]["service-function-path"] = list()

    for node in gInput["service-function-chains"]:
        sfps["service-function-paths"]["service-function-path"].append(
            {
                "name": node["name"] + "-" + "SFP",
                "service-chain-name": node["name"],
                "starting-index": 255,
                "symmetric": node["symmetric"],
                "context-metadata": "NSH1",
            }
        )

    return sfps


def get_service_function_metadata_uri():
    return "/restconf/config/service-function-path-metadata:service-function-metadata/"


def get_service_function_metadata_data():
    return {
        "service-function-metadata": {
            "context-metadata": [
                {
                    "name": "NSH1",
                    "context-header1": "1",
                    "context-header2": "2",
                    "context-header3": "3",
                    "context-header4": "4",
                }
            ]
        }
    }


def get_rendered_service_path_uri():
    return "/restconf/operations/rendered-service-path:create-rendered-path/"


def get_rendered_service_path_data():
    global gInput
    rsps = {
        "input": [
            {
                "name": "RSP-" + node["name"],
                "parent-service-function-path": node["name"] + "-" + "SFP",
                "symmetric": node["symmetric"],
            }
            for node in gInput["service-function-chains"]
        ]
    }

    return rsps


def get_service_function_acl_uri():
    return "/restconf/config/ietf-access-control-list:access-lists/"


def get_service_function_acl_data():
    global gInput
    acls = {}

    acl_list = list()
    for node in gInput["acls"]:
        ace_list = list()
        for ace in node["aces"]:
            matches = {
                "destination-ipv4-network": ace["diprange"],
                "source-ipv4-network": ace["siprange"],
                "protocol": ace["proto"],
                "source-port-range": {
                    "lower-port": ace["sprange"][0],
                    "upper-port": ace["sprange"][1],
                },
                "destination-port-range": {
                    "lower-port": ace["dprange"][0],
                    "upper-port": ace["dprange"][1],
                },
            }
            fwd = "Forward"
            if ace["direction"].lower() == fwd.lower():
                ace_list.append(
                    {
                        "rule-name": ace["name"],
                        "actions": {
                            "service-function-acl:rendered-service-path": "RSP-"
                            + ace["action"]
                        },
                        "matches": matches,
                    }
                )
            else:
                ace_list.append(
                    {
                        "rule-name": ace["name"],
                        "actions": {
                            "service-function-acl:rendered-service-path": "RSP-"
                            + ace["action"]
                            + "-Reverse"
                        },
                        "matches": matches,
                    }
                )

        acl_list.append(
            {
                "acl-name": node["name"],
                "acl-type": "ietf-access-control-list:ipv4-acl",
                "access-list-entries": {"ace": ace_list},
            }
        )

    acls["access-lists"] = {"acl": acl_list}
    return acls


def get_service_function_classifiers_uri():
    return "/restconf/config/service-function-classifier:service-function-classifiers/"


def get_service_function_classifiers_data():
    global gInput

    sfcls = {
        "service-function-classifiers": {
            "service-function-classifier": [
                {
                    "name": node["name"],
                    "scl-service-function-forwarder": [
                        {"name": node["sff"], "interface": node["interface"]}
                    ],
                    "acl": {
                        "name": node["acl"],
                        "type": "ietf-access-control-list:ipv4-acl",
                    },
                }
                for node in gInput["service-function-classifiers"]
            ]
        }
    }

    return sfcls


def validate_and_load_input(json_data):
    global gInput
    try:
        gInput = json.loads(json_data)
    except ValueError as e:
        logging.error("Fix following error in input JSON.")
        logging.error(e)
        return False
    return True


def generate_restconf_files_for_create(json_data, output_dir, controller_provider):
    # check if input file data correctness
    return_code = validate_and_load_input(json_data)
    if return_code:
        logging.info("Generating configuration...")
    else:
        logging.error("Invalid json data.")
        sys.exit(1)

    # create outpur file name as script_folder + output.py
    exec_dirname = output_dir
    # create file for Service Node configuration
    outfilename = os.path.join(
        exec_dirname,
        "scripts/Controller_scripts",
        controller_provider,
        "configure.yaml",
    )

    with open(outfilename, "w+") as op_fp:
        print(
            yaml.dump(
                [
                    {
                        "name": "Wait for http controller port to be ready",
                        "wait_for": {
                            "host": gInput["controller"][
                                "ip-address"
                            ],  # TODO переделать на проброс переменных, убрать gInput
                            "port": gInput["controller"]["port"],
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        print(
            yaml.dump(
                [
                    {
                        "name": "Wait for ovs controller port to be ready",
                        "wait_for": {
                            "host": gInput["controller"]["ip-address"],
                            "port": 6653,
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        print(
            yaml.dump(
                [
                    {
                        "name": "Wait for final controller port to be ready",
                        "wait_for": {
                            "host": gInput["controller"]["ip-address"],
                            "port": 9999,
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        print(
            yaml.dump(
                [
                    {
                        "name": "REST API to %s" % get_service_nodes_uri(),
                        "uri": {
                            "url": "http://"
                            + gInput["controller"]["ip-address"]
                            + ":"
                            + gInput["controller"]["port"]
                            + get_service_nodes_uri(),
                            "user": gInput["controller"]["user"],
                            "password": gInput["controller"]["password"],
                            "body": json.dumps(get_service_nodes_data()),
                            "body_format": "json",
                            "method": "PUT",
                            "status_code": [201, 200],
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        print(
            yaml.dump(
                [
                    {
                        "name": "REST API to %s" % get_service_functions_uri(),
                        "uri": {
                            "url": "http://"
                            + gInput["controller"]["ip-address"]
                            + ":"
                            + gInput["controller"]["port"]
                            + get_service_functions_uri(),
                            "user": gInput["controller"]["user"],
                            "password": gInput["controller"]["password"],
                            "body": json.dumps(get_service_functions_data()),
                            "body_format": "json",
                            "method": "PUT",
                            "status_code": [201, 200],
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        print(
            yaml.dump(
                [
                    {
                        "name": "REST API to %s"
                        % get_service_function_forwarders_uri(),
                        "uri": {
                            "url": "http://"
                            + gInput["controller"]["ip-address"]
                            + ":"
                            + gInput["controller"]["port"]
                            + get_service_function_forwarders_uri(),
                            "user": gInput["controller"]["user"],
                            "password": gInput["controller"]["password"],
                            "body": json.dumps(get_service_function_forwarders_data()),
                            "body_format": "json",
                            "method": "PUT",
                            "status_code": [201, 200],
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        print(
            yaml.dump(
                [
                    {
                        "name": "REST API to %s" % get_service_function_metadata_uri(),
                        "uri": {
                            "url": "http://"
                            + gInput["controller"]["ip-address"]
                            + ":"
                            + gInput["controller"]["port"]
                            + get_service_function_metadata_uri(),
                            "user": gInput["controller"]["user"],
                            "password": gInput["controller"]["password"],
                            "body": json.dumps(get_service_function_metadata_data()),
                            "body_format": "json",
                            "method": "PUT",
                            "status_code": [201, 200],
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        print(
            yaml.dump(
                [
                    {
                        "name": "REST API to %s" % get_service_function_chains_uri(),
                        "uri": {
                            "url": "http://"
                            + gInput["controller"]["ip-address"]
                            + ":"
                            + gInput["controller"]["port"]
                            + get_service_function_chains_uri(),
                            "user": gInput["controller"]["user"],
                            "password": gInput["controller"]["password"],
                            "body": json.dumps(get_service_function_chains_data()),
                            "body_format": "json",
                            "method": "PUT",
                            "status_code": [201, 200],
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        print(
            yaml.dump(
                [
                    {
                        "name": "REST API to %s" % get_service_function_paths_uri(),
                        "uri": {
                            "url": "http://"
                            + gInput["controller"]["ip-address"]
                            + ":"
                            + gInput["controller"]["port"]
                            + get_service_function_paths_uri(),
                            "user": gInput["controller"]["user"],
                            "password": gInput["controller"]["password"],
                            "body": json.dumps(get_service_function_paths_data()),
                            "body_format": "json",
                            "method": "PUT",
                            "status_code": [201, 200],
                        },
                    }
                ]
            ),
            file=op_fp,
        )
        for node in gInput["service-function-chains"]:
            rsps = {
                "input": {
                    "name": "RSP-" + node["name"],
                    "parent-service-function-path": node["name"] + "-" + "SFP",
                    "symmetric": node["symmetric"],
                }
            }
            print(
                yaml.dump(
                    [
                        {
                            "name": "REST API to %s" % get_rendered_service_path_uri(),
                            "uri": {
                                "url": "http://"
                                + gInput["controller"]["ip-address"]
                                + ":"
                                + gInput["controller"]["port"]
                                + get_rendered_service_path_uri(),
                                "user": gInput["controller"]["user"],
                                "password": gInput["controller"]["password"],
                                "body": json.dumps(rsps),
                                "body_format": "json",
                                "method": "POST",
                                "status_code": [201, 200],
                            },
                        }
                    ]
                ),
                file=op_fp,
            )
        print(
            yaml.dump(
                [
                    {
                        "name": "REST API to %s" % get_service_function_acl_uri(),
                        "uri": {
                            "url": "http://"
                            + gInput["controller"]["ip-address"]
                            + ":"
                            + gInput["controller"]["port"]
                            + get_service_function_acl_uri(),
                            "user": gInput["controller"]["user"],
                            "password": gInput["controller"]["password"],
                            "body": json.dumps(get_service_function_acl_data()),
                            "body_format": "json",
                            "method": "PUT",
                            "status_code": [201, 200],
                        },
                    }
                ]
            ),
            file=op_fp,
        )

        print(
            yaml.dump(
                [
                    {
                        "name": "REST API to %s"
                        % get_service_function_classifiers_uri(),
                        "uri": {
                            "url": "http://"
                            + gInput["controller"]["ip-address"]
                            + ":"
                            + gInput["controller"]["port"]
                            + get_service_function_classifiers_uri(),
                            "user": gInput["controller"]["user"],
                            "password": gInput["controller"]["password"],
                            "body": json.dumps(get_service_function_classifiers_data()),
                            "body_format": "json",
                            "method": "PUT",
                            "status_code": [201, 200],
                        },
                    }
                ]
            ),
            file=op_fp,
        )
