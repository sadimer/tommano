import copy
import translator.utils as utils
import ipaddress

import logging
import sys

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
        self.mapping = yaml_dict_mapping
        self.translate_to_tosca()

    def get_result_template(self):
        return self.result_template

    # типы которых нет в nfv, но они нужны для развертывания
    def translate_specific_types(self, tmp_template, tmpl_name):
        if tmp_template != {}:
            if tmp_template[tmpl_name]['type'] == 'tosca.nodes.network.Port':
                if 'properties' not in tmp_template[tmpl_name] or 'ip_address' not in tmp_template[tmpl_name]['properties']:
                    # проверь всегда ли VL к этому моменту будет сощдана (если нет будет ошибка по requirements)
                    if 'properties' not in tmp_template[tmpl_name]:
                        tmp_template[tmpl_name]['properties'] = {}
                    for elem in tmp_template[tmpl_name]['requirements']:
                        if 'link' in elem:
                            start = int(ipaddress.IPv4Address(self.new_element_templates[elem['link']]['properties']['start_ip']))
                            end = int(ipaddress.IPv4Address(self.new_element_templates[elem['link']]['properties']['end_ip']))
                            address = str(ipaddress.IPv4Address(utils.get_random_int(start, end)))
                            tmp_template[tmpl_name]['properties']['ip_address'] = address
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

    def translate_to_tosca(self):
        self.result_template = {}
        self.new_element_templates = {}
        additional_keys = []
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

                                            if 'change_name' in elem:
                                                if elem['change_name'] == False:
                                                    if iter not in self.new_element_templates or elem['type'] != self.new_element_templates[iter]['type']:
                                                        logging.error("Error! The requirement is not defined")
                                                        sys.exit(1)
                                                elif elem['change_name'] == True:
                                                    if iter in self.new_element_templates and elem['type'] == self.new_element_templates[iter]['type']:
                                                        tmp_template[tmpl_name] = self.new_element_templates.pop(iter)
                                                        additional_keys += [iter]
                                                    else:
                                                        logging.error("Error! The requirement is not defined")
                                                        sys.exit(1)


                        self.new_element_templates = utils.deep_update_dict(self.new_element_templates, self.translate_specific_types(tmp_template, tmpl_name))
        for key in self.new_element_templates:
            if key in element_templates:
                element_templates.pop(key)
        for key in additional_keys:
            if key in element_templates:
                element_templates.pop(key)
        element_templates = utils.deep_update_dict(element_templates, self.new_element_templates)
        self.result_template['tosca_definitions_version'] = self.version
        self.result_template['topology_template'] = {}
        self.result_template['topology_template']['node_templates'] = element_templates
