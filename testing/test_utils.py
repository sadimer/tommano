import unittest
import os
from translator import utils


class TestUtils(unittest.TestCase):
    def test_project_root_path(self):
        self.assertEqual(
            os.path.dirname(os.path.dirname(__file__)), utils.get_project_root_path()
        )

    def test_get_random_int(self):
        self.assertIn(utils.get_random_int(0, 1), [0, 1])

    def test_tosca_type_parse(self):
        namespace, category, type_name = utils.tosca_type_parse("tosca.nodes.Compute")
        self.assertEqual(namespace, "tosca")
        self.assertEqual(category, "nodes")
        self.assertEqual(type_name, "Compute")
        namespace, category, type_name = utils.tosca_type_parse(
            "tosca.nodes.network.Network"
        )
        self.assertEqual(namespace, "tosca")
        self.assertEqual(category, "nodes")
        self.assertEqual(type_name, "network.Network")

    def test_str_dots_to_dict(self):
        self.assertEqual(
            utils.str_dots_to_dict("dict1.dict2.dict3", "test"),
            {"dict1": {"dict2": {"dict3": "test"}}},
        )
        self.assertEqual(
            utils.str_dots_to_dict("[].dict1.dict2", "test"),
            [{"dict1": {"dict2": "test"}}],
        )
        self.assertEqual(
            utils.str_dots_to_dict("dict1.0.dict2", "test"),
            {"dict1": [{"dict2": "test"}]},
        )
        self.assertEqual(
            utils.str_dots_to_dict("dict1.dict2.[0]", "test"),
            {"dict1": {"dict2": ["test"]}},
        )

    def test_str_dots_to_arr(self):
        self.assertEqual(
            utils.str_dots_to_arr("dict1.dict2.dict3"), ["dict1", "dict2", "dict3"]
        )

    def test_deep_update_dict(self):
        source = {"dict1": {"dict2": {"dict3": "test"}}}
        overrides = {"new_dict1": "test"}
        self.assertEqual(
            utils.deep_update_dict(source, overrides),
            {"dict1": {"dict2": {"dict3": "test"}}, "new_dict1": "test"},
        )
        overrides = {"dict1": {"new_dict2": "test"}}
        self.assertEqual(
            utils.deep_update_dict(source, overrides),
            {
                "dict1": {"dict2": {"dict3": "test"}, "new_dict2": "test"},
                "new_dict1": "test",
            },
        )
        overrides = {"dict1": {"dict2": {"new_dict3": "test"}}}
        self.assertEqual(
            utils.deep_update_dict(source, overrides),
            {
                "dict1": {
                    "dict2": {"dict3": "test", "new_dict3": "test"},
                    "new_dict2": "test",
                },
                "new_dict1": "test",
            },
        )
        source = {"dict1": {"dict2": {"dict3": "test"}}}
        overrides = {"dict1": {"dict2": {"dict3": {"dict4": "test"}}}}
        self.assertEqual(
            utils.deep_update_dict(source, overrides),
            {"dict1": {"dict2": {"dict3": {"dict4": "test"}}}},
        )

    def test_generate_random_subnet(self):
        res = utils.str_dots_to_arr(utils.generate_random_subnet())
        self.assertEqual(len(res), 4)
        self.assertIn(int(res[0]), [10, 192, 172])
        if res[0] == "172":
            self.assertIn(int(res[1]), range(16, 32))
        elif res[0] == "192":
            self.assertEqual(int(res[1]), 168)
        elif res[0] == "10":
            self.assertIn(int(res[1]), range(256))
        self.assertIn(int(res[2]), range(256))
        self.assertEqual(res[3], "0/24")


if __name__ == "__main__":
    unittest.main()
