import argparse
import sys
import yaml
import os

from translator.translator import translate

class TranslatorCli(object):
    def __init__(self, argv):
        parser = self.get_parser()
        (args, args_list) = parser.parse_known_args(argv)
        self.template_file = os.getcwd() + '/' + args.template_file
        self.output_file = args.output_file
        self.validate_only = args.validate_only
        self.output = translate(self.template_file, self.validate_only)
        if self.output_file:
            with open(self.output_file, "w+") as f:
                yaml.dump(self.output, f)
        else:
            print(yaml.dump(self.output))

    def get_parser(self):
        parser = argparse.ArgumentParser(prog="nfv-toscatranslator")
        parser.add_argument('--template-file',
                            metavar='<filename>',
                            required=True,
                            help='YAML TOSCA NFV template to parse')
        parser.add_argument('--validate-only',
                            action='store_true',
                            default=False,
                            help='Only validate input NFV template, do not perform translation')
        parser.add_argument('--output-file',
                            metavar='<filename>',
                            required=False,
                            help='Output file for TOSCA normative template')
        return parser

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    TranslatorCli(args)


if __name__ == '__main__':
    main()