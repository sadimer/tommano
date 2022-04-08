import copy
import translator.utils as utils
import ipaddress
import yaml
import logging
import sys

DEF_PATH = '/definitions/'
TRANS_PATH = '/translator/'

from toscaparser.functions import GetProperty


class ToscaNormativeTemplate(object):
    """
        Класс транслятора
        Вход:
        1) tosca_parser_tpl - тип который вернул tosca-parser
        2) yaml_dict_mapping - yaml dict маппинга TOSCA_NFV_mapping.yaml
        Атрибуты:
        self.definitions - yaml dict определений типов NFV и нормативной TOCSA
        self.node_templates - шаблоны узлов в данной топологии
        self.relationship_templates - шаблоны отношений в данной топологии
        self.version - версия TOSCA
        self.mapping - yaml dict маппинга TOSCA_NFV_mapping.yaml
        self.generated_scripts - dict of lists строк ansible скриптов для настройки compute узлов
        self.num_addresses - dict в ктором лежит таблица соответствия адресов и compute узлов в формате {host:[address1, address2]}
        self.result_template - итоговой нормативный шаблон TOSCA
        self.new_element_templates - промежуточный dict для обработки сгенерированных шаблонов
        Методы:
        get_result - возвращает результат обработки: result_template и generated_scripts
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
        logging.info("Successfully resolved get_property functions in TOSCA NFV template.")
        self.mapping = yaml_dict_mapping
        self.expand_mapping()
        logging.info("Successfully expand types in mapping.")
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
                self.mapping[key] = utils.deep_update_dict(self.mapping[key],
                                                           self.mapping[self.definitions[key]['derived_from']])
                key = self.definitions[key]['derived_from']

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
                    else:
                        logging.error("Error! Unknown type of 'configure'.")
                        sys.exit(1)
                    try:
                        with open(def_file, "r+") as f:
                            vnf_def = f.readlines()
                    except:
                        logging.error("Error! Failed to open VNF template file.")
                        sys.exit(1)

                    if 'properties' in tmp_template[tmpl_name]:
                        if 'meta' in tmp_template[tmpl_name]['properties']:
                            script = "configure_" + tmp_template[tmpl_name]['properties']['meta'] + ".yaml"
                            if script not in self.generated_scripts:
                                self.generated_scripts[script] = vnf_def
                            else:
                                self.generated_scripts[script] += vnf_def
                        else:
                            logging.error("Error! VNFD hasn't meta, please check mapping for VNFD.")
                            sys.exit(1)

            if tmp_template[tmpl_name]['type'] == 'tosca.nodes.network.Port':
                if 'properties' not in tmp_template[tmpl_name] or 'ip_address' not in tmp_template[tmpl_name][
                    'properties']:
                    if 'properties' not in tmp_template[tmpl_name]:
                        tmp_template[tmpl_name]['properties'] = {}
                    if 'requirements' in tmp_template[tmpl_name]:
                        flag = False
                        for elem in tmp_template[tmpl_name]['requirements']:
                            if 'link' in elem:
                                start = int(ipaddress.IPv4Address(
                                    self.new_element_templates[elem['link']]['properties']['start_ip']))
                                end = int(ipaddress.IPv4Address(
                                    self.new_element_templates[elem['link']]['properties']['end_ip']))
                                address = str(ipaddress.IPv4Address(utils.get_random_int(start, end)))
                                tmp_template[tmpl_name]['properties']['ip_address'] = address
                                flag = True
                                break
                        if not flag:
                            logging.error("Error! No link requirement.")
                            sys.exit(1)
                else:
                    if 'requirements' in tmp_template[tmpl_name]:
                        address = tmp_template[tmpl_name]['properties']['ip_address']
                        ext = False
                        for elem in tmp_template[tmpl_name]['requirements']:
                            if 'link' in elem:
                                ext = False
                                if 'properties' in self.new_element_templates[elem['link']] and 'cidr' in \
                                        self.new_element_templates[elem['link']]['properties']:
                                    cidr = self.new_element_templates[elem['link']]['properties']['cidr']
                                else:
                                    logging.error("Error! Network dont have cidr.")
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
                                                'iPAddressDict': {
                                                    len(self.num_addresses[elem['binding']]): {address: cidr}}}}}}})
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
                    new_data[key] = self.resolve_get_property_functions(value,
                                                                        tmpl_name if tmpl_name is not None else key)
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
                        return self.get_property_value([req[value[1]]['node']] + value[2:], req[value[1]]['node'])
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
            logging.error("Failed to get property: %s." % yaml.dump(value))
            sys.exit(1)
        return tmpl_properties

    def translate_to_tosca(self):
        self.result_template = {}
        self.new_element_templates = {}
        additional_keys = []
        new_additional_keys = []
        element_templates = copy.copy(self.node_templates)
        element_templates.update(copy.copy(self.relationship_templates))
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
                                                            tmp_template[tmpl_name] = utils.deep_update_dict(
                                                                tmp_template[tmpl_name],
                                                                utils.str_dots_to_dict(elem['parameter'],
                                                                                       elem['format'].format(iter)))
                                                        else:
                                                            tmp_template[tmpl_name] = utils.str_dots_to_dict(
                                                                elem['parameter'],
                                                                elem['format'].format(iter))
                                                else:
                                                    if tmpl_name in tmp_template:
                                                        tmp_template[tmpl_name] = utils.deep_update_dict(
                                                            tmp_template[tmpl_name],
                                                            utils.str_dots_to_dict(elem['parameter'], iter))
                                                    else:
                                                        tmp_template[tmpl_name] = utils.str_dots_to_dict(
                                                            elem['parameter'], iter)
                                            if 'type' in elem:
                                                if tmpl_name in tmp_template:
                                                    if 'type' not in tmp_template[tmpl_name]:
                                                        tmp_template[tmpl_name] = utils.deep_update_dict(
                                                            tmp_template[tmpl_name],
                                                            {'type': elem['type']})
                                                else:
                                                    tmp_template[tmpl_name] = {'type': elem['type']}
                                            else:
                                                logging.error("Error! Undefined node type in template.")
                                                sys.exit(1)

                                            if 'node_name' in elem:
                                                if elem['node_name'] == 'check':
                                                    if iter not in self.new_element_templates or elem['type'] != \
                                                            self.new_element_templates[iter]['type']:
                                                        logging.error("Error! The requirement is not defined.")
                                                        sys.exit(1)
                                                elif elem['node_name'] == 'rename':
                                                    if iter in self.new_element_templates and elem['type'] == \
                                                            self.new_element_templates[iter]['type']:
                                                        tmp_template[tmpl_name] = utils.deep_update_dict(
                                                            tmp_template[tmpl_name],
                                                            self.new_element_templates.pop(iter))
                                                        additional_keys += [iter]
                                                    else:
                                                        logging.error("Error! The requirement is not defined.")
                                                        sys.exit(1)
                                                elif elem['node_name'] == 'not change':
                                                    if iter in self.new_element_templates and elem['type'] == \
                                                            self.new_element_templates[iter]['type']:
                                                        self.new_element_templates[iter] = utils.deep_update_dict(
                                                            self.new_element_templates[iter],
                                                            tmp_template[tmpl_name])
                                                        new_additional_keys += [tmpl_name]
                                                    else:
                                                        logging.error("Error! The requirement is not defined.")
                                                        sys.exit(1)
                                                else:
                                                    logging.warning("Unknown node_name parameter.")
                        self.new_element_templates = utils.deep_update_dict(self.new_element_templates,
                                                                            self.translate_specific_types(tmp_template,
                                                                                                          tmpl_name))
                        logging.info("Successfully parsed {} node.".format(tmpl_name))
        for key in self.new_element_templates:
            if key in element_templates:
                element_templates.pop(key)
        for key in additional_keys:
            if key in element_templates:
                element_templates.pop(key)
        for key in new_additional_keys:
            if key in self.new_element_templates:
                self.new_element_templates.pop(key)
        logging.info("Successfully delete unused nodes.")
        for key, value in self.new_element_templates.items():
            script = "configure_" + key + ".yaml"
            if 'interfaces' in value and 'Standard' in value['interfaces'] and 'configure' in value['interfaces'][
                'Standard']:
                if 'implementation' in value['interfaces']['Standard']['configure']:
                    self.new_element_templates[key]['interfaces']['Standard']['configure']['implementation'] = script
                    logging.info("Successfully added {} script to {}.".format(script, key))
                elif not isinstance(value['interfaces']['Standard']['configure'], dict):
                    self.new_element_templates[key]['interfaces']['Standard']['configure'] = script
                    logging.info("Successfully added {} script to {}.".format(script, key))
                else:
                    logging.error("Error! Unknown type of 'configure'.")
                    sys.exit(1)
        element_templates = utils.deep_update_dict(element_templates, self.new_element_templates)
        self.result_template['tosca_definitions_version'] = self.version
        self.result_template['topology_template'] = {}
        self.result_template['topology_template']['node_templates'] = element_templates
