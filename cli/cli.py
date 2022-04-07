import argparse
import sys
import yaml
import os

from translator.translator import translate

TOPOLOGY_TPL_NAME = '/topology.yaml'


class TranslatorCli(object):
    def __init__(self, argv):
        parser = self.get_parser()
        (args, args_list) = parser.parse_known_args(argv)
        self.template_file = os.getcwd() + '/' + args.template_file
        self.output_dir = args.output_dir
        if self.output_dir and not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.validate_only = args.validate_only
        self.output_file, self.generated_scripts = translate(self.template_file, self.validate_only)
        if self.output_dir:
            with open(self.output_dir + TOPOLOGY_TPL_NAME, "w+") as f:
                yaml.dump(self.output_file, f)
            for key, script in self.generated_scripts.items():
                with open(self.output_dir + '/' + key, "w+") as ouf:
                    for line in script:
                        print(line, file=ouf, end='')
        else:
            print(yaml.dump(self.output_file))
            for key, script in self.generated_scripts.items():
                print("\n" + key + ":")
                for line in script:
                    print(line, end='')

    def get_parser(self):
        parser = argparse.ArgumentParser(prog="nfv_tosca_translator")
        parser.add_argument('--template-file',
                            metavar='<filename>',
                            required=True,
                            help='YAML TOSCA NFV template to parse')
        parser.add_argument('--validate-only',
                            action='store_true',
                            default=False,
                            help='Only validate input NFV template, do not perform translation')
        parser.add_argument('--output-dir',
                            metavar='<dirname>',
                            required=False,
                            help='Output dir for TOSCA normative template and configure scripts')
        return parser


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    TranslatorCli(args)


if __name__ == '__main__':
    main()
