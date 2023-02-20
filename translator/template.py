import copy
import json
import os
from translator.sfc_config import generate_restconf_files_for_create

import translator.utils as utils
import ipaddress
import yaml
import logging
import sys

DEF_PATH = "/definitions/"
TRANS_PATH = "/translator/"
ORCHECTRATOR_PATH = "/definitions/Orchestrator_configs/"
CONTROLLER_PATH = "/definitions/Controller_configs/"
VNF_PATH = DEF_PATH + "/VNF_types/"
ADD_PATH = DEF_PATH + "/Additional_types/"
PROVIDERS_PATH = DEF_PATH + "/Provider_types/"

SEPARATOR = "."

from toscaparser.functions import GetProperty


class ToscaNormativeTemplate(object):
    """
    Класс транслятора
    Вход:
    1) tosca_parser_tpl - тип который вернул tosca-parser
    2) yaml_dict_mapping - yaml dict маппинга TOSCA_NFV_mapping_nfv.yaml
    Атрибуты:
    self.definitions - yaml dict определений типов NFV и нормативной TOCSA
    self.node_templates - шаблоны узлов в данной топологии
    self.relationship_templates - шаблоны отношений в данной топологии
    self.version - версия TOSCA
    self.mapping - yaml dict маппинга TOSCA_NFV_mapping_nfv.yaml
    self.basic_scripts - dict of lists строк ansible скриптов для настройки compute узлов
    self.num_addresses - dict в ктором лежит таблица соответствия адресов и compute узлов в формате {host:[address1, address2]}
    self.result_template - итоговой нормативный шаблон TOSCA
    self.new_element_templates - промежуточный dict для обработки сгенерированных шаблонов
    Методы:
    get_result - возвращает результат обработки: result_template и basic_scripts
    expand_mapping - расширяет маппинг типов: для каждого типа A derived from B применяются правила из маппинга для
    обоих типов с приоритетеом у правил типа А
    translate_specific_types - обрабатывает ip адреса (генерирует, если они не указаны), объединяет скрипты
    конфигцрации VNF в один
    resolve_get_property_functions - подставляет вместо get_property значения на которые данные функции ссылаются
    get_property_value - достает значение некоторого property
    translate_to_tosca - основной метод трансляции шаблона с NFV типами в полностью норматиный TOSCA шаблон
    Принцип работы:
    1) достаем все определения из шаблонных файлов NFV_definition_1_0.yaml и TOSCA_definition_1_0.yaml
    2) расширяем определения в маппинге которые derived from
    3) объдеиняем шаблоны узлов и отношений в один dict
    4) подставляем вместо get_property значения на которые данные функции ссылаются
    5) запускаем процесс трансляции в нормативный TOSCA шаблон:
        5.1  проходимся по всему dict сущностей, используя правила из маппинга создаем новые dict шаблоны, отельно
        отмечу правила для requirements: check - проверить существование требуемого узла, not change - добавить
        указанные в правиле атрибуты к требуемому узлу, но не менять его имя, change - добавить
        указанные в правиле атрибуты к требуемому узлу и заменить его имя на имя текущего узла
        5.2  данные шаблоны обрабатываем методом translate_specific_types, в них происходит рандомная генерация
        ip адресов, адресов и имени сети/подсети (согласно стандарту NFV они не указываются), определяется
        соответствие ip адресов и compute узлов, так же в них созданные шаблоны compute в которых из параметров
        указаны лишь скрипты для настройки (полученные после трансляции VNFD типов) обьединяются с шаблонами compute
        тех vdu, на которых базируются данные VNF, скрипт настройки обновляется путем дописывания в него скрипта
        который был закреплен за той или иной VNF
        5.3  обьединяем полученные шаблоны в полноценные шаблоны нормативных типов TOSCA и сохраняем в
        new_element_templates
    6) для всех имен из new_element_templates удаляем старые узлы (называния узлов сохрняются, но типы c namespace
    nfv должны удаляться), и узлы при обработке requirements которых было указано их заменить (дополнив при этом
    какие то другие узлы)
    7) для всех полученных compute узлов определяем соответствие с их конфигурационными файлами и дописыаем их в
    interfaces: Standard: configure
    8) составляем полный шаблон tosca
    9) при использовании метода get_result - возвращаем результат работы
    """

    def __init__(
        self,
        tosca_parser_tpl,
        yaml_dict_mapping,
        orchestrator,
        provider,
        controller,
        output_dir,
    ):
        self.result_template = {}
        self.additional_keys = []
        self.network_service_keys = []
        self.new_additional_keys = []
        self.orchestrator = orchestrator
        self.provider = provider
        self.output_dir = output_dir
        topology_template = tosca_parser_tpl.topology_template
        self.definitions = topology_template.custom_defs
        self.node_templates = {}
        self.relationship_templates = {}
        with open(
            utils.get_project_root_path() + ORCHECTRATOR_PATH + orchestrator + ".yaml",
            "r",
        ) as f:
            orc = yaml.load(f, Loader=yaml.SafeLoader)

        with open(
            utils.get_project_root_path() + CONTROLLER_PATH + controller + ".yaml",
            "r",
        ) as f:
            file_dump = yaml.load(f, Loader=yaml.SafeLoader)
            self.controller = file_dump["controller"]
            self.vnf_mapping = file_dump["vnf_types"]
            self.tosca_controller = file_dump["tosca"]

        self.basic_script_type = orc["basic_script_type"]
        self.basic_configure_node_type = orc["basic_configure_node_type"]
        self.vnf_script_type = orc["vnf_script_type"]
        self.vnf_configure_node_type = orc["vnf_configure_node_type"]
        self.address_config = orc["address_config"]
        self.port_binding_requirement = orc["port_binding_requirement"]
        try:
            self.software_prefix = orc["software_prefix"]
        except:
            self.software_prefix = ""
        self.version = tosca_parser_tpl.version
        for tmpl in topology_template.nodetemplates:
            self.node_templates[tmpl.name] = tmpl.entity_tpl
        for tmpl in topology_template.relationship_templates:
            self.relationship_templates[tmpl.name] = tmpl.entity_tpl
        self.node_templates = self.resolve_get_property_functions(self.node_templates)
        self.relationship_templates = self.resolve_get_property_functions(
            self.relationship_templates
        )
        logging.info(
            "Successfully resolved get_property functions in TOSCA NFV template."
        )
        self.mapping = yaml_dict_mapping
        self.expand_mapping()
        logging.info("Successfully expand types in mapping.")
        self.basic_scripts = {}
        self.vnf_scripts = {}
        self.num_addresses = {}
        self.translate_to_tosca()

    def get_result(self):
        return self.result_template, self.basic_scripts, self.vnf_scripts

    def expand_mapping(self):
        for key in self.mapping:
            while (
                key in self.definitions
                and "derived_from" in self.definitions[key]
                and self.definitions[key]["derived_from"] in self.definitions
                and self.definitions[key]["derived_from"] in self.mapping
            ):
                self.mapping[key] = utils.deep_update_dict(
                    self.mapping[key],
                    self.mapping[self.definitions[key]["derived_from"]],
                )
                key = self.definitions[key]["derived_from"]

    def translate_specific_types(self, tmp_template, tmpl_name):
        if tmp_template != {}:
            if tmp_template[tmpl_name]["type"] == "tosca.nodes.network.Port":
                if (
                    "properties" not in tmp_template[tmpl_name]
                    or "ip_address" not in tmp_template[tmpl_name]["properties"]
                ):
                    if "properties" not in tmp_template[tmpl_name]:
                        tmp_template[tmpl_name]["properties"] = {}
                    if "requirements" in tmp_template[tmpl_name]:
                        flag = False
                        for elem in tmp_template[tmpl_name]["requirements"]:
                            if "link" in elem:
                                start = int(
                                    ipaddress.IPv4Address(
                                        self.new_element_templates[elem["link"]][
                                            "properties"
                                        ]["start_ip"]
                                    )
                                )
                                end = int(
                                    ipaddress.IPv4Address(
                                        self.new_element_templates[elem["link"]][
                                            "properties"
                                        ]["end_ip"]
                                    )
                                )
                                address = str(
                                    ipaddress.IPv4Address(
                                        utils.get_random_int(start, end)
                                    )
                                )
                                tmp_template[tmpl_name]["properties"][
                                    "ip_address"
                                ] = address
                                flag = True
                                break
                        if not flag:
                            logging.error("Error! No link requirement.")
                            sys.exit(1)
                else:
                    if "requirements" in tmp_template[tmpl_name]:
                        address = tmp_template[tmpl_name]["properties"]["ip_address"]
                        ext = False
                        for elem in tmp_template[tmpl_name]["requirements"]:
                            if "link" in elem:
                                ext = False
                                if (
                                    "properties"
                                    in self.new_element_templates[elem["link"]]
                                    and "cidr"
                                    in self.new_element_templates[elem["link"]][
                                        "properties"
                                    ]
                                ):
                                    cidr = self.new_element_templates[elem["link"]][
                                        "properties"
                                    ]["cidr"]
                                else:
                                    logging.error("Error! Network dont have cidr.")
                                    sys.exit(1)
                                break
                            else:
                                ext = True
                        for elem in tmp_template[tmpl_name]["requirements"]:
                            if "binding" in elem:
                                if elem["binding"] not in self.num_addresses:
                                    self.num_addresses[elem["binding"]] = [address]
                                elif address not in self.num_addresses[elem["binding"]]:
                                    self.num_addresses[elem["binding"]] += [address]
                                else:
                                    break
                                if ext:
                                    if self.address_config == "addresses":
                                        self.new_element_templates[
                                            elem["binding"]
                                        ] = utils.deep_update_dict(
                                            self.new_element_templates[elem["binding"]],
                                            {
                                                "properties": {
                                                    "ports": {
                                                        "external_"
                                                        + str(
                                                            len(
                                                                self.num_addresses[
                                                                    elem["binding"]
                                                                ]
                                                            )
                                                        ): {"addresses": [address]}
                                                    }
                                                }
                                            },
                                        )
                                    elif self.address_config == "port_name":
                                        self.new_element_templates[
                                            elem["binding"]
                                        ] = utils.deep_update_dict(
                                            self.new_element_templates[elem["binding"]],
                                            # возможность нескольких айпи - потом сделаю
                                            {
                                                "properties": {
                                                    "ports": {
                                                        "external_"
                                                        + str(
                                                            len(
                                                                self.num_addresses[
                                                                    elem["binding"]
                                                                ]
                                                            )
                                                        ): {"port_name": address}
                                                    }
                                                }
                                            },
                                        )
                                else:
                                    if self.address_config == "addresses":
                                        self.new_element_templates[
                                            elem["binding"]
                                        ] = utils.deep_update_dict(
                                            self.new_element_templates[elem["binding"]],
                                            {
                                                "properties": {
                                                    "ports": {
                                                        "internal_"
                                                        + str(
                                                            len(
                                                                self.num_addresses[
                                                                    elem["binding"]
                                                                ]
                                                            )
                                                        ): {"addresses": [address]}
                                                    }
                                                }
                                            },
                                        )
                                    elif self.address_config == "port_name":
                                        self.new_element_templates[
                                            elem["binding"]
                                        ] = utils.deep_update_dict(
                                            self.new_element_templates[elem["binding"]],
                                            {
                                                "properties": {
                                                    "ports": {
                                                        "internal_"
                                                        + str(
                                                            len(
                                                                self.num_addresses[
                                                                    elem["binding"]
                                                                ]
                                                            )
                                                        ): {"port_name": address}
                                                    }
                                                }
                                            },
                                        )
                                    if (
                                        self.software_prefix + elem["binding"]
                                        not in self.new_element_templates
                                    ):
                                        self.new_element_templates[
                                            self.software_prefix + elem["binding"]
                                        ] = {"type": "tosca.nodes.SoftwareComponent"}
                                    self.new_element_templates[
                                        self.software_prefix + elem["binding"]
                                    ] = utils.deep_update_dict(
                                        self.new_element_templates[
                                            self.software_prefix + elem["binding"]
                                        ],
                                        {
                                            "interfaces": {
                                                "Standard": {
                                                    self.basic_script_type: {
                                                        "inputs": {
                                                            "iPAddressDict": {
                                                                str(
                                                                    len(
                                                                        self.num_addresses[
                                                                            elem[
                                                                                "binding"
                                                                            ]
                                                                        ]
                                                                    )
                                                                ): {
                                                                    "address": address,
                                                                    "cidr": cidr,
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        },
                                    )
                                if not self.port_binding_requirement:
                                    tmp_template[tmpl_name]["requirements"].remove(elem)
                                    if (
                                        len(tmp_template[tmpl_name]["requirements"])
                                        == 0
                                    ):
                                        self.new_additional_keys += [tmpl_name]
                                break
            elif tmp_template[tmpl_name]["type"] == "tosca.nodes.network.Network":
                net_name = "net" + str(utils.get_random_int(0, 1024))
                if "properties" not in tmp_template[tmpl_name]:
                    cidr = utils.generate_random_subnet()
                    tmp_template[tmpl_name]["properties"] = {}
                    tmp_template[tmpl_name]["properties"]["cidr"] = cidr
                    tmp_template[tmpl_name]["properties"]["end_ip"] = str(
                        ipaddress.ip_network(cidr)[-4]
                    )
                    tmp_template[tmpl_name]["properties"]["start_ip"] = str(
                        ipaddress.ip_network(cidr)[10]
                    )
                    tmp_template[tmpl_name]["properties"]["gateway_ip"] = str(
                        ipaddress.ip_network(cidr)[1]
                    )
                    tmp_template[tmpl_name]["properties"]["network_name"] = net_name
                else:
                    if "cidr" not in tmp_template[tmpl_name]["properties"]:
                        cidr = utils.generate_random_subnet()
                        tmp_template[tmpl_name]["properties"]["cidr"] = cidr
                        tmp_template[tmpl_name]["properties"]["end_ip"] = str(
                            ipaddress.ip_network(cidr)[-4]
                        )
                        tmp_template[tmpl_name]["properties"]["start_ip"] = str(
                            ipaddress.ip_network(cidr)[10]
                        )
                        tmp_template[tmpl_name]["properties"]["gateway_ip"] = str(
                            ipaddress.ip_network(cidr)[1]
                        )
                    else:
                        if "end_ip" not in tmp_template[tmpl_name]["properties"]:
                            cidr = tmp_template[tmpl_name]["properties"]["cidr"]
                            tmp_template[tmpl_name]["properties"]["end_ip"] = str(
                                ipaddress.ip_network(cidr)[-4]
                            )
                        if "start_ip" not in tmp_template[tmpl_name]["properties"]:
                            cidr = tmp_template[tmpl_name]["properties"]["cidr"]
                            tmp_template[tmpl_name]["properties"]["start_ip"] = str(
                                ipaddress.ip_network(cidr)[10]
                            )
                        if "gateway_ip" not in tmp_template[tmpl_name]["properties"]:
                            cidr = tmp_template[tmpl_name]["properties"]["cidr"]
                            tmp_template[tmpl_name]["properties"]["gateway_ip"] = str(
                                ipaddress.ip_network(cidr)[1]
                            )
                    if "network_name" not in tmp_template[tmpl_name]["properties"]:
                        tmp_template[tmpl_name]["properties"]["network_name"] = net_name
        return tmp_template

    def resolve_get_property_functions(self, data=None, tmpl_name=None):
        if data is None:
            data = self.node_templates
        if isinstance(data, dict):
            new_data = {}
            for key, value in data.items():
                if key == "get_property":
                    new_data = self.get_property_value(value, tmpl_name)
                else:
                    new_data[key] = self.resolve_get_property_functions(
                        value, tmpl_name if tmpl_name is not None else key
                    )
            return new_data
        elif isinstance(data, list):
            new_data = []
            for v in data:
                new_data.append(self.resolve_get_property_functions(v, tmpl_name))
            return new_data
        elif isinstance(data, GetProperty):
            value = data.args
            return self.get_property_value(value, tmpl_name)
        return data

    def get_property_value(self, value, tmpl_name):
        prop_keys = []
        tmpl_properties = None
        if value[0] == "self":
            value[0] = tmpl_name
        if value[0] == "host":
            value = [tmpl_name, "host"] + value[1:]
        node_tmpl = self.node_templates[value[0]]
        if node_tmpl.get("requirements", None) is not None:
            for req in node_tmpl["requirements"]:
                if req.get(value[1], None) is not None:
                    if req[value[1]].get("node", None) is not None:
                        return self.get_property_value(
                            [req[value[1]]["node"]] + value[2:], req[value[1]]["node"]
                        )
                    if req[value[1]].get("node_filter", None) is not None:
                        tmpl_properties = {}
                        node_filter_props = req[value[1]]["node_filter"].get(
                            "properties", []
                        )
                        for prop in node_filter_props:
                            tmpl_properties.update(prop)
                        prop_keys = value[2:]
        if node_tmpl.get("capabilities", {}).get(value[1], None) is not None:
            tmpl_properties = node_tmpl["capabilities"][value[1]].get("properties", {})
            prop_keys = value[2:]
        if node_tmpl.get("properties", {}).get(value[1], None) is not None:
            tmpl_properties = node_tmpl["properties"]
            prop_keys = value[1:]

        for key in prop_keys:
            if tmpl_properties.get(key, None) is None:
                tmpl_properties = None
                break
            tmpl_properties = tmpl_properties[key]
        if tmpl_properties is None:
            logging.error("Failed to get property: %s." % yaml.dump(value))
            sys.exit(1)
        return tmpl_properties

    def create_config_json(
        self,
    ):  # возможно надо будет попытаться это все переписать на маппинг
        odl_config = {
            "service-function-path": "to be auto created from service-function-chains",
            "rendered-service-path": "to be auto created from service-function-chains and service-function-path",
        }
        sf_addresses = []
        sff_addresses = []
        sf_names = {}
        for key in self.network_service_keys:
            element = self.node_templates.get(key)
            if element["type"] == "nfv.nodes.ns.NSD":
                for req in element.get("requirements", []):
                    if req.get("vnffgd"):
                        logging.info(
                            "VNFFG is found, trying to generate setup config for ODL"
                        )
                        vnffg = self.node_templates.get(req["vnffgd"])
                        for req in vnffg.get("requirements", []):
                            if req.get("nfpd"):
                                nfpd = self.node_templates.get(req["nfpd"])
                                nfpd_name = req["nfpd"]
                                rules = nfpd.get("properties").get("nfpRule")
                                for rule in rules:
                                    if rule.get("direction") == "Bidirectional":
                                        rule["action"] = req["nfpd"]
                                        rule["direction"] = "Forward"
                                        utils.deep_update_dict(
                                            odl_config,
                                            {
                                                "acls": [
                                                    {
                                                        "aces": [rule],
                                                        "type": "ipv4-acl",
                                                        "name": rule["name"],
                                                    }
                                                ],
                                                "service-function-classifiers": [
                                                    {
                                                        "acl": rule["name"],
                                                        "interface": "veth-br",
                                                        "name": "cls"
                                                        + "-"
                                                        + rule["name"],
                                                    }
                                                ],
                                            },
                                        )
                                        rule = copy.deepcopy(rule)
                                        tmp = rule["sprange"]
                                        rule["sprange"] = rule["dprange"]
                                        rule["dprange"] = tmp
                                        rule["direction"] = "Reverse"
                                        rule["name"] = rule["name"] + "-" + "reverse"
                                        utils.deep_update_dict(
                                            odl_config,
                                            {
                                                "acls": [
                                                    {
                                                        "aces": [rule],
                                                        "type": "ipv4-acl",
                                                        "name": rule["name"],
                                                    }
                                                ],
                                                "service-function-classifiers": [
                                                    {
                                                        "acl": rule["name"],
                                                        "interface": "veth-br",
                                                        "name": "cls"
                                                        + "-"
                                                        + rule["name"],
                                                    }
                                                ],
                                            },
                                        )
                                    else:
                                        utils.deep_update_dict(
                                            odl_config,
                                            {
                                                "acls": [
                                                    {
                                                        "aces": [rule],
                                                        "type": "ipv4-acl",
                                                        "name": rule["name"],
                                                    }
                                                ],
                                                "service-function-classifiers": [
                                                    {
                                                        "acl": rule["name"],
                                                        "interface": "veth-br",
                                                        "name": "cls"
                                                        + "-"
                                                        + rule["name"],
                                                    }
                                                ],
                                            },
                                        )
                                local_addresses = []
                                for req in nfpd.get("requirements", []):
                                    if req.get("cpd"):
                                        address = (
                                            self.new_element_templates.get(req["cpd"])
                                            .get("properties")
                                            .get("ip_address")
                                        )
                                        sf_addresses.append(address)
                                        local_addresses.append(address)
                                utils.deep_update_dict(
                                    odl_config,
                                    {
                                        "service-function-chains": [
                                            {
                                                "name": nfpd_name,
                                                "symmetric": "true",
                                                "service_function": local_addresses,
                                            }
                                        ]
                                    },
                                )
                        for req in vnffg.get("requirements"):
                            if req.get("cpdPoolId"):
                                pool = self.node_templates.get(req["cpdPoolId"])
                                for req in pool.get("requirements", []):
                                    if req.get("cpdId"):
                                        address = (
                                            self.new_element_templates.get(req["cpdId"])
                                            .get("properties")
                                            .get("ip_address")
                                        )
                                        sff = True
                                        cpd = self.node_templates.get(req["cpdId"])
                                        for possible_req in cpd.get("requirements", []):
                                            if possible_req.get("VDUCpd"):
                                                cpd = self.node_templates.get(
                                                    possible_req["VDUCpd"]
                                                )
                                                sff = False
                                                break
                                        if sff:
                                            sff_addresses.append(address)

                                        for possible_req in cpd.get("requirements", []):
                                            if possible_req.get("intCpd"):
                                                name = possible_req.get("intCpd")
                                        utils.deep_update_dict(
                                            odl_config,
                                            {
                                                "service-nodes": [
                                                    {
                                                        "ip-address": address,
                                                        "name": "sn_" + name,
                                                    }
                                                ]
                                            },
                                        )
                                        # ищем VNFD
                                        for elem in self.node_templates.values():
                                            reqs = elem.get("requirements", [])
                                            for req in reqs:
                                                if (
                                                    req.get("vdu") == name
                                                ):  # ну пока будет работать
                                                    vnfd_type = self.vnf_mapping[
                                                        elem["type"].split(SEPARATOR)[
                                                            -1
                                                        ]
                                                    ]
                                                    if vnfd_type == "error":
                                                        logging.error(
                                                            "This VNFD cant be used with VNFFG"
                                                        )
                                                        sys.exit(1)
                                                    break
                                        if address in sf_addresses:
                                            sf_names.update({address: name})
                                            utils.deep_update_dict(
                                                odl_config,
                                                {
                                                    "service-functions": [
                                                        {
                                                            "ip-address": address,
                                                            "name": name,
                                                            "service_node": "sn_"
                                                            + name,
                                                            "sff_name": "",
                                                            "type": vnfd_type,
                                                        }
                                                    ]
                                                },
                                            )
                                        else:
                                            utils.deep_update_dict(
                                                odl_config,
                                                {
                                                    "service-function-forwarders": [
                                                        {
                                                            "ip-address": address,
                                                            "name": name,
                                                            "service_node": "sn_"
                                                            + name,
                                                            "service_function": [],
                                                        }
                                                    ]
                                                },
                                            )
                    if req.get("virtualLinkDesc"):
                        start = int(
                            ipaddress.IPv4Address(
                                self.new_element_templates[req["virtualLinkDesc"]][
                                    "properties"
                                ]["start_ip"]
                            )
                        )
                        end = int(
                            ipaddress.IPv4Address(
                                self.new_element_templates[req["virtualLinkDesc"]][
                                    "properties"
                                ]["end_ip"]
                            )
                        )
                        address = str(
                            ipaddress.IPv4Address(utils.get_random_int(start, end))
                        )  # нет защиты от совпадений
                        # TODO: сделать
                        utils.deep_update_dict(self.controller, {"ip-address": address})
                        utils.deep_update_dict(
                            odl_config, {"controller": self.controller}
                        )
                        if self.address_config == "port_name":
                            utils.deep_update_dict(
                                self.tosca_controller["controller"],
                                {
                                    "properties": {
                                        "ports": {"internal_1": {"port_name": address}}
                                    }
                                },
                            )
                        elif self.address_config == "addresses":
                            utils.deep_update_dict(
                                self.tosca_controller["controller"],
                                {
                                    "properties": {
                                        "ports": {
                                            "internal_1": {"addresses": [address]}
                                        }
                                    }
                                },
                            )
                        else:
                            logging.error(
                                "Unknown address_config type in orchestrator config."
                            )
                            sys.exit(1)
                        utils.deep_update_dict(
                            self.tosca_controller["controller_port"],
                            {
                                "properties": {"ip_address": address},
                                "requirements": [{"link": req["virtualLinkDesc"]}],
                            },
                        )
        map_sf_sff = self.split_sf_sff(sf_addresses, sff_addresses)
        inverse_map_sf_sff = {}
        for key, value in map_sf_sff.items():
            for elem in value:
                inverse_map_sf_sff.update({sf_names[elem]: key})
        for sfc in odl_config.get("service-function-chains", []):
            new_sf = []
            sfc_len = len(sfc["service_function"])
            for i in range(sfc_len):
                new_sf.append(sf_names[sfc["service_function"][i]])
                for element, value in self.new_element_templates.items():
                    for req in value.get("requirements", []):
                        if req.get("host") == sf_names[sfc["service_function"][i]]:
                            utils.deep_update_dict(
                                self.new_element_templates.get(element),
                                {
                                    "interfaces": {
                                        "Standard": {
                                            self.vnf_script_type: {
                                                "inputs": {
                                                    "service_function_chains": {
                                                        "RSP" + "-" + sfc["name"]: i,
                                                        "RSP"
                                                        + "-"
                                                        + sfc["name"]
                                                        + "-"
                                                        + "Reverse": sfc_len
                                                        - i
                                                        - 1,
                                                    },
                                                    "controller": copy.deepcopy(
                                                        self.controller
                                                    ),
                                                    "forwarder": {
                                                        "ip-address": inverse_map_sf_sff.get(
                                                            sf_names[
                                                                sfc["service_function"][
                                                                    i
                                                                ]
                                                            ]
                                                        )
                                                    },
                                                }
                                            }
                                        }
                                    }
                                },
                            )
            sfc["service_function"] = new_sf
        for sff in odl_config.get("service-function-forwarders", []):
            utils.deep_update_dict(
                self.new_element_templates.get(self.software_prefix + sff["name"]),
                {
                    "interfaces": {
                        "Standard": {
                            self.vnf_script_type: {
                                "implementation": self.vnf_script_type
                                + "_"
                                + "forwarder.yaml",
                                "inputs": {
                                    "controller": copy.deepcopy(self.controller),
                                },
                            }
                        }
                    },
                    "requirements": [{"host": sff["name"]}],
                },
            )
            if sff["ip-address"] in map_sf_sff:
                sff["service_function"] = [
                    sf_names[x] for x in map_sf_sff[sff["ip-address"]]
                ]
                for sf in odl_config.get("service-functions", []):
                    if sf["ip-address"] in map_sf_sff[sff["ip-address"]]:
                        sf["sff_name"] = sff["name"]
            else:
                for cls in odl_config.get("service-function-classifiers", []):
                    if not cls.get("sff"):
                        cls["sff"] = sff["name"]
                        cls["name"] = cls["name"] + "." + sff["name"]
                    else:
                        cls = copy.deepcopy(cls)
                        cls["name"] = cls["name"].split(SEPARATOR)[0]
                        cls["name"] = cls["name"] + "." + sff["name"]
                        cls["sff"] = sff["name"]
                        utils.deep_update_dict(
                            odl_config, {"service-function-classifiers": [cls]}
                        )
                    script = self.vnf_script_type + "_" + "classifier.yaml"
                    utils.deep_update_dict(
                        self.new_element_templates.get(
                            self.software_prefix + cls["sff"]
                        ),
                        {
                            "interfaces": {
                                "Standard": {
                                    self.vnf_script_type: {
                                        "implementation": script,
                                        "inputs": {
                                            "controller": copy.deepcopy(
                                                self.controller
                                            ),
                                        },
                                    }
                                }
                            }
                        },
                    )
        generate_restconf_files_for_create(
            json.dumps(odl_config, ensure_ascii=False, indent=4),
            output_dir=self.output_dir,
        )
        # for debug
        # print(json.dumps(odl_config, ensure_ascii=False, indent=4))

    @staticmethod
    def split_sf_sff(sf_addresses, sff_addresses):
        dict_result = {}
        num_parts = len(sff_addresses)
        part_length = len(sf_addresses) // num_parts
        result = [
            sf_addresses[i : i + part_length]
            for i in range(0, (num_parts - 1) * part_length, part_length)
        ]
        result.append(sf_addresses[(num_parts - 1) * part_length :])
        for i in range(len(sff_addresses)):
            dict_result.update({sff_addresses[i]: result[i]})
        return dict_result

    def translate_to_tosca(self):
        self.new_element_templates = {}
        element_templates = copy.copy(self.node_templates)
        element_templates.update(copy.copy(self.relationship_templates))
        for tmpl_name, element in element_templates.items():
            (namespace, element_type, element_name) = utils.tosca_type_parse(
                element["type"]
            )
            if len(element_name.split(SEPARATOR)) > 1:
                subnamespace = element_name.split(SEPARATOR)[0]
                if subnamespace == "ns":
                    self.network_service_keys.append(tmpl_name)
            if namespace == "nfv":
                tmp_template = {}
                for key, value in self.mapping.items():
                    if element["type"] == key:
                        for k, v in value.items():
                            if k in element:
                                for atr, atr_k in v.items():
                                    iter = element[k]
                                    for e in utils.str_dots_to_arr(atr):
                                        if isinstance(iter, dict):
                                            if e in iter:
                                                iter = iter[e]
                                            else:
                                                iter = None
                                                break
                                        elif isinstance(iter, list):
                                            flag = False
                                            for tmp in iter:
                                                if e in tmp:
                                                    iter = tmp[e]
                                                    flag = True
                                                    break
                                            if not flag:
                                                iter = None
                                                break
                                    if iter:
                                        for elem in atr_k:
                                            if "rename" in elem:
                                                tmpl_name += "_" + elem["rename"]
                                                if tmpl_name not in tmp_template:
                                                    tmp_template[tmpl_name] = {}
                                            if "parameter" in elem:
                                                if "format" in elem:
                                                    if tmpl_name in tmp_template:
                                                        tmp_template[
                                                            tmpl_name
                                                        ] = utils.deep_update_dict(
                                                            tmp_template[tmpl_name],
                                                            utils.str_dots_to_dict(
                                                                elem["parameter"],
                                                                elem["format"].format(
                                                                    iter
                                                                ),
                                                            ),
                                                        )
                                                    else:
                                                        tmp_template[
                                                            tmpl_name
                                                        ] = utils.str_dots_to_dict(
                                                            elem["parameter"],
                                                            elem["format"].format(iter),
                                                        )
                                                else:
                                                    if tmpl_name in tmp_template:
                                                        tmp_template[
                                                            tmpl_name
                                                        ] = utils.deep_update_dict(
                                                            tmp_template[tmpl_name],
                                                            utils.str_dots_to_dict(
                                                                elem["parameter"], iter
                                                            ),
                                                        )
                                                    else:
                                                        tmp_template[
                                                            tmpl_name
                                                        ] = utils.str_dots_to_dict(
                                                            elem["parameter"], iter
                                                        )
                                            if "type" in elem:
                                                if tmpl_name in tmp_template:
                                                    if (
                                                        "type"
                                                        not in tmp_template[tmpl_name]
                                                    ):
                                                        tmp_template[
                                                            tmpl_name
                                                        ] = utils.deep_update_dict(
                                                            tmp_template[tmpl_name],
                                                            {"type": elem["type"]},
                                                        )
                                                else:
                                                    tmp_template[tmpl_name] = {
                                                        "type": elem["type"]
                                                    }
                                            else:
                                                logging.error(
                                                    "Error! Undefined node type in template."
                                                )
                                                sys.exit(1)

                                            if "node_name" in elem:
                                                if elem["node_name"] == "check":
                                                    if (
                                                        iter
                                                        not in self.new_element_templates
                                                    ):
                                                        logging.warning(
                                                            "Error! The requirement is not defined."
                                                        )
                                                elif elem["node_name"] == "rename":
                                                    if (
                                                        iter
                                                        in self.new_element_templates
                                                    ):
                                                        if (
                                                            "requirement_format"
                                                            not in elem
                                                        ):
                                                            tmp_template[
                                                                tmpl_name
                                                            ] = utils.deep_update_dict(
                                                                tmp_template[tmpl_name],
                                                                self.new_element_templates.pop(
                                                                    iter
                                                                ),
                                                            )
                                                            self.additional_keys += [
                                                                iter
                                                            ]
                                                        else:
                                                            if (
                                                                elem[
                                                                    "requirement_format"
                                                                ].format(iter)
                                                                not in self.new_element_templates
                                                            ):
                                                                self.new_element_templates[
                                                                    elem[
                                                                        "requirement_format"
                                                                    ].format(iter)
                                                                ] = {}
                                                            tmp_template[
                                                                tmpl_name
                                                            ] = utils.deep_update_dict(
                                                                tmp_template[tmpl_name],
                                                                self.new_element_templates.pop(
                                                                    elem[
                                                                        "requirement_format"
                                                                    ].format(iter)
                                                                ),
                                                            )
                                                            self.additional_keys += [
                                                                elem[
                                                                    "requirement_format"
                                                                ].format(iter)
                                                            ]
                                                    else:
                                                        logging.warning(
                                                            "Error! The requirement is not defined."
                                                        )
                                                elif elem["node_name"] == "not change":
                                                    if (
                                                        iter
                                                        in self.new_element_templates
                                                    ):
                                                        if (
                                                            "requirement_format"
                                                            not in elem
                                                        ):
                                                            self.new_element_templates[
                                                                iter
                                                            ] = utils.deep_update_dict(
                                                                self.new_element_templates[
                                                                    iter
                                                                ],
                                                                tmp_template[tmpl_name],
                                                            )
                                                        else:
                                                            if (
                                                                elem[
                                                                    "requirement_format"
                                                                ].format(iter)
                                                                not in self.new_element_templates
                                                            ):
                                                                self.new_element_templates[
                                                                    elem[
                                                                        "requirement_format"
                                                                    ].format(iter)
                                                                ] = {}
                                                            self.new_element_templates[
                                                                elem[
                                                                    "requirement_format"
                                                                ].format(iter)
                                                            ] = utils.deep_update_dict(
                                                                self.new_element_templates[
                                                                    elem[
                                                                        "requirement_format"
                                                                    ].format(iter)
                                                                ],
                                                                tmp_template[tmpl_name],
                                                            )
                                                        self.new_additional_keys += [
                                                            tmpl_name
                                                        ]
                                                    else:
                                                        logging.warning(
                                                            "Error! The requirement is not defined."
                                                        )
                                                else:
                                                    logging.warning(
                                                        "Error! unknown type of node_name."
                                                    )

                        self.new_element_templates = utils.deep_update_dict(
                            self.new_element_templates,
                            self.translate_specific_types(tmp_template, tmpl_name),
                        )
                        logging.info("Successfully parsed {} node.".format(tmpl_name))
        basic_script = self.basic_script_type + "_" + self.provider + ".yaml"
        vnf_script = self.vnf_script_type + "_" + self.provider + ".yaml"
        controller_script = self.basic_script_type + "_" + "controller" + ".yaml"
        forwarder_script = self.vnf_script_type + "_" + "forwarder" + ".yaml"
        classifier_script = self.vnf_script_type + "_" + "classifier" + ".yaml"

        if len(self.network_service_keys) > 0:
            self.create_config_json()
            self.update_scripts(
                vnf_script,
                self.vnf_scripts,
                ADD_PATH + self.provider + "/" + self.provider + ".yaml",
            )
            self.update_scripts(
                forwarder_script,
                self.vnf_scripts,
                ADD_PATH + self.provider + "/" + "forwarder" + ".yaml",
            )
            self.update_scripts(
                classifier_script,
                self.vnf_scripts,
                ADD_PATH + self.provider + "/" + "classifier" + ".yaml",
            )
            self.update_scripts(
                controller_script,
                self.basic_scripts,
                ADD_PATH + self.provider + "/" + "controller" + ".yaml",
            )
        for key in self.new_element_templates:
            if key in element_templates:
                element_templates.pop(key)
        for key in self.additional_keys:
            if key in element_templates:
                element_templates.pop(key)
        for key in self.network_service_keys:
            if key in element_templates:
                element_templates.pop(key)
        for key in self.new_additional_keys:
            if key in self.new_element_templates:
                self.new_element_templates.pop(key)
        logging.info("Successfully delete unused nodes.")
        vnffiles = [
            f
            for f in os.listdir(
                utils.get_project_root_path() + VNF_PATH + self.provider + "/"
            )
            if os.path.isfile(
                os.path.join(
                    utils.get_project_root_path() + VNF_PATH + self.provider + "/", f
                )
            )
        ]
        self.update_scripts(
            basic_script, self.basic_scripts, PROVIDERS_PATH + self.provider + ".yaml"
        )
        logging.info("Successfully loaded provider template file.")
        for file in vnffiles:
            self.update_scripts(
                vnf_script, self.vnf_scripts, VNF_PATH + self.provider + "/" + file
            )
        logging.info("Successfully loaded VNF template files.")
        for key, value in self.new_element_templates.items():
            if self.basic_configure_node_type == value["type"]:
                self.new_element_templates[key] = utils.deep_update_dict(
                    self.new_element_templates[key],
                    {
                        "interfaces": {
                            "Standard": {
                                self.basic_script_type: {"implementation": basic_script}
                            }
                        }
                    },
                )
            if self.vnf_configure_node_type == value["type"]:
                interfaces = self.new_element_templates[key].get("interfaces")
                if interfaces:
                    if (
                        interfaces.get("Standard")
                        and interfaces.get("Standard").get(self.vnf_script_type)
                        and "VNF_types"
                        in interfaces.get("Standard")
                        .get(self.vnf_script_type)
                        .get("implementation")
                    ):
                        self.new_element_templates[key] = utils.deep_update_dict(
                            self.new_element_templates[key],
                            {
                                "interfaces": {
                                    "Standard": {
                                        self.vnf_script_type: {
                                            "implementation": vnf_script
                                        }
                                    }
                                }
                            },
                        )
        if len(self.network_service_keys) > 0:
            for node in self.new_element_templates:
                if self.software_prefix in node:
                    utils.deep_update_dict(
                        self.new_element_templates[
                            node
                        ],  # ну мб это плохое решение, но попробовать стоит
                        {"requirements": [{"dependency": "software_for_controller"}]},
                    )
            utils.deep_update_dict(self.new_element_templates, self.tosca_controller)
        element_templates = utils.deep_update_dict(
            element_templates, self.new_element_templates
        )
        self.result_template["tosca_definitions_version"] = self.version
        self.result_template["topology_template"] = {}
        self.result_template["topology_template"]["node_templates"] = element_templates

    def update_scripts(self, script, scripts, path):
        try:
            with open(
                utils.get_project_root_path() + path,
                "r+",
            ) as f:
                script_lines = f.readlines()
        except:
            logging.error("Error! Failed to open file %s." % script)
            sys.exit(1)
        if script not in scripts:
            scripts[script] = script_lines
        else:
            scripts[script] += script_lines
