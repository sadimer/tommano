import copy
import translator.utils as utils

class ToscaNormativeTemplate(object):
    def __init__(self, tosca_parser_tpl, yaml_dict_mapping):
        topology_template = tosca_parser_tpl.topology_template
        self.definitions = topology_template.custom_defs
        self.node_templates = {}
        self.relationship_templates = {}
        for tmpl in topology_template.nodetemplates:
            self.node_templates[tmpl.name] = tmpl.entity_tpl
        for tmpl in topology_template.relationship_templates:
            self.relationship_templates[tmpl.name] = tmpl.entity_tpl
        self.mapping = yaml_dict_mapping
        self.translate_to_tosca()

    def translate_to_tosca(self):
        element_templates = copy.copy(self.node_templates)
        element_templates.update(copy.copy(self.relationship_templates))
        new_element_templates = {}
        for tmpl_name, element in element_templates.items():
            (namespace, element_type, element_name) = utils.tosca_type_parse(element['type'])
            if namespace == 'nfv':
                for item in self.mapping:
                    None
                    # TODO