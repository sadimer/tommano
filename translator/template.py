import copy
import translator.utils as utils
import ipaddress
import yaml
import logging
import sys
import os

DEF_PATH = '/definitions/'
TRANS_PATH = '/translator/'

from toscaparser.functions import GetProperty

class ToscaNormativeTemplate(object):
    def __init__(self, tosca_parser_tpl, yaml_dict_mapping):
        topology_template = tosca_parser_tpl.topology_template
        self.definitions = topology_template.custom_defs
        self.node_templates = {}
        self.relationship_templates = {}
        self.version = tosca_parser_tpl.version
        for tmpl in topology_template.nodetemplates:
            self.node_templates[tmpl.name] = tmpl.entity_tpl
        for tmpl in topology_template.relationship_templates:
            self.relationship_templates[tmpl.name] = tmpl.entity_tpl
        self.node_templates = self.resolve_get_property_functions(self.node_templates)
        self.relationship_templates = self.resolve_get_property_functions(self.relationship_templates)
        self.mapping = yaml_dict_mapping
        self.expand_mapping()
        self.generated_scripts = {}
        self.num_addresses = {}
        self.translate_to_tosca()

    def get_result(self):
        return self.result_template, self.generated_scripts

    def expand_mapping(self):
        for key in self.mapping:
            while key in self.definitions and \
                    'derived_from' in self.definitions[key] and \
                    self.definitions[key]['derived_from'] in self.definitions and \
                    self.definitions[key]['derived_from'] in self.mapping:
                self.mapping[key] = utils.deep_update_dict(self.mapping[key], self.mapping[self.definitions[key]['derived_from']])
                key = self.definitions[key]['derived_from']


    # типы которых нет в nfv, но они нужны для развертывания
    def translate_specific_types(self, tmp_template, tmpl_name):
        if tmp_template != {}:
            if tmp_template[tmpl_name]['type'] == 'tosca.nodes.Compute':
                if 'interfaces' in tmp_template[tmpl_name] and 'Standard' in tmp_template[tmpl_name]['interfaces'] and \
                        'configure' in tmp_template[tmpl_name]['interfaces']['Standard']:
                    if 'implementation' in tmp_template[tmpl_name]['interfaces']['Standard']['configure']:
                        def_file = utils.get_project_root_path() + DEF_PATH + \
                                       tmp_template[tmpl_name]['interfaces']['Standard']['configure']['implementation']
                    elif not isinstance(tmp_template[tmpl_name]['interfaces']['Standard']['configure'], dict):
                        def_file = utils.get_project_root_path() + DEF_PATH + \
                                       tmp_template[tmpl_name]['interfaces']['Standard']['configure']
                    try:
                        with open(def_file, "r+") as f:
                            vnf_def = f.readlines()
                    except:
                        logging.error("Error! Failed to open VNF template file")
                        sys.exit(1)

                    if 'properties' in tmp_template[tmpl_name]:
                        if 'meta' in tmp_template[tmpl_name]['properties']:
                            script = "configure_" + tmp_template[tmpl_name]['properties']['meta'] + ".yaml"
                            if script not in self.generated_scripts:
                                self.generated_scripts[script] = vnf_def
                            else:
                                self.generated_scripts[script] += vnf_def
                        else:
                            logging.error("Error! VNFD hasnt meta, plase check mapping for VNFD")
                            sys.exit(1)

            if tmp_template[tmpl_name]['type'] == 'tosca.nodes.network.Port':
                if 'properties' not in tmp_template[tmpl_name] or 'ip_address' not in tmp_template[tmpl_name]['properties']:
                    # проверь всегда ли VL к этому моменту будет сощдана (если нет будет ошибка по requirements)
                    if 'properties' not in tmp_template[tmpl_name]:
                        tmp_template[tmpl_name]['properties'] = {}
                    if 'requirements' in tmp_template[tmpl_name]:
                        flag = False
                        # адрес в vnf вещь необязательная, изголяемся как хотим
                        for elem in tmp_template[tmpl_name]['requirements']:
                            if 'link' in elem:
                                start = int(ipaddress.IPv4Address(self.new_element_templates[elem['link']]['properties']['start_ip']))
                                end = int(ipaddress.IPv4Address(self.new_element_templates[elem['link']]['properties']['end_ip']))
                                address = str(ipaddress.IPv4Address(utils.get_random_int(start, end)))
                                tmp_template[tmpl_name]['properties']['ip_address'] = address
                                flag = True
                                break
                        if not flag:
                            logging.error("Error! No link requirement")
                            sys.exit(1)
                else:
                    # не самое удачное решение, но работает
                    if 'requirements' in tmp_template[tmpl_name]:
                        address = tmp_template[tmpl_name]['properties']['ip_address']
                        ext = False
                        for elem in tmp_template[tmpl_name]['requirements']:
                            if 'link' in elem:
                                ext = False
                                if 'properties' in self.new_element_templates[elem['link']] and 'cidr' in self.new_element_templates[elem['link']]['properties']:
                                    cidr = self.new_element_templates[elem['link']]['properties']['cidr']
                                else:
                                    logging.error("Error! Network dont have cidr")
                                    sys.exit(1)
                                break
                            else:
                                ext = True
                        for elem in tmp_template[tmpl_name]['requirements']:
                            if 'binding' in elem:
                                if elem['binding'] not in self.num_addresses:
                                    self.num_addresses[elem['binding']] = [address]
                                elif address not in self.num_addresses[elem['binding']]:
                                    self.num_addresses[elem['binding']] += [address]
                                else:
                                    break
                                # убрать?
                                if ext:
                                    self.new_element_templates[elem['binding']] = utils.deep_update_dict(
                                        self.new_element_templates[elem['binding']],
                                        {'properties': {'ports': {'external': {'addresses': [address]}}}})
                                else:
                                    self.new_element_templates[elem['binding']] = utils.deep_update_dict(
                                        self.new_element_templates[elem['binding']],
                                        {'properties': {'ports': {'internal': {'addresses': [address]}}}})
                                    self.new_element_templates[elem['binding']] = utils.deep_update_dict(
                                        self.new_element_templates[elem['binding']], {'interfaces': {'Standard': {
                                            'configure': {'inputs': {
                                                'iPAddressDict': {len(self.num_addresses[elem['binding']]): {address: cidr}}}}}}})
                                break
            elif tmp_template[tmpl_name]['type'] == 'tosca.nodes.network.Network':
                net_name = 'net' + str(utils.get_random_int(0, 1024))
                if 'properties' not in tmp_template[tmpl_name]:
                    cidr = utils.generate_random_subnet()
                    tmp_template[tmpl_name]['properties'] = {}
                    tmp_template[tmpl_name]['properties']['cidr'] = cidr
                    tmp_template[tmpl_name]['properties']['end_ip'] = str(ipaddress.ip_network(cidr)[-4])
                    tmp_template[tmpl_name]['properties']['start_ip'] = str(ipaddress.ip_network(cidr)[10])
                    tmp_template[tmpl_name]['properties']['gateway_ip'] = str(ipaddress.ip_network(cidr)[1])
                    tmp_template[tmpl_name]['properties']['network_name'] = net_name
                else:
                    if 'cidr' not in tmp_template[tmpl_name]['properties']:
                        cidr = utils.generate_random_subnet()
                        tmp_template[tmpl_name]['properties']['cidr'] = cidr
                        tmp_template[tmpl_name]['properties']['end_ip'] = str(ipaddress.ip_network(cidr)[-4])
                        tmp_template[tmpl_name]['properties']['start_ip'] = str(ipaddress.ip_network(cidr)[10])
                        tmp_template[tmpl_name]['properties']['gateway_ip'] = str(ipaddress.ip_network(cidr)[1])
                    else:
                        if 'end_ip' not in tmp_template[tmpl_name]['properties']:
                            cidr = tmp_template[tmpl_name]['properties']['cidr']
                            tmp_template[tmpl_name]['properties']['end_ip'] = str(ipaddress.ip_network(cidr)[-4])
                        if 'start_ip' not in tmp_template[tmpl_name]['properties']:
                            cidr = tmp_template[tmpl_name]['properties']['cidr']
                            tmp_template[tmpl_name]['properties']['start_ip'] = str(ipaddress.ip_network(cidr)[10])
                        if 'gateway_ip' not in tmp_template[tmpl_name]['properties']:
                            cidr = tmp_template[tmpl_name]['properties']['cidr']
                            tmp_template[tmpl_name]['properties']['gateway_ip'] = str(ipaddress.ip_network(cidr)[1])
                    if 'network_name' not in tmp_template[tmpl_name]['properties']:
                        tmp_template[tmpl_name]['properties']['network_name'] = net_name
        return tmp_template

    def resolve_get_property_functions(self, data=None, tmpl_name=None):
        if data is None:
            data = self.node_templates
        if isinstance(data, dict):
            new_data = {}
            for key, value in data.items():
                if key == 'get_property':
                    new_data = self.get_property_value(value, tmpl_name)
                else:
                    new_data[key] = self.resolve_get_property_functions(value, tmpl_name if tmpl_name is not None else key)
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
        if value[0] == 'self':
            value[0] = tmpl_name
        if value[0] == 'host':
            value = [tmpl_name, 'host'] + value[1:]
        node_tmpl = self.node_templates[value[0]]
        if node_tmpl.get('requirements', None) is not None:
            for req in node_tmpl['requirements']:
                if req.get(value[1], None) is not None:
                    if req[value[1]].get('node', None) is not None:
                        return self._get_property_value([req[value[1]]['node']] + value[2:], req[value[1]]['node'])
                    if req[value[1]].get('node_filter', None) is not None:
                        tmpl_properties = {}
                        node_filter_props = req[value[1]]['node_filter'].get('properties', [])
                        for prop in node_filter_props:
                            tmpl_properties.update(prop)
                        prop_keys = value[2:]
        if node_tmpl.get('capabilities', {}).get(value[1], None) is not None:
            tmpl_properties = node_tmpl['capabilities'][value[1]].get('properties', {})
            prop_keys = value[2:]
        if node_tmpl.get('properties', {}).get(value[1], None) is not None:
            tmpl_properties = node_tmpl['properties']
            prop_keys = value[1:]

        for key in prop_keys:
            if tmpl_properties.get(key, None) is None:
                tmpl_properties = None
                break
            tmpl_properties = tmpl_properties[key]
        if tmpl_properties is None:
            logging.error("Failed to get property: %s" % yaml.dump(value))
            sys.exit(1)
        return tmpl_properties

    def translate_to_tosca(self):
        self.result_template = {}
        self.new_element_templates = {}
        additional_keys = []
        new_additional_keys = []
        element_templates = copy.copy(self.node_templates)
        # тут пока хз че делать
        # element_templates.update(copy.copy(self.relationship_templates))
        for tmpl_name, element in element_templates.items():
            (namespace, element_type, element_name) = utils.tosca_type_parse(element['type'])
            if namespace == 'nfv':
                tmp_template = {}
                for key, value in self.mapping.items():
                    if element['type'] == key:
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
                                            if 'parameter' in elem:
                                                if 'format' in elem:
                                                    if elem['format'] == '{node_name}':
                                                        if tmpl_name in tmp_template:
                                                            tmp_template[tmpl_name] = utils.deep_update_dict(
                                                                tmp_template[tmpl_name],
                                                                utils.str_dots_to_dict(elem['parameter'],
                                                                                       tmpl_name))
                                                        else:
                                                            tmp_template[tmpl_name] = utils.str_dots_to_dict(
                                                                elem['parameter'],
                                                                tmpl_name)
                                                    else:
                                                        if tmpl_name in tmp_template:
                                                            tmp_template[tmpl_name] = utils.deep_update_dict(tmp_template[tmpl_name],
                                                                                                             utils.str_dots_to_dict(elem['parameter'],
                                                                                                             elem['format'].format(iter)))
                                                        else:
                                                            tmp_template[tmpl_name] = utils.str_dots_to_dict(elem['parameter'],
                                                                                                             elem['format'].format(iter))
                                                else:
                                                    if tmpl_name in tmp_template:
                                                        tmp_template[tmpl_name] = utils.deep_update_dict(tmp_template[tmpl_name],
                                                                                                         utils.str_dots_to_dict(elem['parameter'], iter))
                                                    else:
                                                        tmp_template[tmpl_name] = utils.str_dots_to_dict(elem['parameter'], iter)
                                            if 'type' in elem:
                                                if tmpl_name in tmp_template:
                                                    # ПЕРВЫЙ ТАЙП ВСТРЕТИВШИЙСЯ В ШАБЛОНЕ БУДТ ЗАПИСАН - НЕ ЕСТЬ ХОРОШО, ПОТОМ ПЕРЕДЕЛАТЬ
                                                    if 'type' not in tmp_template[tmpl_name]:
                                                        tmp_template[tmpl_name] = utils.deep_update_dict(tmp_template[tmpl_name],
                                                                                                         {'type': elem['type']})
                                                else:
                                                    tmp_template[tmpl_name] = {'type': elem['type']}
                                            else:
                                                logging.error("Error! Undefined node type in template")
                                                sys.exit(1)

                                            if 'node_name' in elem:
                                                if elem['node_name'] == 'check':
                                                    if iter not in self.new_element_templates or elem['type'] != self.new_element_templates[iter]['type']:
                                                        logging.error("Error! The requirement is not defined")
                                                        sys.exit(1)
                                                elif elem['node_name'] == 'rename':
                                                    if iter in self.new_element_templates and elem['type'] == self.new_element_templates[iter]['type']:
                                                        tmp_template[tmpl_name] = utils.deep_update_dict(tmp_template[tmpl_name],
                                                                                                         self.new_element_templates.pop(iter))
                                                        additional_keys += [iter]
                                                    else:
                                                        logging.error("Error! The requirement is not defined")
                                                        sys.exit(1)
                                                elif elem['node_name'] == 'not change':
                                                    if iter in self.new_element_templates and elem['type'] == self.new_element_templates[iter]['type']:
                                                        self.new_element_templates[iter] = utils.deep_update_dict(
                                                                            self.new_element_templates[iter],
                                                                            tmp_template[tmpl_name])
                                                        new_additional_keys += [tmpl_name]
                                                    else:
                                                        logging.error("Error! The requirement is not defined")
                                                        sys.exit(1)

                        self.new_element_templates = utils.deep_update_dict(self.new_element_templates,
                                                                            self.translate_specific_types(tmp_template, tmpl_name))
        for key in self.new_element_templates:
            if key in element_templates:
                element_templates.pop(key)
        for key in additional_keys:
            if key in element_templates:
                element_templates.pop(key)
        for key in new_additional_keys:
            if key in self.new_element_templates:
                self.new_element_templates.pop(key)
        # оч смахивает на костыль, но пока ничего другого не придумал вообще((((((((
        for key, value in self.new_element_templates.items():
            script = "configure_" + key + ".yaml"
            if 'interfaces' in value and 'Standard' in value['interfaces'] and 'configure' in value['interfaces']['Standard']:
                if 'implementation' in value['interfaces']['Standard']['configure']:
                    self.new_element_templates[key]['interfaces']['Standard']['configure']['implementation'] = script
                elif not isinstance(value['interfaces']['Standard']['configure'], dict):
                    self.new_element_templates[key]['interfaces']['Standard']['configure'] = script
        element_templates = utils.deep_update_dict(element_templates, self.new_element_templates)
        self.result_template['tosca_definitions_version'] = self.version
        self.result_template['topology_template'] = {}
        self.result_template['topology_template']['node_templates'] = element_templates
