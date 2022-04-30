import os
import unittest

import yaml
from yaml import SafeLoader

from translator import utils
from translator.translator import translate


class TestTranslate(unittest.TestCase):
    os.chdir(utils.get_project_root_path())

    def test_validate_small_tpl(self):
        output_tpl, generated_scripts = translate("examples/small_nfv_example.yaml", True, 'nfv', 'cumulus')
        self.assertEqual(generated_scripts, {})
        self.assertEqual(output_tpl, {"template successfully passed validation": "examples/small_nfv_example.yaml"})

    def test_validate_full_tpl(self):
        output_tpl, generated_scripts = translate("examples/full_nfv_example.yaml", True, 'nfv', 'cumulus')
        self.assertEqual(generated_scripts, {})
        self.assertEqual(output_tpl, {"template successfully passed validation": "examples/full_nfv_example.yaml"})

    def test_small_tpl(self):
        output_tpl, generated_scripts = translate("examples/small_nfv_example.yaml", False, 'nfv', 'cumulus')
        with open("testing/small/topology.yaml", "r") as tpl_file:
            data = yaml.load(tpl_file, Loader=SafeLoader)
        self.assertIsNotNone(output_tpl)
        self.assertIsNotNone(output_tpl['tosca_definitions_version'])
        self.assertEqual(output_tpl['tosca_definitions_version'], data['tosca_definitions_version'])
        self.assertIsNotNone(output_tpl['topology_template']['node_templates'])
        self.assertIsInstance(output_tpl['topology_template']['node_templates'], dict)
        for x_key, x in output_tpl['topology_template']['node_templates'].items():
            self.assertIsInstance(x, dict)
            self.assertIsNotNone(x['type'])
            self.assertIsNotNone(x['properties'])
            self.assertIsInstance(x['properties'], dict)
            if x['type'] == "tosca.nodes.network.Port":
                self.assertIn('ip_address', x['properties'])
                self.assertIsNotNone(x['requirements'])
                self.assertIsInstance(x['requirements'], list)
                keys_list = [list(elem.keys())[0] for elem in x['requirements']]
                self.assertIn('binding', keys_list)
                self.assertIn('link', keys_list)
            if x['type'] == "tosca.nodes.network.Network":
                self.assertIn('cidr', x['properties'])
                self.assertIn('end_ip', x['properties'])
                self.assertIn('gateway_ip', x['properties'])
                self.assertIn('network_name', x['properties'])
                self.assertIn('start_ip', x['properties'])
            if x['type'] == "tosca.nodes.Compute":
                self.assertIsNotNone(x['capabilities'])
                self.assertIsInstance(x['capabilities'], dict)
                self.assertIsNotNone(x['capabilities']['host'])
                self.assertIsNotNone(x['capabilities']['os'])
                self.assertIsInstance(x['capabilities']['host'], dict)
                self.assertIsInstance(x['capabilities']['os'], dict)
                self.assertIsNotNone(x['capabilities']['host']['properties'])
                self.assertIsNotNone(x['capabilities']['os']['properties'])
                self.assertIsInstance(x['capabilities']['host']['properties'], dict)
                self.assertIsInstance(x['capabilities']['os']['properties'], dict)
                self.assertIn('architecture', x['capabilities']['os']['properties'])
                self.assertIn('type', x['capabilities']['os']['properties'])
                self.assertIn('disk_size', x['capabilities']['host']['properties'])
                self.assertIn('mem_size', x['capabilities']['host']['properties'])
                self.assertIn('num_cpus', x['capabilities']['host']['properties'])
                self.assertIsNotNone(x['interfaces'])
                self.assertIsInstance(x['interfaces'], dict)
                self.assertIsNotNone(x['interfaces']['Standard'])
                self.assertIsInstance(x['interfaces']['Standard'], dict)
                self.assertIsNotNone(x['interfaces']['Standard']['configure'])
                self.assertIsInstance(x['interfaces']['Standard']['configure'], dict)
                self.assertIsNotNone(x['interfaces']['Standard']['configure'])
                self.assertIsInstance(x['interfaces']['Standard']['configure'], dict)
                self.assertIn('inputs', x['interfaces']['Standard']['configure'])
                self.assertIsNotNone(x['interfaces']['Standard']['configure']['inputs'])
                self.assertIsInstance(x['interfaces']['Standard']['configure']['inputs'], dict)
                self.assertIn('iPAddressDict', x['interfaces']['Standard']['configure']['inputs'])
                self.assertIsInstance(x['interfaces']['Standard']['configure']['inputs']['iPAddressDict'], dict)
                self.assertEqual(len(x['interfaces']['Standard']['configure']['inputs']['iPAddressDict']), 2)
                self.assertIn('Routing_rules', x['interfaces']['Standard']['configure']['inputs'])
                self.assertIsInstance(x['interfaces']['Standard']['configure']['inputs']['Routing_rules'], list)
                self.assertEqual(len(x['interfaces']['Standard']['configure']['inputs']['Routing_rules']), 1)
                self.assertIn('destAddr', x['interfaces']['Standard']['configure']['inputs']['Routing_rules'][0])
                self.assertIn('sourceAddr', x['interfaces']['Standard']['configure']['inputs']['Routing_rules'][0])
                self.assertIn('Routing_routes', x['interfaces']['Standard']['configure']['inputs'])
                self.assertIsInstance(x['interfaces']['Standard']['configure']['inputs']['Routing_routes'], list)
                self.assertEqual(len(x['interfaces']['Standard']['configure']['inputs']['Routing_routes']), 1)
                self.assertIn('destCidr', x['interfaces']['Standard']['configure']['inputs']['Routing_routes'][0])
                self.assertIn('dev', x['interfaces']['Standard']['configure']['inputs']['Routing_routes'][0])
                self.assertIn('gateway', x['interfaces']['Standard']['configure']['inputs']['Routing_routes'][0])
                self.assertIn('src', x['interfaces']['Standard']['configure']['inputs']['Routing_routes'][0])
                self.assertIn('implementation', x['interfaces']['Standard']['configure'])
                self.assertIn('ports', x['properties'])
                self.assertIsNotNone(x['properties']['ports'])
                self.assertIsInstance(x['properties']['ports'], dict)
                self.assertIsNotNone(x['properties']['ports']['internal'])
                self.assertIsInstance(x['properties']['ports']['internal'], dict)
                self.assertIsNotNone(x['properties']['ports']['internal']['addresses'])
                self.assertIsInstance(x['properties']['ports']['internal']['addresses'], list)
                self.assertEqual(len(x['properties']['ports']['internal']['addresses']), 2)
            for y_key, y in data['topology_template']['node_templates'].items():
                if x_key == y_key:
                    self.assertEqual(x['type'], y['type'])
        files = os.listdir("testing/small")
        self.assertEqual(set(files), set(generated_scripts.keys()) | {"topology.yaml"})
        for key, value in generated_scripts.items():
            with open("testing/small/" + key, "r") as tpl_file:
                data = tpl_file.readlines()
            self.assertEqual(value, data)

    def test_full_tpl(self):
        output_tpl, generated_scripts = translate("examples/full_nfv_example.yaml", False, 'nfv', 'cumulus')
        with open("testing/full/topology.yaml", "r") as tpl_file:
            data = yaml.load(tpl_file, Loader=SafeLoader)
        self.assertIsNotNone(output_tpl)
        self.assertEqual(output_tpl, data)
        files = os.listdir("testing/full")
        self.assertEqual(set(files), set(generated_scripts.keys()) | {"topology.yaml"})
        for key, value in generated_scripts.items():
            with open("testing/full/" + key, "r") as tpl_file:
                data = tpl_file.readlines()
            self.assertEqual(value, data)


if __name__ == '__main__':
    unittest.main()
